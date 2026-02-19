# tests/check_normalization.py
import os
import sys
import duckdb
from datetime import datetime

PARQUET_DIR = "data_parquet"
DUCKDB_DIR = "duckdb"
DB_PATH = os.path.join(DUCKDB_DIR, "catalog.db")

SIRENE_BRONZE = os.path.join(PARQUET_DIR, "sirene.parquet")
RNA_BRONZE    = os.path.join(PARQUET_DIR, "rna.parquet")
BAN_BRONZE    = os.path.join(PARQUET_DIR, "ban.parquet")

SIRENE_SILVER = os.path.join(PARQUET_DIR, "sirene_silver.parquet")
RNA_SILVER    = os.path.join(PARQUET_DIR, "rna_silver.parquet")
BAN_SILVER    = os.path.join(PARQUET_DIR, "ban_silver.parquet")


# -----------------------------
# Seuils / règles
# -----------------------------
# Si True: on échoue si des tokens "abréviations interdites" restent
STRICT_FORBIDDEN_TOKENS = os.getenv("STRICT_FORBIDDEN_TOKENS", "1") == "1"

# Tolérance max (ratio) de tokens interdits avant échec (si strict=0)
FORBIDDEN_TOKEN_MAX_RATIO = float(os.getenv("FORBIDDEN_TOKEN_MAX_RATIO", "0.0001"))  # 0.01%

# Tolérance max de valeurs vides (street_norm/city_norm/name_norm)
EMPTY_MAX_RATIO = float(os.getenv("EMPTY_MAX_RATIO", "0.02"))  # 2%

# Top N mots courts à afficher
TOP_SHORT_WORDS_N = int(os.getenv("TOP_SHORT_WORDS_N", "80"))

FORBIDDEN_TOKENS = [
    "AV", "BD", "RTE", "CHE", "PL", "ALL", "SQ", "CRS", "RES", "LD", "LDT", "IMP", "ST", "STE", "AVEN", "AVE", "BLVD", "CHEM"
]


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def require_file(path: str) -> bool:
    if not os.path.exists(path):
        log(f"❌ Fichier manquant: {path}")
        return False
    return True


def q1(con: duckdb.DuckDBPyConnection, sql: str):
    return con.execute(sql).fetchone()[0]


def q_all(con: duckdb.DuckDBPyConnection, sql: str):
    return con.execute(sql).fetchall()


def percent(n: int, total: int) -> float:
    if total == 0:
        return 0.0
    return (n / total) * 100.0


def header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def check_counts(con, bronze_path: str, silver_path: str, label: str):
    header(f"{label} — COUNT bronze vs silver")
    bronze = q1(con, f"SELECT count(*) FROM '{bronze_path}'")
    silver = q1(con, f"SELECT count(*) FROM '{silver_path}'")
    print(f"bronze: {bronze:,}")
    print(f"silver: {silver:,}")
    ok = (bronze == silver)
    print("✅ OK" if ok else "❌ MISMATCH")
    return ok, bronze, silver


def check_allowed_chars(con, silver_path: str, cols: list[str], label: str):
    header(f"{label} — Caractères interdits (doit être 0)")
    where = " OR ".join([f"{c} ~ '[^A-Z0-9 ]'" for c in cols])
    bad = q1(con, f"SELECT count(*) FROM '{silver_path}' WHERE {where}")
    print(f"rows_with_bad_chars: {bad:,}")
    ok = (bad == 0)
    print("✅ OK" if ok else "❌ BAD CHARS FOUND")
    return ok, bad


def check_double_spaces(con, silver_path: str, cols: list[str], label: str):
    header(f"{label} — Doubles espaces (doit être 0)")
    where = " OR ".join([f"{c} LIKE '%  %'" for c in cols])
    bad = q1(con, f"SELECT count(*) FROM '{silver_path}' WHERE {where}")
    print(f"rows_with_double_spaces: {bad:,}")
    ok = (bad == 0)
    print("✅ OK" if ok else "❌ DOUBLE SPACES FOUND")
    return ok, bad


