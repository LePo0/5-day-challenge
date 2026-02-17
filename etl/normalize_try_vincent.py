# etl/normalize.py
import os
from datetime import datetime
import duckdb

PARQUET_DIR = "data_parquet"
DUCKDB_DIR = "duckdb"
DB_PATH = os.path.join(DUCKDB_DIR, "catalog.db")

SIRENE_BRONZE = os.path.join(PARQUET_DIR, "sirene.parquet")
RNA_BRONZE    = os.path.join(PARQUET_DIR, "rna.parquet")
BAN_BRONZE    = os.path.join(PARQUET_DIR, "ban.parquet")

SIRENE_SILVER = os.path.join(PARQUET_DIR, "sirene_silver.parquet")
RNA_SILVER    = os.path.join(PARQUET_DIR, "rna_silver.parquet")
BAN_SILVER    = os.path.join(PARQUET_DIR, "ban_silver.parquet")

os.makedirs(PARQUET_DIR, exist_ok=True)
os.makedirs(DUCKDB_DIR, exist_ok=True)

# ---------------------------
# MODE DEV / PROD
# ---------------------------
# DEV=1 -> sample + pas de ZSTD + outputs en .tmp (plus rapide à itérer)
DEV = os.getenv("DEV", "0") == "1"
# % de sample en DEV (ex: 1 = 1%)
DEV_SAMPLE_PCT = int(os.getenv("DEV_SAMPLE_PCT", "1"))
# LIMIT alternative (0 = désactivé)
DEV_LIMIT = int(os.getenv("DEV_LIMIT", "0"))

# Compression: en PROD ZSTD (plus compact), en DEV souvent sans codec
PROD_CODEC = os.getenv("PROD_CODEC", "ZSTD")  # ZSTD, SNAPPY, GZIP, ou vide
THREADS = int(os.getenv("DUCKDB_THREADS", "8"))
MEMORY_LIMIT = os.getenv("DUCKDB_MEMORY_LIMIT", "4GB")

def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def ensure_db_ok() -> None:
    """Auto-répare un catalog.db invalide."""
    if os.path.exists(DB_PATH):
        try:
            t = duckdb.connect(DB_PATH)
            t.close()
        except Exception:
            os.remove(DB_PATH)

def out_opts() -> str:
    """Options Parquet selon DEV/PROD."""
    if DEV:
        return "(FORMAT PARQUET)"  # plus rapide en dev
    if PROD_CODEC:
        return f"(FORMAT PARQUET, CODEC '{PROD_CODEC}')"
    return "(FORMAT PARQUET)"

def source_expr(path: str) -> str:
    """Source FROM selon DEV/PROD."""
    if not DEV:
        return f"'{path}'"
    # DEV: soit LIMIT, soit SAMPLE (SAMPLE est souvent plus représentatif)
    if DEV_LIMIT > 0:
        return f"(SELECT * FROM '{path}' LIMIT {DEV_LIMIT})"
    return f"'{path}' USING SAMPLE {DEV_SAMPLE_PCT} PERCENT"

def atomic_replace(tmp_path: str, final_path: str) -> None:
    """Remplace atomiquement (Windows-friendly)."""
    if os.path.exists(tmp_path):
        os.replace(tmp_path, final_path)

def register_macros(con: duckdb.DuckDBPyConnection) -> None:
    """
    Macros SQL DuckDB: beaucoup plus rapides que les UDF Python.
    - norm_txt: upper + suppression ponctuation + collapse spaces
    - norm_street: norm_txt + mapping abréviations "type voie"
    """
    con.execute(r"""
    CREATE OR REPLACE MACRO norm_txt(x) AS (
      TRIM(
        REGEXP_REPLACE(
          REGEXP_REPLACE(
            UPPER(COALESCE(x, '')),
            '[^A-Z0-9 ]+', ' ', 'g'
          ),
          '\s+', ' ', 'g'
        )
      )
    );
    """)
    
    con.execute(r"""
    CREATE OR REPLACE MACRO norm_street(x) AS (
      TRIM(
        REGEXP_REPLACE(
          REGEXP_REPLACE(
            REGEXP_REPLACE(
              REGEXP_REPLACE(
                REGEXP_REPLACE(
                  REGEXP_REPLACE(
                    REGEXP_REPLACE(
                      REGEXP_REPLACE(
                        REGEXP_REPLACE(
                          REGEXP_REPLACE(
                            REGEXP_REPLACE(
                              REGEXP_REPLACE(
                                norm_txt(x),
                                '\bSTE\b', 'SAINTE', 'g'
                              ),
                              '\bST\b', 'SAINT', 'g'
                            ),
                            '\bAVEN\b|\bAVE\b|\bAV\b', 'AVENUE', 'g'
                          ),
                          '\bBLVD\b|\bBD\b', 'BOULEVARD', 'g'
                        ),
                        '\bRTE\b|\bRT\b', 'ROUTE', 'g'
                      ),
                      '\bCHEM\b|\bCHE\b', 'CHEMIN', 'g'
                    ),
                    '\bIMP\b', 'IMPASSE', 'g'
                  ),
                  '\bPL\b', 'PLACE', 'g'
                ),
                '\bALL\b', 'ALLEE', 'g'
              ),
              '\bCRS\b', 'COURS', 'g'
            ),
            '\bSQ\b', 'SQUARE', 'g'
          ),
          '\s+', ' ', 'g'
        )
      )
    );
    """)

