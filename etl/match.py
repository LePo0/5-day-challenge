# etl/match.py - VERSION STREAMING (sans explosion RAM)
import os
import duckdb
from datetime import datetime

PARQUET_DIR = "data_parquet"
DUCKDB_DIR = "duckdb"
DB_PATH = os.path.join(DUCKDB_DIR, "catalog.db")

SIRENE_SILVER = os.path.join(PARQUET_DIR, "sirene_silver.parquet")
RNA_SILVER = os.path.join(PARQUET_DIR, "rna_silver.parquet")
LINK_OUT = os.path.join(PARQUET_DIR, "link_sirene_rna.parquet")

os.makedirs(DUCKDB_DIR, exist_ok=True)

def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def main() -> None:
    if not os.path.exists(SIRENE_SILVER):
        raise FileNotFoundError(f"Manquant: {SIRENE_SILVER}")
    if not os.path.exists(RNA_SILVER):
        raise FileNotFoundError(f"Manquant: {RNA_SILVER}")

    con = duckdb.connect(DB_PATH)
    
    # Configuration optimale pour streaming
    con.execute("SET memory_limit='4GB';")  # Réduit (on stream)
    con.execute("SET threads TO 4;")  # Moins de threads = moins de RAM
    con.execute("SET preserve_insertion_order=false;")  # Économie RAM
    con.execute("SET temp_directory='./temp_duckdb';")
    con.execute("PRAGMA max_temp_directory_size='100GB';")

    log("MATCH SIRENE ↔ RNA : VERSION STREAMING (sans explosion RAM)")

    # =========================================================================
    # ÉTAPE 1 : EXACT MATCH (rapide, petite table)
    # =========================================================================
    log("1) EXACT SIRET match...")
    
    con.execute(f"""
        CREATE OR REPLACE TABLE link_exact AS
        SELECT
            s.siret,
            r.id_rna,
            1.0::DOUBLE AS score,
            'EXACT_SIRET' AS methode
        FROM read_parquet('{SIRENE_SILVER}') s
        JOIN read_parquet('{RNA_SILVER}') r ON s.siret = r.siret
        WHERE r.siret IS NOT NULL AND length(r.siret) = 14;
    """)

    exact_count = con.execute("SELECT count(*) FROM link_exact").fetchone()[0]
    log(f"   {exact_count:,} matches exacts")

    # =========================================================================
    # ÉTAPE 2 : ADDRESS MATCH PAR BATCH DE CODE POSTAL (streaming)
    # =========================================================================
    log("2) ADDRESS MATCH par batch (streaming par code_postal)...")
    
    # Récupérer tous les codes postaux VALIDES (5 chiffres uniquement)
    all_cp = con.execute(f"""
        SELECT DISTINCT code_postal 
        FROM read_parquet('{SIRENE_SILVER}')
        WHERE code_postal IS NOT NULL
          AND length(code_postal) = 5
          AND regexp_full_match(code_postal, '^[0-9]{{5}}$')
        ORDER BY code_postal
    """).fetchdf()['code_postal'].tolist()
    
    total_cp = len(all_cp)
    log(f"   {total_cp:,} codes postaux à traiter")
    
    # Créer table résultats vide
    con.execute("""
        CREATE OR REPLACE TABLE link_address (
            siret VARCHAR,
            id_rna VARCHAR,
            score DOUBLE,
            methode VARCHAR
        );
    """)
    
    batch_size = 100  # Traiter 100 CP à la fois
    batches = [all_cp[i:i+batch_size] for i in range(0, len(all_cp), batch_size)]
    
    for batch_idx, cp_batch in enumerate(batches):
        # Utiliser une liste Python directement (plus sûr que string concatenation)
        
        if (batch_idx + 1) % 20 == 0 or batch_idx == 0:
            log(f"   Batch {batch_idx+1}/{len(batches)} : CP {cp_batch[0]} à {cp_batch[-1]}")
        
        # Traiter ce batch de codes postaux avec paramètres
        con.execute("""
            INSERT INTO link_address
            WITH candidates_base AS (
                SELECT
                    s.siret,
                    r.id_rna,
                    s.name_norm,
                    r.title_norm,
                    TRIM(
                        UPPER(
                            regexp_replace(
                                COALESCE(s.complement_adresse, ''),
                                '[^A-Z0-9 ]',
                                ' ',
                                'g'
                            )
                        )
                    ) AS complement_norm,
                    -- Score adresse (sans stocker les textes)
                    (
                        0.40 +  -- code_postal + numero matchés
                        CASE WHEN s.type_voie_norm = r.type_voie_norm THEN 0.30 ELSE 0.0 END +
                        CASE 
                            WHEN s.libelle_voie_norm = r.libelle_voie_norm THEN 0.30
                            ELSE 0.0
                        END
                    ) AS score_addr
                FROM read_parquet(?) s
                INNER JOIN read_parquet(?) r
                    ON s.code_postal = r.code_postal
                    AND s.numero_norm = r.numero_norm
                    AND s.type_voie_norm = r.type_voie_norm
                WHERE s.code_postal = ANY(?)
                  AND s.siret NOT IN (SELECT siret FROM link_exact)
                  AND s.libelle_voie_norm = r.libelle_voie_norm
            ),
            candidates AS (
                SELECT
                    siret,
                    id_rna,
                    score_addr,
                    -- Score nom: priorité name_norm, fallback complement_adresse
                    CASE 
                        WHEN COALESCE(NULLIF(name_norm, ''), NULLIF(complement_norm, '')) IS NOT NULL
                             AND title_norm IS NOT NULL
                             AND title_norm != ''
                             AND greatest(
                                 length(COALESCE(NULLIF(name_norm, ''), NULLIF(complement_norm, ''))),
                                 length(title_norm)
                             ) > 0
                        THEN 1.0 - (
                            editdist3(
                                COALESCE(NULLIF(name_norm, ''), NULLIF(complement_norm, '')),
                                title_norm
                            )::DOUBLE
                            /
                            greatest(
                                length(COALESCE(NULLIF(name_norm, ''), NULLIF(complement_norm, ''))),
                                length(title_norm)
                            )::DOUBLE
                        )
                        ELSE 0.0 
                    END AS score_nm
                FROM candidates_base
            ),
            scored AS (
                SELECT
                    siret,
                    id_rna,
                    (0.70 * score_addr + 0.30 * score_nm) AS score
                FROM candidates
                WHERE score_addr >= 0.70
            ),
            ranked AS (
                SELECT
                    siret, id_rna, score,
                    row_number() OVER (PARTITION BY siret ORDER BY score DESC) AS rn,
                    count(*) OVER (PARTITION BY siret) AS cnt
                FROM scored
            )
            SELECT siret, id_rna, score, 'ADDRESS_MATCH' AS methode
            FROM ranked
            WHERE 
                (cnt = 1 AND score >= 0.50)
                OR (cnt > 1 AND score >= 0.70)
                OR (cnt > 1 AND rn = 1 AND score >= 0.50);
        """, [SIRENE_SILVER, RNA_SILVER, cp_batch])
        
        if (batch_idx + 1) % 20 == 0:
            current = con.execute("SELECT count(*) FROM link_address").fetchone()[0]
            log(f"      → {current:,} matches jusqu'ici")

    address_count = con.execute("SELECT count(*) FROM link_address").fetchone()[0]
    log(f"   ADDRESS matches: {address_count:,}")

    # =========================================================================
    # ÉTAPE 3 : FUSION + EXPORT
    # =========================================================================
    log("3) Fusion + export...")
    
    con.execute(f"""
        COPY (
            SELECT * FROM link_exact
            UNION ALL
            SELECT * FROM link_address
        ) TO '{LINK_OUT}' (FORMAT PARQUET, CODEC 'ZSTD');
    """)

    total = exact_count + address_count
    log(f"   TOTAL: {total:,} ({exact_count:,} exact + {address_count:,} address)")

    # Nettoyage
    con.execute("DROP TABLE IF EXISTS link_exact;")
    con.execute("DROP TABLE IF EXISTS link_address;")
    
    con.close()
    log("✅ DONE - Matching streaming terminé")

if __name__ == "__main__":
    main()