def check_empty(con, silver_path: str, col: str, label: str, total_rows: int, max_ratio: float):
    header(f"{label} — Valeurs vides pour {col}")
    empty = q1(con, f"SELECT count(*) FROM '{silver_path}' WHERE {col} IS NULL OR {col} = ''")
    ratio = (empty / total_rows) if total_rows else 0.0
    print(f"empty_{col}: {empty:,} / {total_rows:,} ({ratio*100:.4f}%)")
    ok = (ratio <= max_ratio)
    print("✅ OK" if ok else f"❌ TOO MANY EMPTY (>{max_ratio*100:.2f}%)")
    return ok, empty, ratio


def check_block_key(con, sirene_silver_path: str, total_rows: int):
    header("SIRENE — block_key sanity")
    empty = q1(con, f"SELECT count(*) FROM '{sirene_silver_path}' WHERE block_key IS NULL OR block_key = ''")
    badlen = q1(con, f"""
        SELECT count(*)
        FROM '{sirene_silver_path}'
        WHERE block_key IS NOT NULL
          AND block_key <> ''
          AND length(block_key) <> 10
    """)
    print(f"empty_block_key: {empty:,} / {total_rows:,} ({percent(empty,total_rows):.4f}%)")
    print(f"badlen_block_key: {badlen:,} / {total_rows:,} ({percent(badlen,total_rows):.4f}%)")
    ok = (badlen == 0)
    print("✅ OK" if ok else "❌ block_key length issues")
    # empty is not necessarily fatal, but we report it
    return ok, empty, badlen


def check_forbidden_tokens_in_street(con, sirene_silver_path: str, total_rows: int):
    header("SIRENE — Tokens interdits encore présents dans street_norm")
    # On cherche " mot " en padding pour éviter les faux positifs
    selects = []
    for t in FORBIDDEN_TOKENS:
        selects.append(f"sum(CASE WHEN (' ' || street_norm || ' ') LIKE '% {t} %' THEN 1 ELSE 0 END) AS has_{t.lower()}")
    sql = f"SELECT {', '.join(selects)} FROM '{sirene_silver_path}'"
    row = con.execute(sql).fetchone()

    # Affichage
    violations = []
    for i, t in enumerate(FORBIDDEN_TOKENS):
        cnt = int(row[i])
        if cnt > 0:
            violations.append((t, cnt, cnt/total_rows if total_rows else 0.0))

    if not violations:
        print("✅ Aucun token interdit détecté dans street_norm")
        return True, []

    # tri par volume
    violations.sort(key=lambda x: x[1], reverse=True)
    for t, cnt, r in violations[:30]:
        print(f"{t:>5}: {cnt:,} lignes ({r*100:.4f}%)")

    if STRICT_FORBIDDEN_TOKENS:
        print("❌ STRICT_FORBIDDEN_TOKENS=1 => échec si un token interdit reste.")
        return False, violations
    else:
        worst = max(v[2] for v in violations)
        ok = worst <= FORBIDDEN_TOKEN_MAX_RATIO
        print(f"Max ratio interdit observé: {worst*100:.4f}% (seuil {FORBIDDEN_TOKEN_MAX_RATIO*100:.4f}%)")
        print("✅ OK" if ok else "❌ Too many forbidden tokens")
        return ok, violations


def top_short_words(con, sirene_silver_path: str):
    header(f"SIRENE — Top {TOP_SHORT_WORDS_N} mots courts (1..4) dans street_norm")
    rows = q_all(con, f"""
        WITH words AS (
          SELECT unnest(string_split(street_norm, ' ')) AS w
          FROM '{sirene_silver_path}'
        )
        SELECT w, count(*) AS nb
        FROM words
        WHERE length(w) BETWEEN 1 AND 4
        GROUP BY 1
        ORDER BY nb DESC
        LIMIT {TOP_SHORT_WORDS_N}
    """)
    for w, nb in rows:
        print(f"{str(w):>6}  {int(nb):,}")
    return rows


