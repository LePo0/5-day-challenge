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

# seuil : évite des faux positifs
SCORE_THRESHOLD = 0.78  # ajustable selon résultats

def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def main() -> None:
    if not os.path.exists(SIRENE_SILVER):
        raise FileNotFoundError(f"Manquant: {SIRENE_SILVER} (lance make normalize)")
    if not os.path.exists(RNA_SILVER):
        raise FileNotFoundError(f"Manquant: {RNA_SILVER} (lance make normalize)")

    con = duckdb.connect(DB_PATH)
    con.execute("SET memory_limit='4GB';")

    log("MATCH SIRENE ↔ RNA : création table de liens")

    # 1) Exact match sur SIRET (quand RNA fournit le siret)
    #    On garde seulement les siret valides.
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
    log(f"Exact siret matches: {exact_count:,}")

    # 2) Matching “bloqué” pour le reste
    #    Stratégie : on limite énormément les comparaisons :
    #      - même code_postal
    #      - même block_key (prefix texte normalisé)
    #    Score COMPOSITE basé sur nom (70%) + adresse (30%) pour réduire faux positifs
    #
    # Important : on n’essaie PAS de matcher tout le monde : ce serait trop cher.
    # L’objectif est d’attraper les cas importants (dont le Gold case).
    con.execute("""
        CREATE OR REPLACE TEMP TABLE candidates_name AS
        SELECT
            s.siret,
            r.id_rna,
            s.name_norm,
            r.title_norm,
            s.street_norm,
            r.street_norm as rna_street,
            s.code_postal,
            -- Score NOM (similitude des noms)
            CASE
              WHEN greatest(length(s.name_norm), length(r.title_norm)) = 0 THEN 0.0
              ELSE 1.0 - (editdist3(s.name_norm, r.title_norm)::DOUBLE
                         / greatest(length(s.name_norm), length(r.title_norm))::DOUBLE)
            END AS score_nom,
            -- Score ADRESSE (similitude des adresses)
            CASE
              WHEN greatest(length(s.street_norm), length(r.street_norm)) = 0 THEN 0.0
              ELSE 1.0 - (editdist3(s.street_norm, r.street_norm)::DOUBLE
                         / greatest(length(s.street_norm), length(r.street_norm))::DOUBLE)
            END AS score_adresse,
            -- Score COMPOSITE : 70% nom + 30% adresse (réduit les faux positifs)
            (0.7 * CASE
              WHEN greatest(length(s.name_norm), length(r.title_norm)) = 0 THEN 0.0
              ELSE 1.0 - (editdist3(s.name_norm, r.title_norm)::DOUBLE
                         / greatest(length(s.name_norm), length(r.title_norm))::DOUBLE)
            END +
            0.3 * CASE
              WHEN greatest(length(s.street_norm), length(r.street_norm)) = 0 THEN 0.0
              ELSE 1.0 - (editdist3(s.street_norm, r.street_norm)::DOUBLE
                         / greatest(length(s.street_norm), length(r.street_norm))::DOUBLE)
            END) AS score
        FROM read_parquet(?) s
        JOIN read_parquet(?) r
          ON s.code_postal = r.code_postal
         AND s.block_key = r.block_key
        WHERE s.siret NOT IN (SELECT siret FROM link_exact)
          AND s.code_postal IS NOT NULL
          AND r.code_postal IS NOT NULL
          AND length(s.code_postal) = 5
          AND length(r.code_postal) = 5
          AND s.name_norm != ''
          AND r.title_norm != ''
          AND s.block_key != '';
    """, [SIRENE_SILVER, RNA_SILVER])

    cand_count = con.execute("SELECT count(*) FROM candidates_name").fetchone()[0]
    log(f"Candidates (blocked): {cand_count:,}")

    # Pour chaque siret, on garde le meilleur match au-dessus du seuil
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE link_blocked AS
        SELECT siret, id_rna, score, 'BLOCKED_NAME' AS methode
        FROM (
            SELECT
                siret,
                id_rna,
                score,
                row_number() OVER (PARTITION BY siret ORDER BY score DESC) AS rn
            FROM candidates_name
            WHERE score >= {SCORE_THRESHOLD}
        )
        WHERE rn = 1;
    """)

    blocked_count = con.execute("SELECT count(*) FROM link_blocked").fetchone()[0]
    log(f"Blocked name matches kept (score>={SCORE_THRESHOLD}): {blocked_count:,}")

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
    log(f"Address candidates (adresse seule): {candidates_base:,}")
    
    # 2b) PHASE B : Ajouter bonus NAME seulement sur candidats filtrés
    log("Phase B: Calcul bonus nom sur candidats filtrés...")
    
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
    """);

    address_cand_count = con.execute("SELECT count(*) FROM candidates_address").fetchone()[0]
    log(f"Address candidates (avec bonus nom): {address_cand_count:,}")

    # 2c) Sélection adaptative : seuil selon nombre de matches
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
    """);

    address_count = con.execute("SELECT count(*) FROM link_address").fetchone()[0]
    unique_count = con.execute("""
        SELECT count(*) FROM (
            SELECT siret FROM link_address GROUP BY siret HAVING count(*) = 1
        )
    """).fetchone()[0]
    log(f"Address matches kept: {address_count:,} (dont {unique_count:,} matches uniques)")

    # 3) Union final : exact + address
    con.execute("""
        CREATE OR REPLACE TEMP TABLE link_final AS
        SELECT * FROM link_exact
        UNION ALL
        SELECT * FROM link_address;
    """)

    total = con.execute("SELECT count(*) FROM link_final").fetchone()[0]
    log(f"TOTAL links: {total:,}")

    # 4) Export Parquet
    con.execute("""
        COPY link_final TO ? (FORMAT PARQUET, CODEC 'ZSTD');
    """, [LINK_OUT])

    log(f"OK écrit: {LINK_OUT}")

    con.close()
    log("DONE match")

if __name__ == "__main__":
    main()