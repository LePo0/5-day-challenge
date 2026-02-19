# etl/match.py - VERSION ULTRA-OPTIMISÉE
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
        raise FileNotFoundError(f"Manquant: {SIRENE_SILVER}")
    if not os.path.exists(RNA_SILVER):
        raise FileNotFoundError(f"Manquant: {RNA_SILVER}")

    con = duckdb.connect(DB_PATH)
    con.execute("SET memory_limit='6GB';")
    con.execute("SET threads TO 8;")

    log("MATCH SIRENE ↔ RNA : VERSION ULTRA-OPTIMISÉE")
    log("  → Matching PROGRESSIF par code_postal (pas toutes les adresses)")
    log("  → Filtrage STRICT avant editdist3 (type_voie obligatoire)")
    log("  → Calcul NAME une seule fois (pas de doublon)")

    # =========================================================================
    # ÉTAPE 0 : CHARGEMENT + INDEXATION (CODE_POSTAL en priorité)
    # =========================================================================
    log("0) Chargement + indexation par code_postal...")
    
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE sirene_active AS
        SELECT 
            siret, 
            code_postal, 
            numero_norm, 
            type_voie_norm, 
            libelle_voie_norm,
            name_norm
        FROM read_parquet('{SIRENE_SILVER}')
        WHERE code_postal IS NOT NULL 
          AND length(code_postal) = 5
          AND numero_norm IS NOT NULL 
          AND numero_norm != ''
          AND type_voie_norm IS NOT NULL
          AND type_voie_norm != '';
    """)
    
    # INDEX sur (code_postal, numero_norm, type_voie_norm)
    # Permet JOIN rapide progressif : d'abord code_postal, puis numero, puis type_voie
    con.execute("CREATE INDEX idx_sirene_cp_num_type ON sirene_active(code_postal, numero_norm, type_voie_norm);")
    
    sirene_count = con.execute("SELECT count(*) FROM sirene_active").fetchone()[0]
    log(f"   SIRENE indexés: {sirene_count:,}")
    
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE rna_active AS
        SELECT 
            siret as rna_siret,
            id_rna, 
            code_postal, 
            numero_norm, 
            type_voie_norm, 
            libelle_voie_norm,
            title_norm
        FROM read_parquet('{RNA_SILVER}')
        WHERE code_postal IS NOT NULL 
          AND length(code_postal) = 5
          AND numero_norm IS NOT NULL 
          AND numero_norm != ''
          AND type_voie_norm IS NOT NULL
          AND type_voie_norm != '';
    """)
    
    # INDEX identique pour RNA
    con.execute("CREATE INDEX idx_rna_cp_num_type ON rna_active(code_postal, numero_norm, type_voie_norm);")
    
    rna_count = con.execute("SELECT count(*) FROM rna_active").fetchone()[0]
    log(f"   RNA indexés: {rna_count:,}")

    # =========================================================================
    # ÉTAPE 1 : EXACT MATCH sur SIRET
    # =========================================================================
    log("1) EXACT SIRET match...")
    
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE link_exact AS
        SELECT
            s.siret,
            r.id_rna,
            1.0::DOUBLE AS score,
            'EXACT_SIRET' AS methode
        FROM read_parquet('{SIRENE_SILVER}') s
        JOIN read_parquet('{RNA_SILVER}') r ON s.siret = r.siret
        WHERE r.siret IS NOT NULL
          AND length(r.siret) = 14
          AND regexp_full_match(r.siret, '^[0-9]{{14}}$');
    """)

    exact_count = con.execute("SELECT count(*) FROM link_exact").fetchone()[0]
    log(f"   Matches exacts: {exact_count:,}")

    # =========================================================================
    # ÉTAPE 2 : ADDRESS MATCH PROGRESSIF (code_postal → numero → type_voie)
    # =========================================================================
    log("2) ADDRESS MATCH progressif (par code_postal)...")
    
    # -------------------------------------------------------------------------
    # PHASE A : Filtrage STRICT (avant editdist3 coûteux)
    # -------------------------------------------------------------------------
    log("   Phase A: Filtrage strict par code_postal + numero + type_voie...")
    
    con.execute("""
        CREATE OR REPLACE TEMP TABLE candidates_strict AS
        SELECT
            s.siret,
            r.id_rna,
            s.name_norm,
            r.title_norm,
            s.libelle_voie_norm,
            r.libelle_voie_norm as rna_libelle_voie_norm
        FROM sirene_active s
        INNER JOIN rna_active r
            -- JOIN PROGRESSIF : d'abord code_postal (réduit énormément)
            ON s.code_postal = r.code_postal           -- Filtre 1 : même département/ville
            AND s.numero_norm = r.numero_norm          -- Filtre 2 : même numéro
            AND s.type_voie_norm = r.type_voie_norm    -- Filtre 3 : même type (RUE, AV, etc)
        WHERE s.siret NOT IN (SELECT siret FROM link_exact);
    """)

    strict_count = con.execute("SELECT count(*) FROM candidates_strict").fetchone()[0]
    log(f"      {strict_count:,} candidats après filtrage strict")
    log(f"      (réduit de ~80M à {strict_count:,} = {strict_count/80000000*100:.3f}%)")
    
    # -------------------------------------------------------------------------
    # PHASE B : Score ADRESSE (editdist3 seulement sur libelle_voie restant)
    # -------------------------------------------------------------------------
    log("   Phase B: Score adresse sur candidats filtrés...")
    
    con.execute("""
        CREATE OR REPLACE TEMP TABLE candidates_address_scored AS
        SELECT
            siret,
            id_rna,
            name_norm,
            title_norm,
            -- Score ADRESSE : 
            -- - code_postal + numero + type_voie déjà matchés (0.70)
            -- - libelle_voie avec editdist3 (0.30)
            (
                0.70 +  -- code_postal + numero + type_voie matchés (garanti par JOIN)
                CASE 
                    WHEN libelle_voie_norm = rna_libelle_voie_norm THEN 0.30  -- Exact
                    WHEN libelle_voie_norm IS NULL OR rna_libelle_voie_norm IS NULL THEN 0.15  -- Manquant
                    WHEN editdist3(libelle_voie_norm, rna_libelle_voie_norm) <= 2 THEN 0.25  -- Très proche (1-2 chars)
                    WHEN editdist3(libelle_voie_norm, rna_libelle_voie_norm) <= 5 THEN 0.15  -- Proche (3-5 chars)
                    ELSE 0.05  -- Différent
                END
            ) AS score_adresse
        FROM candidates_strict
        WHERE libelle_voie_norm IS NOT NULL 
          OR rna_libelle_voie_norm IS NOT NULL;
    """)

    scored_count = con.execute("SELECT count(*) FROM candidates_address_scored").fetchone()[0]
    log(f"      {scored_count:,} candidats avec score adresse")
    
    # -------------------------------------------------------------------------
    # PHASE C : Bonus NAME (calcul UNE SEULE FOIS avec CTE)
    # -------------------------------------------------------------------------
    log("   Phase C: Bonus nom (calcul unique)...")
    
    con.execute("""
        CREATE OR REPLACE TEMP TABLE candidates_address AS
        WITH name_scores AS (
            SELECT
                siret,
                id_rna,
                score_adresse,
                -- Calcul NAME UNE SEULE FOIS
                CASE 
                    WHEN name_norm IS NOT NULL AND name_norm != ''
                         AND title_norm IS NOT NULL AND title_norm != ''
                         AND greatest(length(name_norm), length(title_norm)) > 0
                    THEN 1.0 - (editdist3(name_norm, title_norm)::DOUBLE / 
                               greatest(length(name_norm), length(title_norm))::DOUBLE)
                    ELSE 0.0 
                END as score_name
            FROM candidates_address_scored
        )
        SELECT
            siret,
            id_rna,
            score_adresse,
            score_name,
            -- Score composite : réutilise score_name (pas de recalcul)
            (0.70 * score_adresse + 0.30 * score_name) as score
        FROM name_scores
        WHERE score_adresse >= 0.75;  -- Adresse doit être bonne (code_postal + numero + type_voie OK)
    """)

    address_cand = con.execute("SELECT count(*) FROM candidates_address").fetchone()[0]
    log(f"      {address_cand:,} candidats avec bonus nom")
    
    # -------------------------------------------------------------------------
    # PHASE D : Sélection adaptative
    # -------------------------------------------------------------------------
    log("   Phase D: Sélection adaptative...")
    
    con.execute("""
        CREATE OR REPLACE TEMP TABLE link_address AS
        WITH ranked AS (
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
        FROM ranked
        WHERE 
            -- Cas 1 : Match unique → garder si score >= 0.50
            (match_count = 1 AND score >= 0.50)
            -- Cas 2 : Plusieurs matches → garder score >= 0.70
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
    
    con.execute(f"""
        COPY link_final TO '{LINK_OUT}' (FORMAT PARQUET, CODEC 'ZSTD');
    """)

    log(f"   Écrit: {LINK_OUT}")
    
    con.close()
    log("✅ DONE - Matching progressif terminé")

if __name__ == "__main__":
    main()