def main() -> int:
    ok_all = True

    # fichiers attendus
    required = [
        DB_PATH,
        SIRENE_BRONZE, RNA_BRONZE, BAN_BRONZE,
        SIRENE_SILVER, RNA_SILVER, BAN_SILVER,
    ]
    for p in required:
        if not require_file(p):
            return 2

    con = duckdb.connect(DB_PATH, read_only=True)

    # --- Counts ---
    ok, _, sirene_rows = check_counts(con, SIRENE_BRONZE, SIRENE_SILVER, "SIRENE")
    ok_all &= ok
    ok, _, rna_rows = check_counts(con, RNA_BRONZE, RNA_SILVER, "RNA")
    ok_all &= ok
    ok, _, ban_rows = check_counts(con, BAN_BRONZE, BAN_SILVER, "BAN")
    ok_all &= ok

    # --- Format invariants ---
    ok, _ = check_allowed_chars(con, SIRENE_SILVER, ["name_norm", "street_norm", "city_norm"], "SIRENE")
    ok_all &= ok
    ok, _ = check_double_spaces(con, SIRENE_SILVER, ["name_norm", "street_norm", "city_norm"], "SIRENE")
    ok_all &= ok

    ok, _ = check_allowed_chars(con, RNA_SILVER, ["title_norm", "city_norm"], "RNA")
    ok_all &= ok
    ok, _ = check_double_spaces(con, RNA_SILVER, ["title_norm", "city_norm"], "RNA")
    ok_all &= ok

    ok, _ = check_allowed_chars(con, BAN_SILVER, ["street_norm", "city_norm"], "BAN")
    ok_all &= ok
    ok, _ = check_double_spaces(con, BAN_SILVER, ["street_norm", "city_norm"], "BAN")
    ok_all &= ok

    # --- Empty checks (tolérances) ---
    ok, _, _ = check_empty(con, SIRENE_SILVER, "name_norm", "SIRENE", sirene_rows, EMPTY_MAX_RATIO)
    ok_all &= ok
    ok, _, _ = check_empty(con, SIRENE_SILVER, "street_norm", "SIRENE", sirene_rows, EMPTY_MAX_RATIO)
    ok_all &= ok
    ok, _, _ = check_empty(con, SIRENE_SILVER, "city_norm", "SIRENE", sirene_rows, EMPTY_MAX_RATIO)
    ok_all &= ok

    ok, _, _ = check_empty(con, RNA_SILVER, "title_norm", "RNA", rna_rows, EMPTY_MAX_RATIO)
    ok_all &= ok
    ok, _, _ = check_empty(con, RNA_SILVER, "city_norm", "RNA", rna_rows, EMPTY_MAX_RATIO)
    ok_all &= ok

    ok, _, _ = check_empty(con, BAN_SILVER, "street_norm", "BAN", ban_rows, EMPTY_MAX_RATIO)
    ok_all &= ok
    ok, _, _ = check_empty(con, BAN_SILVER, "city_norm", "BAN", ban_rows, EMPTY_MAX_RATIO)
    ok_all &= ok

    # --- SIRENE block_key ---
    ok, _, _ = check_block_key(con, SIRENE_SILVER, sirene_rows)
    ok_all &= ok

    # --- Forbidden tokens ---
    ok, _ = check_forbidden_tokens_in_street(con, SIRENE_SILVER, sirene_rows)
    ok_all &= ok

    # --- Diagnostics: top short words ---
    top_short_words(con, SIRENE_SILVER)

    con.close()

    header("RÉSULTAT GLOBAL")
    if ok_all:
        print("✅ Tous les checks critiques sont OK.")
        return 0
    else:
        print("❌ Certains checks critiques ont échoué.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
