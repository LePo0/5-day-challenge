# tests/ban_verify.py
import os
import sys
from datetime import datetime
import duckdb

PARQUET_DIR = "data_parquet"
BAN_BRONZE = os.path.join(PARQUET_DIR, "ban.parquet")
BAN_SILVER = os.path.join(PARQUET_DIR, "ban_silver.parquet")
BAN_ANOMALIES = os.path.join(PARQUET_DIR, "ban_anomalies.parquet")

# Thresholds (override via env vars)
# NOTE: 10 est beaucoup trop bas pour la BAN. Mets 50+ en pratique.
MAX_COMMUNES_PER_CP = int(os.getenv("BAN_MAX_COMMUNES_PER_CP", "50"))
MAX_CPS_PER_COMMUNE = int(os.getenv("BAN_MAX_CPS_PER_COMMUNE", "50"))

# Export anomalies policy
WRITE_ANOMALIES = os.getenv("BAN_WRITE_ANOMALIES", "1") == "1"
# If 1 -> write only strong outliers (recommended)
ANOMALIES_STRICT = os.getenv("BAN_ANOMALIES_STRICT", "1") == "1"

STRICT = os.getenv("BAN_STRICT", "0") == "1"


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def die(msg: str, code: int = 1) -> None:
    log(msg)
    sys.exit(code)


def must_exist(path: str) -> None:
    if not os.path.exists(path):
        die(f"Fichier manquant: {path}")


