import duckdb
import os
import zipfile
import shutil
import glob
import time

# Configuration des chemins
RAW_DIR = "data_raw"
PARQUET_DIR = "data_parquet"
TEMP_RNA_DIR = os.path.join(RAW_DIR, "rna_temp")

os.makedirs(PARQUET_DIR, exist_ok=True)

def extract_zip_single(zip_path, target_dir):
    """Extrait un seul CSV (pour SIRENE)."""
    print(f"Extraction (Single) de {os.path.basename(zip_path)}...")
    if not os.path.exists(zip_path):
        print("Fichier zip introuvable !")
        return None
        
    with zipfile.ZipFile(zip_path, 'r') as z:
        csv_files = [f for f in z.namelist() if f.endswith('.csv')]
        if not csv_files: return None
        target_file = csv_files[0]
        extracted_path = os.path.join(target_dir, target_file)
        if not os.path.exists(extracted_path):
            z.extract(target_file, target_dir)
        return extracted_path

def convert_sirene(con):
    print("\nTraitement SIRENE (StockEtablissement)...")

    zip_path = os.path.join(RAW_DIR, "StockEtablissement_utf8.zip")
    csv_path = extract_zip_single(zip_path, RAW_DIR)
    
    if not csv_path: return

    # On utilise types=VARCHAR pour sécuriser les codes postaux (01000) et SIRET
    query = f"""
        COPY (
            SELECT 
                siret, siren, enseigne1Etablissement as enseigne, 
                denominationUsuelleEtablissement as nom, numeroVoieEtablissement as num_voie,
                typeVoieEtablissement as type_voie, libelleVoieEtablissement as libelle_voie,
                codePostalEtablissement as code_postal, libelleCommuneEtablissement as ville,
                etatAdministratifEtablissement as etat, activitePrincipaleEtablissement as naf
            FROM read_csv('{csv_path}', 
                delim=',', header=True, auto_detect=True, all_varchar=False,
                types={{'codePostalEtablissement': 'VARCHAR', 'siret': 'VARCHAR', 'siren': 'VARCHAR'}}
            )
        ) TO '{PARQUET_DIR}/sirene.parquet' (FORMAT 'PARQUET', CODEC 'ZSTD');
    """
    con.execute(query)
    print("SIRENE converti.")
    try: os.remove(csv_path) 
    except: pass

def convert_rna(con):
    print("\nTraitement RNA (Associations)...")
    # Pour le RNA, on force la reconversion si le fichier temporaire existe, 
    # car ça veut dire que ça a planté avant.
    
    zip_path = os.path.join(RAW_DIR, "rna_waldec.zip")
    
    # Extraction propre
    if os.path.exists(TEMP_RNA_DIR):
        print("Nettoyage dossier temporaire précédent...")
        try: shutil.rmtree(TEMP_RNA_DIR)
        except: pass # Si ça bloque, on espère que c'est vide ou écrasable
            
    os.makedirs(TEMP_RNA_DIR, exist_ok=True)
    
    print("Extraction des CSV départements...")
    with zipfile.ZipFile(zip_path, 'r') as z:
        csv_list = [f for f in z.namelist() if f.endswith('.csv') and "rna_waldec" in f]
        for file in csv_list:
            z.extract(file, TEMP_RNA_DIR)
            
    # Conversion Robuste (Via liste Python)
    print(f"Fusion de {len(csv_list)} fichiers...")
    
    # On récupère la liste exacte des fichiers avec glob pour éviter les erreurs de wildcard DuckDB
    files = glob.glob(os.path.join(TEMP_RNA_DIR, "*.csv"))
    # On reformate la liste pour SQL : ['file1', 'file2']
    files_sql = str(files).replace("\\", "/") 
    
    query = f"""
        COPY (
            SELECT 
                id as id_rna, siret, titre as titre_asso,
                adrs_codepostal as code_postal, adrs_libcommune as ville,
                objet, date_creat,
                -- Ajout colonnes adresse pour matching
                adrs_numvoie as num_voie,
                adrs_typevoie as type_voie,
                adrs_libvoie as libelle_voie
            FROM read_csv({files_sql}, 
                delim=';', 
                header=True, 
                union_by_name=True,
                ignore_errors=True,
                types={{'adrs_codepostal': 'VARCHAR', 'siret': 'VARCHAR', 'id': 'VARCHAR'}}
            )
        ) TO '{PARQUET_DIR}/rna.parquet' (FORMAT 'PARQUET', CODEC 'ZSTD');
    """
    con.execute(query)
    print("RNA converti.")

def convert_ban(con):
    print("\nTraitement BAN...")
    # if os.path.exists(f'{PARQUET_DIR}/ban.parquet'):
    #     print("ban.parquet existe déjà, on passe.")
    #     return

    gz_path = os.path.join(RAW_DIR, "adresses-france.csv.gz").replace("\\", "/")
    query = f"""
        COPY (
            SELECT 
                id, numero, rep, nom_voie, code_postal, nom_commune, lat, lon
            FROM read_csv('{gz_path}', 
                delim=';', quote='"', header=True, ignore_errors=True,
                types={{'code_postal': 'VARCHAR', 'numero': 'VARCHAR'}}
            )
        ) TO '{PARQUET_DIR}/ban.parquet' (FORMAT 'PARQUET', CODEC 'ZSTD');
    """
    con.execute(query)
    print("BAN converti.")

def verify_data(con):
    print("\nVÉRIFICATION DES DONNÉES GÉNÉRÉES :")
    tables = {
        "SIRENE": "sirene.parquet",
        "RNA": "rna.parquet",
        "BAN": "ban.parquet"
    }
    for name, file in tables.items():
        path = f"{PARQUET_DIR}/{file}"
        if os.path.exists(path):
            try:
                # Lecture légère sans charger en RAM
                count = con.execute(f"SELECT count(*) FROM '{path}'").fetchone()[0]
                size_mb = os.path.getsize(path) / (1024 * 1024)
                print(f"{name}: {count:,} lignes ({size_mb:.1f} Mo)")
            except Exception as e:
                print(f"{name}: Erreur lecture ({e})")
        else:
            print(f"{name}: Fichier manquant !")

if __name__ == "__main__":
    con = duckdb.connect(database=':memory:')
    con.execute("SET memory_limit='4GB';")
    
    try:
        convert_sirene(con)
        convert_rna(con)
        convert_ban(con)
        
        # Vérification finale
        verify_data(con)
        
    except Exception as e:
        print(f"\nErreur : {e}")
    finally:
        con.close()
        # Nettoyage final sécurisé
        if os.path.exists(TEMP_RNA_DIR):
            print("\nNettoyage fichiers temporaires...")
            time.sleep(1)
            try: shutil.rmtree(TEMP_RNA_DIR)
            except: pass