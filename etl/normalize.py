# etl/normalize.py
import os
from datetime import datetime
import duckdb

PARQUET_DIR = "data_parquet"
DUCKDB_DIR = "duckdb"
DB_PATH = os.path.join(DUCKDB_DIR, "catalog.db")

SIRENE_BRONZE = os.path.join(PARQUET_DIR, "sirene.parquet")
RNA_BRONZE = os.path.join(PARQUET_DIR, "rna.parquet")
BAN_BRONZE = os.path.join(PARQUET_DIR, "ban.parquet")

SIRENE_SILVER = os.path.join(PARQUET_DIR, "sirene_silver.parquet")
RNA_SILVER = os.path.join(PARQUET_DIR, "rna_silver.parquet")
BAN_SILVER = os.path.join(PARQUET_DIR, "ban_silver.parquet")

# Optional: anomaly outputs (BAN quality)
BAN_ANOMALIES = os.path.join(PARQUET_DIR, "ban_anomalies.parquet")

os.makedirs(PARQUET_DIR, exist_ok=True)
os.makedirs(DUCKDB_DIR, exist_ok=True)

# ---------------------------
# MODE DEV / PROD
# ---------------------------
DEV = os.getenv("DEV", "0") == "1"
DEV_SAMPLE_PCT = int(os.getenv("DEV_SAMPLE_PCT", "1"))
DEV_LIMIT = int(os.getenv("DEV_LIMIT", "0"))

PROD_CODEC = os.getenv("PROD_CODEC", "ZSTD")  # ZSTD / SNAPPY / GZIP / "" (none)
THREADS = int(os.getenv("DUCKDB_THREADS", "8"))
MEMORY_LIMIT = os.getenv("DUCKDB_MEMORY_LIMIT", "8GB")

# ---------------------------
# BAN checks tuning
# ---------------------------
# If a CP is associated with too many communes, we flag it.
BAN_MAX_COMMUNES_PER_CP = int(os.getenv("BAN_MAX_COMMUNES_PER_CP", "10"))
# If a commune is associated with too many CPs, we flag it.
BAN_MAX_CPS_PER_COMMUNE = int(os.getenv("BAN_MAX_CPS_PER_COMMUNE", "20"))
# Write anomalies parquet (1=yes, 0=no)
BAN_WRITE_ANOMALIES = os.getenv("BAN_WRITE_ANOMALIES", "1") == "1"


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
    if DEV_LIMIT > 0:
        return f"(SELECT * FROM '{path}' LIMIT {DEV_LIMIT})"
    return f"'{path}' USING SAMPLE {DEV_SAMPLE_PCT} PERCENT"


def atomic_replace(tmp_path: str, final_path: str) -> None:
    """Remplace atomiquement (Windows-friendly)."""
    if os.path.exists(tmp_path):
        os.replace(tmp_path, final_path)