def has_func(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    try:
        con.execute(f"SELECT {name}('A')").fetchone()
        return True
    except Exception:
        return False


def main() -> None:
    must_exist(BAN_BRONZE)
    must_exist(BAN_SILVER)

    con = duckdb.connect()  # in-memory

    log("BAN VERIFY — start")
    log(
        "thresholds: "
        f"MAX_COMMUNES_PER_CP={MAX_COMMUNES_PER_CP} "
        f"MAX_CPS_PER_COMMUNE={MAX_CPS_PER_COMMUNE} "
        f"STRICT={1 if STRICT else 0} "
        f"ANOMALIES_STRICT={1 if ANOMALIES_STRICT else 0}"
    )

    # ------------------------------------------------------------------
    # 1) COUNT bronze vs silver (silver filtre CP null & len=5)
    # ------------------------------------------------------------------
    bronze_total = con.execute(f"SELECT count(*) FROM '{BAN_BRONZE}'").fetchone()[0]
    bronze_kept = con.execute(
        f"""
        SELECT count(*)
        FROM '{BAN_BRONZE}'
        WHERE code_postal IS NOT NULL AND length(code_postal)=5
        """
    ).fetchone()[0]
    silver_total = con.execute(f"SELECT count(*) FROM '{BAN_SILVER}'").fetchone()[0]

    log("COUNT")
    log(f"  bronze_total: {bronze_total:,}")
    log(f"  bronze_kept (cp not null & len=5): {bronze_kept:,}")
    log(f"  silver_total: {silver_total:,}")

    if silver_total != bronze_kept:
        log("MISMATCH: silver != bronze_kept")
        if STRICT:
            die("STRICT=1 => arrêt sur mismatch count")
    else:
        log("OK: silver == bronze_kept")

    # ------------------------------------------------------------------
    # 2) Colonnes requises
    # ------------------------------------------------------------------
    cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM '{BAN_SILVER}'").fetchall()]
    required = {
        "id",
        "code_postal",
        "numero",
        "rep",
        "nom_voie",
        "nom_commune",
        "lat",
        "lon",
        "street_norm",
        "city_norm",
        "type_voie_norm",
        "libelle_voie_norm",
    }
    missing = sorted(required.difference(set(cols)))
    log("COLUMNS")
    if missing:
        log(f"colonnes manquantes: {missing}")
        if STRICT:
            die("STRICT=1 => colonnes requises manquantes")
    else:
        log("OK")

    # ------------------------------------------------------------------
    # 3) Standardisation
    #
    # Problème dans ta v1:
    # - regexp_matches(street_norm, '[^A-Z0-9 ]') donne des résultats surprenants selon versions
    #
    # On fait des checks robustes :
    # - FULL match: ^[A-Z0-9 ]*$ (si fonction dispo)
    # - double spaces: LIKE '%  %'
    # - NBSP/espaces invisibles: contains chr(160)
    # ------------------------------------------------------------------
    log("STANDARDISATION")

    use_full = has_func(con, "regexp_full_match")

    if use_full:
        bad_chars_street = con.execute(
            f"""
            SELECT count(*)
            FROM '{BAN_SILVER}'
            WHERE street_norm IS NOT NULL
              AND NOT regexp_full_match(street_norm, '^[A-Z0-9 ]*$')
            """
        ).fetchone()[0]
        bad_chars_city = con.execute(
            f"""
            SELECT count(*)
            FROM '{BAN_SILVER}'
            WHERE city_norm IS NOT NULL
              AND NOT regexp_full_match(city_norm, '^[A-Z0-9 ]*$')
            """
        ).fetchone()[0]
    else:
        # fallback
        bad_chars_street = con.execute(
            f"""
            SELECT count(*)
            FROM '{BAN_SILVER}'
            WHERE street_norm IS NOT NULL
              AND regexp_matches(street_norm, '[^A-Z0-9 ]')
            """
        ).fetchone()[0]
        bad_chars_city = con.execute(
            f"""
            SELECT count(*)
            FROM '{BAN_SILVER}'
            WHERE city_norm IS NOT NULL
              AND regexp_matches(city_norm, '[^A-Z0-9 ]')
            """
        ).fetchone()[0]

    double_spaces_street = con.execute(
        f"SELECT count(*) FROM '{BAN_SILVER}' WHERE street_norm LIKE '%  %'"
    ).fetchone()[0]
    double_spaces_city = con.execute(
        f"SELECT count(*) FROM '{BAN_SILVER}' WHERE city_norm LIKE '%  %'"
    ).fetchone()[0]

    # NBSP check (souvent cause d’anomalies "fantômes")
    nbsp_street = con.execute(
        f"""
        SELECT count(*)
        FROM '{BAN_SILVER}'
        WHERE street_norm LIKE '%' || chr(160) || '%'
        """
    ).fetchone()[0]
    nbsp_city = con.execute(
        f"""
        SELECT count(*)
        FROM '{BAN_SILVER}'
        WHERE city_norm LIKE '%' || chr(160) || '%'
        """
    ).fetchone()[0]

    log(f"  street_norm bad chars: {bad_chars_street:,}")
    log(f"  city_norm   bad chars: {bad_chars_city:,}")
    log(f"  street_norm double spaces: {double_spaces_street:,}")
    log(f"  city_norm   double spaces: {double_spaces_city:,}")
    log(f"  street_norm contains NBSP: {nbsp_street:,}")
    log(f"  city_norm   contains NBSP: {nbsp_city:,}")

    if STRICT and (bad_chars_street or bad_chars_city or double_spaces_street or double_spaces_city or nbsp_street or nbsp_city):
        die("STRICT=1 => échec standardisation")

    # ------------------------------------------------------------------
    # 4) Tokenisation/parsing
    # ------------------------------------------------------------------
    log("TOKENISATION")
    empty_type = con.execute(
        f"""
        SELECT count(*)
        FROM '{BAN_SILVER}'
        WHERE type_voie_norm IS NULL OR trim(type_voie_norm) = ''
        """
    ).fetchone()[0]
    empty_lib = con.execute(
        f"""
        SELECT count(*)
        FROM '{BAN_SILVER}'
        WHERE libelle_voie_norm IS NULL OR trim(libelle_voie_norm) = ''
        """
    ).fetchone()[0]
    log(f"  empty type_voie_norm: {empty_type:,} / {silver_total:,} ({(empty_type/silver_total*100):.4f}%)")
    log(f"  empty libelle_voie_norm: {empty_lib:,} / {silver_total:,} ({(empty_lib/silver_total*100):.4f}%)")

    # ------------------------------------------------------------------
    # 5) Validité CP <-> commune (heuristique robuste)
    #
    # Le fait que certains CP aient 30-50 communes n’est pas rare (communes déléguées,
    # zones rurales, réorganisations, etc.). On sort:
    # - distribution (min/median/p95/p99/max)
    # - top outliers
    # - anomalies: CP au-dessus du seuil (par défaut 50)
    # ------------------------------------------------------------------
    log("CP <-> COMMUNE (HEURISTIC)")

    stats = con.execute(
        f"""
        WITH x AS (
          SELECT code_postal, count(DISTINCT city_norm) AS nb_communes
          FROM '{BAN_SILVER}'
          GROUP BY 1
        )
        SELECT
          min(nb_communes),
          approx_quantile(nb_communes, 0.50),
          approx_quantile(nb_communes, 0.95),
          approx_quantile(nb_communes, 0.99),
          max(nb_communes)
        FROM x
        """
    ).fetchone()

    log(f"  nb_communes_per_cp: min={stats[0]} median~={stats[1]} p95~={stats[2]} p99~={stats[3]} max={stats[4]}")

    outlier_cp_count = con.execute(
        f"""
        SELECT count(*)
        FROM (
          SELECT code_postal
          FROM '{BAN_SILVER}'
          GROUP BY 1
          HAVING count(DISTINCT city_norm) > {MAX_COMMUNES_PER_CP}
        )
        """
    ).fetchone()[0]
    log(f"  CP with >{MAX_COMMUNES_PER_CP} communes: {outlier_cp_count:,}")

    log("  Top 20 CP -> nb communes")
    top_cp = con.execute(
        f"""
        SELECT code_postal, count(DISTINCT city_norm) AS nb_communes
        FROM '{BAN_SILVER}'
        GROUP BY 1
        ORDER BY nb_communes DESC
        LIMIT 20
        """
    ).fetchall()
    for cp, n in top_cp:
        log(f"    {cp}: {n}")

    # Commune -> nb CP
    log("  Top 20 commune -> nb CP")
    top_city = con.execute(
        f"""
        SELECT city_norm, count(DISTINCT code_postal) AS nb_cps
        FROM '{BAN_SILVER}'
        GROUP BY 1
        ORDER BY nb_cps DESC
        LIMIT 20
        """
    ).fetchall()
    for city, n in top_city:
        log(f"    {city}: {n}")

    # ------------------------------------------------------------------
    # 6) Geo sanity
    # ------------------------------------------------------------------
    log("GEO SANITY")
    bad_geo = con.execute(
        f"""
        SELECT count(*)
        FROM '{BAN_SILVER}'
        WHERE lat IS NULL OR lon IS NULL
           OR lat < -90 OR lat > 90
           OR lon < -180 OR lon > 180
        """
    ).fetchone()[0]
    log(f"  bad_geo_rows: {bad_geo:,}")
    if STRICT and bad_geo:
        die("STRICT=1 => échec geo sanity")

    # ------------------------------------------------------------------
    # 7) Export anomalies (plus intelligent)
    #
    # Ta v1 sortait 5.8M lignes parce que seuil trop bas.
    # Ici:
    # - on exporte CP outliers (seuil env)
    # - + geo outliers
    # - + optionnel: (ANOMALIES_STRICT=0) inclure aussi les communes outliers
    # ------------------------------------------------------------------
    if WRITE_ANOMALIES:
        log(f"WRITE anomalies -> {BAN_ANOMALIES}")
        tmp = BAN_ANOMALIES + ".tmp"

        where_extra = ""
        if not ANOMALIES_STRICT:
            where_extra = f"""
            OR (b.city_norm IN (
                SELECT city_norm
                FROM '{BAN_SILVER}'
                GROUP BY 1
                HAVING count(DISTINCT code_postal) > {MAX_CPS_PER_COMMUNE}
            ))
            """

        con.execute(
            f"""
            COPY (
              WITH cp_outliers AS (
                SELECT code_postal
                FROM '{BAN_SILVER}'
                GROUP BY 1
                HAVING count(DISTINCT city_norm) > {MAX_COMMUNES_PER_CP}
              )
              SELECT
                b.*,
                (b.code_postal IN (SELECT code_postal FROM cp_outliers)) AS is_cp_outlier,
                (
                  b.lat IS NULL OR b.lon IS NULL
                  OR b.lat < -90 OR b.lat > 90
                  OR b.lon < -180 OR b.lon > 180
                ) AS is_geo_outlier
              FROM '{BAN_SILVER}' b
              WHERE
                (b.code_postal IN (SELECT code_postal FROM cp_outliers))
                OR (
                  b.lat IS NULL OR b.lon IS NULL
                  OR b.lat < -90 OR b.lat > 90
                  OR b.lon < -180 OR b.lon > 180
                )
                {where_extra}
            )
            TO '{tmp}' (FORMAT PARQUET, CODEC 'ZSTD');
            """
        )
        os.replace(tmp, BAN_ANOMALIES)
        n_anom = con.execute(f"SELECT count(*) FROM '{BAN_ANOMALIES}'").fetchone()[0]
        log(f"  anomalies rows: {n_anom:,}")

    log("BAN VERIFY — done ✅")
    con.close()


if __name__ == "__main__":
    main()