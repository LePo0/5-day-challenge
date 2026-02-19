# etl/match.py
import os
import duckdb
from datetime import datetime

PARQUET_DIR = "data_parquet"
DUCKDB_DIR = "duckdb"
DB_PATH = os.path.join(DUCKDB_DIR, "catalog.db")

SIRENE_SILVER = os.path.join(PARQUET_DIR, "sirene_silver.parquet")
RNA_SILVER    = os.path.join(PARQUET_DIR, "rna_silver.parquet")
LINK_OUT      = os.path.join(PARQUET_DIR, "link_sirene_rna.parquet")

os.makedirs(DUCKDB_DIR, exist_ok=True)

def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def main() -> None:
    if not os.path.exists(SIRENE_SILVER):
        raise FileNotFoundError(f"Manquant: {SIRENE_SILVER} (lance make normalize)")
    if not os.path.exists(RNA_SILVER):
        raise FileNotFoundError(f"Manquant: {RNA_SILVER} (lance make normalize)")

    con = duckdb.connect(DB_PATH)
    con.execute("SET memory_limit='4GB';")
    con.execute("SET threads TO 8;")

    log("MATCH SIRENE ↔ RNA : création table de liens (VERSION OPTIMISÉE)")

    # =========================================================================
    # ÉTAPE 1 : EXACT MATCH sur SIRET
    # =========================================================================
    log("1) EXACT SIRET match...")
    
    con.execute("""
        CREATE OR REPLACE TEMP TABLE link_exact AS
        SELECT
            s.siret AS siret,
            r.id_rna AS id_rna,
            1.0::DOUBLE AS score,
            'EXACT_SIRET' AS methode
        FROM read_parquet(?) s
        JOIN read_parquet(?) r
          ON s.siret = r.siret
        WHERE r.siret IS NOT NULL
          AND length(r.siret) = 14
          AND regexp_full_match(r.siret, '^[0-9]{14}$');
    """, [SIRENE_SILVER, RNA_SILVER])

    exact_count = con.execute("SELECT count(*) FROM link_exact").fetchone()[0]
    log(f"   Exact matches: {exact_count:,}")

    # =========================================================================
    # ÉTAPE 2 : ADDRESS MATCH en 2 PHASES (OPTIMISÉ)
    # =========================================================================
    log("2) ADDRESS MATCH (2 phases : adresse puis bonus nom)...")
    
    # -------------------------------------------------------------------------
    # PHASE A : Match sur ADRESSE UNIQUEMENT (RAPIDE - sans editdist3 sur nom)
    # -------------------------------------------------------------------------
    log("   Phase A: Candidats sur adresse...")
    
    con.execute("""
        CREATE OR REPLACE TEMP TABLE candidates_address_base AS
        SELECT
            s.siret,
            r.id_rna,
            s.name_norm,
            r.title_norm,
            -- Score ADRESSE basé sur composants (SANS editdist3 sur nom)
            (
                CASE
                    WHEN COALESCE(s.numero_norm, '') = COALESCE(r.numero_norm, '') 
                         AND s.numero_norm IS NOT NULL AND s.numero_norm != '' THEN 0.30
                    ELSE 0.0
                END +
                CASE
                    WHEN COALESCE(s.type_voie_norm, '') = COALESCE(r.type_voie_norm, '') THEN 0.25
                    ELSE 0.0
                END +
                CASE
                    WHEN greatest(length(COALESCE(s.libelle_voie_norm, '')), length(COALESCE(r.libelle_voie_norm, ''))) = 0 THEN 0.0
                    ELSE 0.45 * (1.0 - (editdist3(
                        COALESCE(s.libelle_voie_norm, ''),
                        COALESCE(r.libelle_voie_norm, '')
                    )::DOUBLE / greatest(
                        length(COALESCE(s.libelle_voie_norm, 'x')),
                        length(COALESCE(r.libelle_voie_norm, 'x'))
                    )::DOUBLE))
                END
            ) AS score_adresse
        FROM read_parquet(?) s
        INNER JOIN read_parquet(?) r
            ON s.code_postal = r.code_postal
            AND COALESCE(s.numero_norm, '') = COALESCE(r.numero_norm, '')
        WHERE s.siret NOT IN (SELECT siret FROM link_exact)
          AND s.numero_norm IS NOT NULL 
          AND s.numero_norm != ''
          AND r.numero_norm IS NOT NULL
          AND r.numero_norm != ''
          AND length(s.code_postal) = 5
          AND length(r.code_postal) = 5;
    """, [SIRENE_SILVER, RNA_SILVER])

    candidates_base = con.execute("SELECT count(*) FROM candidates_address_base").fetchone()[0]
    log(f"      {candidates_base:,} candidats (adresse seule)")
    
    # -------------------------------------------------------------------------
    # PHASE B : Bonus NAME sur candidats filtrés (RAPIDE - seulement ~2M lignes)
    # -------------------------------------------------------------------------
    log("   Phase B: Ajout bonus nom...")
    
    con.execute("""
        CREATE OR REPLACE TEMP TABLE candidates_address AS
        SELECT
            siret,
            id_rna,
            score_adresse,
            -- Bonus NAME calculé seulement ici (bien moins de lignes)
            CASE 
                WHEN name_norm != '' AND name_norm IS NOT NULL
                     AND title_norm != '' AND title_norm IS NOT NULL
                     AND greatest(length(name_norm), length(title_norm)) > 0
                THEN 1.0 - (editdist3(name_norm, title_norm)::DOUBLE / 
                           greatest(length(name_norm), length(title_norm))::DOUBLE)
                ELSE 0.0 
            END as score_name,
            -- Score composite final : 70% adresse + 30% nom
            (
                0.70 * score_adresse +
                0.30 * CASE 
                    WHEN name_norm != '' AND name_norm IS NOT NULL
                         AND title_norm != '' AND title_norm IS NOT NULL
                         AND greatest(length(name_norm), length(title_norm)) > 0
                    THEN 1.0 - (editdist3(name_norm, title_norm)::DOUBLE / 
                               greatest(length(name_norm), length(title_norm))::DOUBLE)
                    ELSE 0.0 
                END
            ) as score
        FROM candidates_address_base
        WHERE score_adresse >= 0.40;  -- Pré-filtre : adresse doit matcher au moins 40%
    """)

    address_cand_count = con.execute("SELECT count(*) FROM candidates_address").fetchone()[0]
    log(f"      {address_cand_count:,} candidats (avec bonus nom)")
    
    # -------------------------------------------------------------------------
    # PHASE C : Sélection adaptative selon nombre de matches
    # -------------------------------------------------------------------------
    log("   Phase C: Sélection adaptative...")
    
    con.execute("""
        CREATE OR REPLACE TEMP TABLE link_address AS
        WITH ranked_matches AS (
            SELECT
                siret,
                id_rna,
                score,
                row_number() OVER (PARTITION BY siret ORDER BY score DESC) AS rn,
                count(*) OVER (PARTITION BY siret) AS match_count
            FROM candidates_address
        )
        SELECT 
            siret, 
            id_rna, 
            score, 
            'ADDRESS_MATCH' AS methode
        FROM ranked_matches
        WHERE 
            -- Cas 1 : Match unique → garder même si score moyen
            (match_count = 1 AND score >= 0.50)  
            -- Cas 2 : Plusieurs matches → garder score élevé
            OR (match_count > 1 AND score >= 0.70)
            -- Cas 3 : Plusieurs matches faibles → garder le meilleur
            OR (match_count > 1 AND rn = 1 AND score >= 0.50);
    """)

    address_count = con.execute("SELECT count(*) FROM link_address").fetchone()[0]
    unique_count = con.execute("""
        SELECT count(*) FROM (
            SELECT siret FROM link_address GROUP BY siret HAVING count(*) = 1
        )
    """).fetchone()[0]
    log(f"   ADDRESS matches: {address_count:,} (dont {unique_count:,} uniques)")

    # =========================================================================
    # ÉTAPE 3 : FUSION FINALE
    # =========================================================================
    log("3) Fusion finale...")
    
    con.execute("""
        CREATE OR REPLACE TEMP TABLE link_final AS
        SELECT * FROM link_exact
        UNION ALL
        SELECT * FROM link_address;
    """)

    total = con.execute("SELECT count(*) FROM link_final").fetchone()[0]
    exact_pct = exact_count / total * 100 if total > 0 else 0
    address_pct = address_count / total * 100 if total > 0 else 0
    
    log(f"   TOTAL links: {total:,}")
    log(f"     - EXACT_SIRET   : {exact_count:,} ({exact_pct:.1f}%)")
    log(f"     - ADDRESS_MATCH : {address_count:,} ({address_pct:.1f}%)")

    # =========================================================================
    # ÉTAPE 4 : EXPORT
    # =========================================================================
    log("4) Export Parquet...")
    
    con.execute("""
        COPY link_final TO ? (FORMAT PARQUET, CODEC 'ZSTD');
    """, [LINK_OUT])

    log(f"   Écrit: {LINK_OUT}")
    
    con.close()
    log("✅ DONE")

if __name__ == "__main__":
    main()