def register_macros(con: duckdb.DuckDBPyConnection) -> None:
    """
    Macros SQL ultra compatibles:
    - Pas de \\b / \\s
    - Mapping par mot entier via padding d'espaces
    - Suppression explicite de [ND] et variantes (ND], ND)
    - Normalisation NBSP (chr(160)) -> ' '
    - Collapse final des espaces (2 passes)
    - Fallback si strip_accents() n'existe pas

    + BAN parsing:
    - ban_type(street_norm): extrait un type_voie standardisé (heuristique, long->court)
    - ban_libelle(street_norm): extrait le libellé sans type_voie
    """

    def _create(with_strip_accents: bool) -> None:
        base = (
            "upper(strip_accents(CAST(COALESCE(x, '') AS VARCHAR)))"
            if with_strip_accents
            else "upper(CAST(COALESCE(x, '') AS VARCHAR))"
        )

        con.execute(
            f"""
CREATE OR REPLACE MACRO norm_txt(x) AS (
    trim(
        regexp_replace(
            regexp_replace(
                regexp_replace(
                    -- base -> keep only A-Z0-9 + spaces, convert NBSP to space
                    replace(
                        regexp_replace(
                            {base},
                            '[^A-Z0-9 ]+',
                            ' '
                        ),
                        chr(160),
                        ' '
                    ),
                    -- collapse spaces (2 passes for robustness)
                    ' +',
                    ' '
                ),
                ' +',
                ' '
            ),
            -- final safety (should already be clean, but keeps it bulletproof)
            '[^A-Z0-9 ]+',
            ' '
        )
    )
);

-- remove [ND] and common ND variants AFTER normalization
CREATE OR REPLACE MACRO kill_nd(x) AS (
    trim(
        replace(
            replace(
                replace(
                    ' ' || x || ' ',
                    ' [ND] ',
                    ' '
                ),
                ' ND] ',
                ' '
            ),
            ' ND ',
            ' '
        )
    )
);

CREATE OR REPLACE MACRO norm_street(x) AS (
    trim(
        regexp_replace(
            regexp_replace(
                (
                    regexp_replace(
                        regexp_replace(
                            regexp_replace(
                                regexp_replace(
                                    regexp_replace(
                                        regexp_replace(
                                            regexp_replace(
                                                regexp_replace(
                                                    regexp_replace(
                                                        regexp_replace(
                                                            regexp_replace(
                                                                regexp_replace(
                                                                    regexp_replace(
                                                                        regexp_replace(
                                                                            regexp_replace(
                                                                                regexp_replace(
                                                                                    regexp_replace(
                                                                                        regexp_replace(
                                                                                            regexp_replace(
                                                                                                regexp_replace(
                                                                                                    regexp_replace(
                                                                                                        -- pad with spaces to match whole tokens
                                                                                                        ' ' || kill_nd(norm_txt(x)) || ' ',

                                                                                                        ' STE ',  ' SAINTE '
                                                                                                    ),
                                                                                                    ' ST ',   ' SAINT '
                                                                                                ),
                                                                                                ' AVEN ', ' AVENUE '
                                                                                            ),
                                                                                            ' AVE ',  ' AVENUE '
                                                                                        ),
                                                                                        ' AV ',   ' AVENUE '
                                                                                    ),
                                                                                    ' BLVD ', ' BOULEVARD '
                                                                                ),
                                                                                ' BD ',   ' BOULEVARD '
                                                                            ),
                                                                            ' RTE ',  ' ROUTE '
                                                                        ),
                                                                        ' CHEM ', ' CHEMIN '
                                                                    ),
                                                                    ' CHE ',  ' CHEMIN '
                                                                ),
                                                                ' IMP ',  ' IMPASSE '
                                                            ),
                                                            ' PL ',   ' PLACE '
                                                        ),
                                                        ' ALL ',  ' ALLEE '
                                                    ),
                                                    ' CRS ',  ' COURS '
                                                ),
                                                ' SQ ',   ' SQUARE '
                                            ),
                                            ' RES ',  ' RESIDENCE '
                                        ),
                                        ' LDT ',  ' LIEU DIT '
                                    ),
                                    ' LD ',   ' LIEU DIT '
                                ),
                                ' RLE ',  ' RUELLE '
                            ),
                            ' MTE ',  ' MONTEE '
                        ),
                        ' FG ',   ' FAUBOURG '
                    )
                ),
                -- collapse spaces after replacements (2 passes)
                ' +',
                ' '
            ),
            ' +',
            ' '
        )
    )
);

-- ---------------------------
-- BAN parsing (heuristique)
-- ---------------------------

-- Extract a standardized "type de voie" from street_norm.
-- Order matters: longer/multiword prefixes first.
CREATE OR REPLACE MACRO ban_type(s) AS (
    CASE
        WHEN s IS NULL OR s = '' THEN NULL

        WHEN s LIKE 'LIEU DIT %' THEN 'LIEU DIT'
        WHEN s LIKE 'GRANDE RUE %' THEN 'GRANDE RUE'
        WHEN s LIKE 'PETITE RUE %' THEN 'PETITE RUE'
        WHEN s LIKE 'ANCIEN CHEMIN %' THEN 'ANCIEN CHEMIN'
        WHEN s LIKE 'ANCIENNE ROUTE %' THEN 'ANCIENNE ROUTE'
        WHEN s LIKE 'VIEUX CHEMIN %' THEN 'VIEUX CHEMIN'
        WHEN s LIKE 'VIEILLE ROUTE %' THEN 'VIEILLE ROUTE'
        WHEN s LIKE 'ROND POINT %' THEN 'ROND POINT'
        WHEN s LIKE 'ROND-POINT %' THEN 'ROND-POINT'
        WHEN s LIKE 'ZONE INDUSTRIELLE %' THEN 'ZONE INDUSTRIELLE'
        WHEN s LIKE 'ZONE ARTISANALE %' THEN 'ZONE ARTISANALE'

        -- single-token common types
        WHEN split_part(s, ' ', 1) IN (
            'RUE','AVENUE','BOULEVARD','ROUTE','CHEMIN','IMPASSE','PLACE','ALLEE',
            'COURS','QUAI','SQUARE','RESIDENCE','CITE','PASSAGE','HAM','HAMEAU',
            'TRAVERSE','VOIE','ZAC','DOMAINE','PARC','QUARTIER','ESPLANADE',
            'CHAUSSEE','COUR','CORNICHE','SENTIER','COTE','ZI','ZA','ZONE',
            'PORT','PLAN','GALERIE','PONT','TERRASSE','VILLAGE','VENELLE',
            'PARVIS','CHATEAU','POINTE','PORTE','FOND','ROCADE','CARREFOUR',
            'RAMPE','PLACETTE','MARCHE','DIGUE','REMPART','CONTOUR','CHAMP',
            'JARDIN','RAVINE','PLATEAU','CROIX','MARINA','ENCLOS','PLAINE',
            'DESCENTE','PLAGE','VALLON','VALLEE','CARRIERE','LEVEE','BOURG',
            'MAISON','DRAILLE','TOUR','ROC','GARE','BASSIN','VILLE','PROMENADE',
            'ESCALIER','LICES','PISTE','FONTAINE','FOSSE','ETANG','ARCADE',
            'AERODROME','AIRE','CANAL','AUTOROUTE','BRETELLE','TERTRE',
            'VOIRIE','HAUTEUR','BASE','PARKING','FORET','STADE','BERGE',
            'POSTE','ECART','RUISSEAU','CASERNE','TRABOULE','PORCHE','PHARE',
            'TUNNEL','MAS','HALLE','GREVE','DEVIATION','VIADUC','STATION',
            'HIPPODROME','MOULIN','CAMPING'
        )
        THEN split_part(s, ' ', 1)

        ELSE NULL
    END
);

-- Extract libellé (street without type prefix) from street_norm.
CREATE OR REPLACE MACRO ban_libelle(s) AS (
    CASE
        WHEN s IS NULL OR s = '' THEN NULL
        WHEN ban_type(s) IS NULL THEN s
        WHEN ban_type(s) IN ('LIEU DIT','GRANDE RUE','PETITE RUE','ANCIEN CHEMIN','ANCIENNE ROUTE','VIEUX CHEMIN','VIEILLE ROUTE','ROND POINT','ROND-POINT','ZONE INDUSTRIELLE','ZONE ARTISANALE')
            THEN trim(substr(s, length(ban_type(s)) + 2))
        ELSE
            trim(substr(s, length(ban_type(s)) + 2))
    END
);
"""
        )

    try:
        _create(with_strip_accents=True)
        log("MACROS: strip_accents OK")
    except Exception as e:
        log(
            f"MACROS: strip_accents indisponible ({type(e).__name__}), fallback sans accents"
        )
        _create(with_strip_accents=False)