def normalize_sirene(con: duckdb.DuckDBPyConnection) -> None:
    log("NORMALIZE SIRENE -> sirene_silver.parquet")
    if not os.path.exists(SIRENE_BRONZE):
        raise FileNotFoundError(f"Manquant: {SIRENE_BRONZE}")

    src = source_expr(SIRENE_BRONZE)
    out_final = SIRENE_SILVER
    out_tmp = out_final + ".tmp"
    opts = out_opts()

    # Important: éviter de polluer la rue avec type_voie=[ND] ou valeurs bizarres
    # On trim + NULLIF pour supprimer '[ND]' et les vides.
    con.execute(f"""
        COPY (
            SELECT
                siret,
                siren,
                nom,
                enseigne,
                naf,
                etat,
                code_postal,
                num_voie AS numero,
                trim(type_voie) AS type_voie,
                libelle_voie,
                ville,

                norm_txt(concat_ws(' ', nom, enseigne)) AS name_norm,

                norm_street(
                  concat_ws(' ',
                    NULLIF(trim(type_voie), '[ND]'),
                    libelle_voie
                  )
                ) AS street_norm,

                norm_txt(ville) AS city_norm,

                substr(norm_txt(concat_ws(' ', nom, enseigne)), 1, 10) AS block_key
            FROM {src}
        )
        TO '{out_tmp}' {opts};
    """)
    atomic_replace(out_tmp, out_final)
    log("OK SIRENE silver écrit")

def normalize_rna(con: duckdb.DuckDBPyConnection) -> None:
    log("NORMALIZE RNA -> rna_silver.parquet")
    if not os.path.exists(RNA_BRONZE):
        raise FileNotFoundError(f"Manquant: {RNA_BRONZE}")

    src = source_expr(RNA_BRONZE)
    out_final = RNA_SILVER
    out_tmp = out_final + ".tmp"
    opts = out_opts()

    con.execute(f"""
        COPY (
            SELECT
                id_rna,
                siret,
                titre_asso,
                code_postal,
                ville,
                objet,
                date_creat,

                norm_txt(titre_asso) AS title_norm,
                norm_txt(ville) AS city_norm,
                substr(norm_txt(titre_asso), 1, 10) AS block_key
            FROM {src}
        )
        TO '{out_tmp}' {opts};
    """)
    atomic_replace(out_tmp, out_final)
    log("OK RNA silver écrit")

def normalize_ban(con: duckdb.DuckDBPyConnection) -> None:
    log("NORMALIZE BAN -> ban_silver.parquet")
    if not os.path.exists(BAN_BRONZE):
        raise FileNotFoundError(f"Manquant: {BAN_BRONZE}")

    src = source_expr(BAN_BRONZE)
    out_final = BAN_SILVER
    out_tmp = out_final + ".tmp"
    opts = out_opts()

    con.execute(f"""
        COPY (
            SELECT
                id,
                code_postal,
                numero,
                rep,
                nom_voie,
                nom_commune,
                lat,
                lon,

                norm_street(nom_voie) AS street_norm,
                norm_txt(nom_commune) AS city_norm
            FROM {src}
            WHERE code_postal IS NOT NULL AND length(code_postal)=5
        )
        TO '{out_tmp}' {opts};
    """)
    atomic_replace(out_tmp, out_final)
    log("OK BAN silver écrit")

def quick_checks(con: duckdb.DuckDBPyConnection) -> None:
    log("CHECKS (counts)")
    for label, path in [
        ("SIRENE_SILVER", SIRENE_SILVER),
        ("RNA_SILVER", RNA_SILVER),
        ("BAN_SILVER", BAN_SILVER),
    ]:
        if not os.path.exists(path):
            log(f"{label}: fichier manquant ({path})")
            continue
        cnt = con.execute(f"SELECT count(*) FROM '{path}'").fetchone()[0]
        log(f"{label}: {cnt:,} lignes")

def main() -> None:
    ensure_db_ok()
    con = duckdb.connect(DB_PATH)

    con.execute(f"SET memory_limit='{MEMORY_LIMIT}';")
    con.execute(f"SET threads TO {THREADS};")
    con.execute("SET preserve_insertion_order=false;")
    con.execute("PRAGMA enable_progress_bar;")

    # PROD: macros (rapide)
    register_macros(con)

    normalize_sirene(con)
    normalize_rna(con)
    normalize_ban(con)
    quick_checks(con)

    con.close()
    log("DONE normalize")

if __name__ == "__main__":
    log(f"MODE={'DEV' if DEV else 'PROD'} threads={THREADS} mem={MEMORY_LIMIT} codec={('NONE' if DEV else PROD_CODEC)}")
    if DEV:
        log(f"DEV_SAMPLE_PCT={DEV_SAMPLE_PCT} DEV_LIMIT={DEV_LIMIT}")
    main()