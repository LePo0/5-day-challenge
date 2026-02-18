import duckdb
import os
import time

# Chemins
PARQUET_DIR = "data_parquet"
DB_PATH = "duckdb/warehouse.duckdb" 
os.makedirs("duckdb", exist_ok=True)

def create_db_connection():
    con = duckdb.connect(DB_PATH)
    con.execute("SET memory_limit='4GB';") 
    con.execute("SET temp_directory='duckdb/tmp';")
    return con

def create_macros(con):
    print("Etape 1 : Creation des Macros...")
    con.execute("""
    CREATE OR REPLACE MACRO normalize_addr(col) AS 
    TRIM(
        REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(
                        UPPER(strip_accents(col)), 
                        ' AV ', ' AVENUE '
                    ), ' BD ', ' BOULEVARD '
                ), ' PL ', ' PLACE '
            ), ' R ', ' RUE '
        )
    );
    """)

def create_silver_tables(con):
    print("Etape 2 : Preparation des tables SILVER (Pre-calculs)...")
    
    # 2.1 BAN SILVER
    print("   -> BAN Silver (Nettoyage & Indexation)...")
    con.execute("DROP TABLE IF EXISTS ban_silver;")
    con.execute(f"""
    CREATE TABLE ban_silver AS 
    SELECT 
        code_postal,
        numero,
        nom_voie,
        normalize_addr(nom_voie) as nom_voie_norm,
        lat,
        lon
    FROM '{PARQUET_DIR}/ban.parquet'
    WHERE code_postal IS NOT NULL;
    """)
    con.execute("CREATE INDEX idx_ban_join ON ban_silver(code_postal, numero, nom_voie_norm);")
    
    # 2.2 SIRENE SILVER
    print("   -> SIRENE Silver (Pre-calcul adresse)...")
    con.execute("DROP TABLE IF EXISTS sirene_silver;")
    con.execute(f"""
    CREATE TABLE sirene_silver AS 
    SELECT 
        siret, siren, nom, enseigne, naf, etat, 
        code_postal, ville, num_voie, type_voie, libelle_voie,
        normalize_addr(COALESCE(type_voie, '') || ' ' || COALESCE(libelle_voie, '')) as adresse_norm
    FROM '{PARQUET_DIR}/sirene.parquet';
    """)
    con.execute("CREATE INDEX idx_sirene_join ON sirene_silver(code_postal, num_voie, adresse_norm);")

    # 2.3 RNA SILVER
    print("   -> RNA Silver...")
    con.execute("DROP TABLE IF EXISTS rna_silver;")
    con.execute(f"""
    CREATE TABLE rna_silver AS 
    SELECT DISTINCT id_rna, siret, titre_asso
    FROM '{PARQUET_DIR}/rna.parquet'
    WHERE siret IS NOT NULL;
    """)
    con.execute("CREATE INDEX idx_rna_siret ON rna_silver(siret);")
    
    print("Tables Silver pretes et indexees.")

def create_golden_record(con):
    print("Etape 3 : Creation du GOLDEN RECORD...")
    start_time = time.time()
    
    con.execute("DROP TABLE IF EXISTS golden_record;")
    
    # Jointure optimisée sur égalité stricte pour la performance
    query = f"""
    CREATE TABLE golden_record AS 
    SELECT 
        s.siret, s.siren, s.nom, s.enseigne, s.naf, s.etat, 
        s.code_postal, s.ville, s.num_voie, s.type_voie, s.libelle_voie,
        
        -- Info RNA
        r.id_rna,
        r.titre_asso,
        CASE WHEN r.id_rna IS NOT NULL THEN 'ASSOCIATION' ELSE 'ENTREPRISE' END as nature,
        
        -- Info BAN
        b.lat,
        b.lon,
        b.nom_voie as ban_label,
        CASE WHEN b.lat IS NOT NULL THEN true ELSE false END as is_geolocated
        
    FROM sirene_silver s
    
    -- Jointure RNA (Hash Join)
    LEFT JOIN rna_silver r ON s.siret = r.siret
    
    -- Jointure BAN (Hash Join)
    LEFT JOIN ban_silver b 
        ON s.code_postal = b.code_postal 
        AND s.num_voie = b.numero
        AND s.adresse_norm = b.nom_voie_norm
    """
    
    con.execute(query)
    
    duration = time.time() - start_time
    print(f"Jointure terminee en {duration:.1f} secondes.")
    
    # Nettoyage
    con.execute("DROP TABLE sirene_silver;")
    con.execute("DROP TABLE ban_silver;")
    con.execute("DROP TABLE rna_silver;")

def verify_croix_rouge(con):
    print("TEST DE VALIDATION (SIRET EXISTANT)...")
    
    # SIRET trouve par ton script de debug
    target_siret = "77567227234024" 
    
    res = con.execute(f"SELECT * FROM golden_record WHERE siret = '{target_siret}'").fetchall()
    
    if not res:
        print(f"ECHEC : Le SIRET {target_siret} est introuvable.")
        return

    cols = [d[0] for d in con.description]
    row = res[0]
    data = dict(zip(cols, row))
    
    print(f"   SIRET : {data.get('siret')}")
    print(f"   Ville : {data.get('ville')} (CP: {data.get('code_postal')})")
    
    rna = data.get('id_rna')
    if rna:
        print(f"   RNA TROUVE : {rna} (Jointure Asso reussie)")
    else:
        print(f"   RNA non trouve")

    lat = data.get('lat')
    if lat:
        print(f"   GPS TROUVE : {lat}, {data.get('lon')} (Jointure BAN reussie)")
    else:
        print(f"   GPS non trouve (Adresse non normalisee ou absente BAN)")
        print(f"      -> Adresse source : {data.get('num_voie')} {data.get('type_voie')} {data.get('libelle_voie')}")

if __name__ == "__main__":
    if os.path.exists(DB_PATH + ".wal"):
        try: os.remove(DB_PATH + ".wal")
        except: pass

    con = create_db_connection()
    try:
        create_macros(con)
        create_silver_tables(con)
        create_golden_record(con)
        verify_croix_rouge(con)
    except Exception as e:
        print(f"Erreur : {e}")
    finally:
        con.close()