def normalize_sirene(con: duckdb.DuckDBPyConnection) -> None:
    log("NORMALIZE SIRENE -> sirene_silver.parquet")
    if not os.path.exists(SIRENE_BRONZE):
        raise FileNotFoundError(f"Manquant: {SIRENE_BRONZE}")

    src = source_expr(SIRENE_BRONZE)
    out_final = SIRENE_SILVER
    out_tmp = out_final + ".tmp"
    opts = out_opts()

    con.execute(
        f"""
COPY (
    WITH base AS (
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
            -- Fallback explicite : nom → enseigne → ''
            COALESCE(
                NULLIF(trim(nom), ''),
                NULLIF(trim(enseigne), ''),
                ''
            ) AS nom_effectif,
            norm_street(
                concat_ws(
                    ' ',
                    num_voie,
                    NULLIF(trim(type_voie), '[ND]'),
                    libelle_voie
                )
            ) AS rue_normalisee
        FROM {src}
    )
    SELECT
        siret,
        siren,
        nom,
        enseigne,
        naf,
        etat,
        code_postal,
        numero,
        type_voie,
        libelle_voie,
        ville,

        norm_txt(nom_effectif) AS name_norm,
        rue_normalisee AS street_norm,
        norm_txt(ville) AS city_norm,
        
        -- Block key hybride :
        -- Si nom existe → substr(nom, 1, 10)
        -- Sinon → substr(rue, 1, 10) pour matching par adresse
        CASE
            WHEN length(norm_txt(nom_effectif)) > 0 
            THEN substr(norm_txt(nom_effectif), 1, 10)
            ELSE substr(rue_normalisee, 1, 10)
        END AS block_key
    FROM base
)
TO '{out_tmp}' {opts};
"""
    )
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

    con.execute(
        f"""
COPY (
    WITH base AS (
        SELECT
            id_rna,
            siret,
            titre_asso,
            code_postal,
            ville,
            objet,
            date_creat,
            num_voie,
            type_voie,
            libelle_voie,
            -- Normalisation adresse
            norm_street(
                concat_ws(
                    ' ',
                    num_voie,
                    NULLIF(trim(type_voie), ''),
                    libelle_voie
                )
            ) AS rue_normalisee
        FROM {src}
    )
    SELECT
        id_rna,
        siret,
        titre_asso,
        code_postal,
        ville,
        objet,
        date_creat,
        num_voie,
        type_voie,
        libelle_voie,

        norm_txt(titre_asso) AS title_norm,
        norm_txt(ville) AS city_norm,
        rue_normalisee AS street_norm,
        
        -- Block key hybride (comme SIRENE) :
        -- Si titre existe → substr(titre, 1, 10)
        -- Sinon → substr(rue, 1, 10) pour matching par adresse
        CASE
            WHEN length(norm_txt(titre_asso)) > 0 
            THEN substr(norm_txt(titre_asso), 1, 10)
            ELSE substr(rue_normalisee, 1, 10)
        END AS block_key
    FROM base
)
TO '{out_tmp}' {opts};
"""
    )
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

    # Focus BAN:
    # - tokenisation: numero/rep/cp/commune + street_norm
    # - parsing: type_voie_norm + libelle_voie_norm (heuristique)
    # - standardisation: norm_street/norm_txt
    # OPTIMISATION: CTE pour calculer norm_street() une seule fois au lieu de 3x
    con.execute(
        f"""
COPY (
    WITH normalized AS (
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
    SELECT
        id,
        code_postal,
        numero,
        rep,
        nom_voie,
        nom_commune,
        lat,
        lon,
        street_norm,
        city_norm,
        ban_type(street_norm) AS type_voie_norm,
        ban_libelle(street_norm) AS libelle_voie_norm
    FROM normalized
)
TO '{out_tmp}' {opts};
"""
    )
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


