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
    #    Score basé sur distance d’édition normalisée.
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
            s.code_postal,
            -- score: 1 - dist / max_len
            CASE
              WHEN greatest(length(s.name_norm), length(r.title_norm)) = 0 THEN 0.0
              ELSE 1.0 - (editdist3(s.name_norm, r.title_norm)::DOUBLE
                         / greatest(length(s.name_norm), length(r.title_norm))::DOUBLE)
            END AS score
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

    # 2c) Matching par ADRESSE street_norm vs street_norm (avec colonnes RNA adresse)
    #     Plus précis que street_norm vs title_norm !
    con.execute("""
        CREATE OR REPLACE TEMP TABLE candidates_address AS
        SELECT
            s.siret,
            r.id_rna,
            s.street_norm as sirene_street,
            r.street_norm as rna_street,
            -- Comparaison adresse SIRENE vs adresse RNA
            CASE
              WHEN greatest(length(s.street_norm), length(r.street_norm)) = 0 THEN 0.0
              ELSE 1.0 - (editdist3(s.street_norm, r.street_norm)::DOUBLE
                         / greatest(length(s.street_norm), length(r.street_norm))::DOUBLE)
            END AS score
        FROM read_parquet(?) s
        JOIN read_parquet(?) r
          ON s.code_postal = r.code_postal
         AND s.city_norm = r.city_norm
        WHERE s.siret NOT IN (SELECT siret FROM link_exact)
          AND (s.name_norm = '' OR s.name_norm IS NULL)
          AND (r.title_norm = '' OR r.title_norm IS NULL)
          AND s.street_norm != ''
          AND s.street_norm IS NOT NULL
          AND r.street_norm != ''
          AND r.street_norm IS NOT NULL
          AND length(s.code_postal) = 5
          AND length(r.code_postal) = 5;
    """, [SIRENE_SILVER, RNA_SILVER])

    address_cand_count = con.execute("SELECT count(*) FROM candidates_address").fetchone()[0]
    log(f"Address candidates (both without name): {address_cand_count:,}")

    con.execute("""
        CREATE OR REPLACE TEMP TABLE link_address AS
        SELECT siret, id_rna, score, 'ADDRESS_MATCH' AS methode
        FROM (
            SELECT
                siret,
                id_rna,
                score,
                row_number() OVER (PARTITION BY siret ORDER BY score DESC) AS rn
            FROM candidates_address
            WHERE score >= 0.85
        )
        WHERE rn = 1;
    """)

    address_count = con.execute("SELECT count(*) FROM link_address").fetchone()[0]
    log(f"Address matches kept (score>=0.85): {address_count:,}")

    # 3) Union final : exact + blocked + address
    con.execute("""
        CREATE OR REPLACE TEMP TABLE link_final AS
        SELECT * FROM link_exact
        UNION ALL
        SELECT * FROM link_blocked
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

    # 5) Gold check : SIRET Croix Rouge
    # gold_siret = "77567227221138"
    # gold = con.execute(f"""
    #     SELECT siret, id_rna, score, methode FROM link_final WHERE siret = '{gold_siret}';
    # """).fetchall()
    
    # if gold:
    #     log(f" GOLD CHECK ({gold_siret}): {gold}")
    # else:
    #     log(f"  GOLD CHECK ({gold_siret}): PAS DE MATCH TROUVÉ")
        
    #     # Debug supplémentaire
    #     sirene_info = con.execute(f"""
    #         SELECT name_norm, street_norm, code_postal, city_norm, block_key
    #         FROM read_parquet('{SIRENE_SILVER}')
    #         WHERE siret = '{gold_siret}'
    #     """).fetchone()
        
    #     if sirene_info:
    #         log(f"   SIRENE: name='{sirene_info[0]}', street='{sirene_info[1]}', "
    #             f"cp={sirene_info[2]}, city={sirene_info[3]}, block_key='{sirene_info[4]}'")

    con.close()
    log("DONE match")

if __name__ == "__main__":
    main()