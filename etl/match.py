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
        CREATE OR REPLACE TEMP TABLE candidates AS
        SELECT
            s.siret,
            r.id_rna,
            s.name_norm,
            r.title_norm,
            s.code_postal,
            -- score: 1 - dist / max_len
            CASE
              WHEN greatest(length(s.name_norm), length(r.title_norm)) = 0 THEN 0.0
              ELSE 1.0 - (edit_distance(s.name_norm, r.title_norm)::DOUBLE
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
          AND length(r.code_postal) = 5;
    """, [SIRENE_SILVER, RNA_SILVER])

    cand_count = con.execute("SELECT count(*) FROM candidates").fetchone()[0]
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
            FROM candidates
            WHERE score >= {SCORE_THRESHOLD}
        )
        WHERE rn = 1;
    """)

    blocked_count = con.execute("SELECT count(*) FROM link_blocked").fetchone()[0]
    log(f"Blocked name matches kept (score>={SCORE_THRESHOLD}): {blocked_count:,}")

    # 3) Union final : exact + blocked (sans doublons)
    con.execute("""
        CREATE OR REPLACE TEMP TABLE link_final AS
        SELECT * FROM link_exact
        UNION ALL
        SELECT * FROM link_blocked;
    """)

    total = con.execute("SELECT count(*) FROM link_final").fetchone()[0]
    log(f"TOTAL links: {total:,}")

    # 4) Export Parquet
    con.execute("""
        COPY (SELECT siret, id_rna, score, methode FROM link_final)
        TO ? (FORMAT PARQUET, CODEC 'ZSTD');
    """, [LINK_OUT])

    log(f"OK écrit: {LINK_OUT}")

    # 5) Preuve Gold case : Croix Rouge (doit sortir avec un RNA non nul)
    # Le sujet insiste sur ce test.
    # Note: l’ID attendu dans l’énoncé est W751000060 (à vérifier selon millésime RNA).
    gold = con.execute("""
        SELECT * FROM link_final WHERE siret = '77567227200020';
    """).fetchall()
    log(f"GOLD CHECK (77567227200020): {gold}")

    con.close()
    log("DONE match")

if __name__ == "__main__":
    main()