def ban_quality_checks(con: duckdb.DuckDBPyConnection) -> None:
    """
    Focus BAN quality:
    - format CP already enforced (5 digits) by WHERE
    - CP <-> commune coherence: flag outlier CPs mapped to many communes, and communes mapped to many CPs
    - geo sanity: lat/lon ranges
    - optional: write anomalies to data_parquet/ban_anomalies.parquet
    """
    if not os.path.exists(BAN_SILVER):
        log("BAN CHECKS: ban_silver.parquet manquant, skip")
        return

    log("BAN CHECKS: CP <-> commune + geo sanity")

    # 1) CP -> nb communes
    cps = con.execute(
        f"""
SELECT
    code_postal,
    count(DISTINCT city_norm) AS nb_communes
FROM '{BAN_SILVER}'
GROUP BY 1
ORDER BY nb_communes DESC
LIMIT 20
"""
    ).fetchall()

    # 2) Commune -> nb CP
    villes = con.execute(
        f"""
SELECT
    city_norm,
    count(DISTINCT code_postal) AS nb_cps
FROM '{BAN_SILVER}'
GROUP BY 1
ORDER BY nb_cps DESC
LIMIT 20
"""
    ).fetchall()

    # 3) lat/lon sanity (France + DROM/COM inclusive approx)
    # lat [-90,90], lon [-180,180] for absolute sanity
    bad_geo = con.execute(
        f"""
SELECT count(*) AS bad_geo
FROM '{BAN_SILVER}'
WHERE lat IS NULL OR lon IS NULL
   OR lat < -90 OR lat > 90
   OR lon < -180 OR lon > 180
"""
    ).fetchone()[0]

    # 4) How many outliers based on thresholds
    outlier_cp = con.execute(
        f"""
SELECT count(*) FROM (
    SELECT code_postal
    FROM '{BAN_SILVER}'
    GROUP BY 1
    HAVING count(DISTINCT city_norm) > {BAN_MAX_COMMUNES_PER_CP}
)
"""
    ).fetchone()[0]

    outlier_city = con.execute(
        f"""
SELECT count(*) FROM (
    SELECT city_norm
    FROM '{BAN_SILVER}'
    GROUP BY 1
    HAVING count(DISTINCT code_postal) > {BAN_MAX_CPS_PER_COMMUNE}
)
"""
    ).fetchone()[0]

    log(f"BAN: bad_geo_rows={bad_geo:,}")
    log(f"BAN: outlier_cps(>{BAN_MAX_COMMUNES_PER_CP} communes)= {outlier_cp:,}")
    log(f"BAN: outlier_communes(>{BAN_MAX_CPS_PER_COMMUNE} CPs)= {outlier_city:,}")

    log("BAN: Top CP -> nb communes (top20)")
    for cp, n in cps:
        log(f"  {cp}: {n}")

    log("BAN: Top commune -> nb CP (top20)")
    for city, n in villes:
        log(f"  {city}: {n}")

    # Optional: write anomalies (lightweight table)
    if BAN_WRITE_ANOMALIES:
        out_tmp = BAN_ANOMALIES + ".tmp"
        opts = out_opts()

        con.execute(
            f"""
COPY (
    WITH
    cp_outliers AS (
        SELECT code_postal
        FROM '{BAN_SILVER}'
        GROUP BY 1
        HAVING count(DISTINCT city_norm) > {BAN_MAX_COMMUNES_PER_CP}
    ),
    city_outliers AS (
        SELECT city_norm
        FROM '{BAN_SILVER}'
        GROUP BY 1
        HAVING count(DISTINCT code_postal) > {BAN_MAX_CPS_PER_COMMUNE}
    )
    SELECT
        b.*,
        (b.code_postal IN (SELECT code_postal FROM cp_outliers)) AS is_cp_outlier,
        (b.city_norm IN (SELECT city_norm FROM city_outliers)) AS is_city_outlier,
        (b.lat IS NULL OR b.lon IS NULL
            OR b.lat < -90 OR b.lat > 90
            OR b.lon < -180 OR b.lon > 180
        ) AS is_geo_outlier
    FROM '{BAN_SILVER}' b
    WHERE
        (b.code_postal IN (SELECT code_postal FROM cp_outliers))
        OR (b.city_norm IN (SELECT city_norm FROM city_outliers))
        OR (b.lat IS NULL OR b.lon IS NULL
            OR b.lat < -90 OR b.lat > 90
            OR b.lon < -180 OR b.lon > 180
        )
)
TO '{out_tmp}' {opts};
"""
        )
        atomic_replace(out_tmp, BAN_ANOMALIES)
        log(f"BAN CHECKS: anomalies écrites -> {BAN_ANOMALIES}")


