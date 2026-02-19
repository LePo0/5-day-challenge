import os
import requests
from tqdm import tqdm

# URLs stables des datasets officiels
URLS = {
    # Source SIRENE (Stock des établissements)
    "sirene": "https://object.files.data.gouv.fr/data-pipeline-open/siren/stock/StockEtablissement_utf8.zip", 
    # Source RNA (Waldec)
    "rna": "https://media.interieur.gouv.fr/rna/rna_waldec_20250901.zip",
    # Source BAN (Adresses France)
    "ban": "https://adresse.data.gouv.fr/data/ban/adresses/latest/csv/adresses-france.csv.gz"
}

# Dossiers imposés
DIRS = ["data_raw", "data_parquet", "duckdb"]

def setup_directories():
    """Crée l'arborescence du projet."""
    for d in DIRS:
        os.makedirs(d, exist_ok=True)
        print(f"Dossier vérifié : {d}/")

def download_file(url, filename):
    """Télécharge un fichier avec barre de progression."""
    path = os.path.join("data_raw", filename)
    
    if os.path.exists(path):
        print(f"Fichier existant : {path} (Ignoré)")
        return path
    
    print(f"⬇Téléchargement de {filename}...")
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status() # Vérifie si l'URL est bonne (404, etc.)
        total_size = int(response.headers.get('content-length', 0))
        
        with open(path, 'wb') as file, tqdm(
            desc=filename,
            total=total_size,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for data in response.iter_content(chunk_size=8192):
                size = file.write(data)
                bar.update(size)
        print(f"Téléchargement terminé : {filename}")
        return path
    except Exception as e:
        print(f"Erreur sur {filename}: {e}")
        if os.path.exists(path): os.remove(path) # Nettoyage si échec

if __name__ == "__main__":
    setup_directories()
    
    # Noms de fichiers exacts requis par le sujet
    download_file(URLS["sirene"], "StockEtablissement_utf8.zip")
    download_file(URLS["rna"], "rna_waldec.zip")
    download_file(URLS["ban"], "adresses-france.csv.gz")