def main() -> None:
    ensure_db_ok()
    con = duckdb.connect(DB_PATH)

    con.execute(f"SET memory_limit='{MEMORY_LIMIT}';")
    con.execute(f"SET threads TO {THREADS};")
    con.execute("SET preserve_insertion_order=false;")
    con.execute("PRAGMA enable_progress_bar;")

    register_macros(con)

    normalize_sirene(con)
    normalize_rna(con)
    normalize_ban(con)
    quick_checks(con)

    # Focus BAN: validity checks (CP <-> commune + geo)
    ban_quality_checks(con)

    con.close()
    log("DONE normalize")


if __name__ == "__main__":
    log(
        f"MODE={'DEV' if DEV else 'PROD'} threads={THREADS} mem={MEMORY_LIMIT} codec={('NONE' if DEV else PROD_CODEC)}"
    )
    if DEV:
        log(f"DEV_SAMPLE_PCT={DEV_SAMPLE_PCT} DEV_LIMIT={DEV_LIMIT}")
    log(
        f"BAN_CHECKS: MAX_COMMUNES_PER_CP={BAN_MAX_COMMUNES_PER_CP} "
        f"MAX_CPS_PER_COMMUNE={BAN_MAX_CPS_PER_COMMUNE} "
        f"WRITE_ANOMALIES={1 if BAN_WRITE_ANOMALIES else 0}"
    )
    main()