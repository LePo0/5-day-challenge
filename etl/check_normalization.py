"""
Script de vérification de la qualité de la normalisation
---------------------------------------------------------
Vérifie les tables normalisées (Silver) pour s'assurer que :
- Les valeurs nulles sont bien gérées
- Les formats sont cohérents
- Les données aberrantes sont filtrées
"""

import duckdb
import os

PARQUET_DIR = "data_parquet"

def create_connection():
    con = duckdb.connect(database=':memory:')
    con.execute("SET memory_limit='4GB';")
    return con

def check_file_exists(filename):
    """Vérifie l'existence d'un fichier."""
    path = os.path.join(PARQUET_DIR, filename)
    exists = os.path.exists(path)
    if exists:
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f" {filename} ({size_mb:.1f} Mo)")
        return True
    else:
        print(f" {filename} manquant")
        return False

def check_sirene_quality(con):
    """Analyse la qualité des données SIRENE normalisées."""
    print("\n" + "="*70)
    print(" VÉRIFICATION SIRENE (Silver)")
    print("="*70)
    
    file = f"{PARQUET_DIR}/sirene_silver.parquet"
    if not os.path.exists(file):
        print(" Fichier manquant")
        return
    
    # Stats générales
    stats = con.execute(f"""
        SELECT 
            COUNT(*) as total,
            COUNT(DISTINCT siret) as siret_unique,
            COUNT(DISTINCT code_postal) as cp_unique,
            SUM(CASE WHEN name_norm IS NULL OR TRIM(name_norm) = '' THEN 1 ELSE 0 END) as nom_null,
            SUM(CASE WHEN code_postal IS NULL THEN 1 ELSE 0 END) as cp_null,
            SUM(CASE WHEN LENGTH(code_postal) != 5 THEN 1 ELSE 0 END) as cp_invalide
        FROM read_parquet('{file}')
    """).fetchone()
    
    print(f"\n Statistiques générales :")
    print(f"   Total lignes      : {stats[0]:,}")
    print(f"   SIRET uniques     : {stats[1]:,}")
    print(f"   Codes postaux     : {stats[2]:,}")
    print(f"   Noms null/vides   : {stats[3]:,} ({stats[3]/stats[0]*100:.2f}%)")
    print(f"   CP null           : {stats[4]:,}")
    print(f"   CP invalides      : {stats[5]:,}")
    
    # Échantillon de données
    print(f"\n Échantillon de 5 lignes :")
    sample = con.execute(f"""
        SELECT siret, name_norm, street_norm, code_postal, city_norm
        FROM read_parquet('{file}')
        LIMIT 5
    """).fetchdf()
    print(sample.to_string(index=False))
    
    # Top 5 villes
    print(f"\n Top 5 villes avec le plus d'établissements :")
    top_cities = con.execute(f"""
        SELECT city_norm, code_postal, COUNT(*) as nb_etab
        FROM read_parquet('{file}')
        GROUP BY city_norm, code_postal
        ORDER BY nb_etab DESC
        LIMIT 5
    """).fetchdf()
    print(top_cities.to_string(index=False))

def check_rna_quality(con):
    """Analyse la qualité des données RNA normalisées."""
    print("\n" + "="*70)
    print(" VÉRIFICATION RNA (Silver)")
    print("="*70)
    
    file = f"{PARQUET_DIR}/rna_silver.parquet"
    if not os.path.exists(file):
        print(" Fichier manquant")
        return
    
    stats = con.execute(f"""
        SELECT 
            COUNT(*) as total,
            COUNT(DISTINCT id_rna) as id_unique,
            SUM(CASE WHEN siret IS NOT NULL THEN 1 ELSE 0 END) as avec_siret,
            SUM(CASE WHEN title_norm IS NULL OR TRIM(title_norm) = '' THEN 1 ELSE 0 END) as titre_null,
            SUM(CASE WHEN code_postal IS NULL THEN 1 ELSE 0 END) as cp_null
        FROM read_parquet('{file}')
    """).fetchone()
    
    print(f"\n Statistiques générales :")
    print(f"   Total lignes      : {stats[0]:,}")
    print(f"   ID RNA uniques    : {stats[1]:,}")
    print(f"   Avec SIRET        : {stats[2]:,} ({stats[2]/stats[0]*100:.2f}%)")
    print(f"   Titres null       : {stats[3]:,}")
    print(f"   CP null           : {stats[4]:,}")
    
    # Échantillon
    print(f"\n Échantillon de 5 associations :")
    sample = con.execute(f"""
        SELECT id_rna, title_norm, code_postal, city_norm
        FROM read_parquet('{file}')
        LIMIT 5
    """).fetchdf()
    print(sample.to_string(index=False))

def check_ban_quality(con):
    """Analyse la qualité des données BAN normalisées."""
    print("\n" + "="*70)
    print(" VÉRIFICATION BAN (Silver)")
    print("="*70)
    
    file = f"{PARQUET_DIR}/ban_silver.parquet"
    if not os.path.exists(file):
        print(" Fichier manquant")
        return
    
    stats = con.execute(f"""
        SELECT 
            COUNT(*) as total,
            COUNT(DISTINCT code_postal) as cp_unique,
            COUNT(DISTINCT city_norm) as communes,
            SUM(CASE WHEN lat IS NULL OR lon IS NULL THEN 1 ELSE 0 END) as sans_coords,
            SUM(CASE WHEN street_norm IS NULL OR TRIM(street_norm) = '' THEN 1 ELSE 0 END) as sans_voie
        FROM read_parquet('{file}')
    """).fetchone()
    
    print(f"\n Statistiques générales :")
    print(f"   Total adresses    : {stats[0]:,}")
    print(f"   Codes postaux     : {stats[1]:,}")
    print(f"   Communes          : {stats[2]:,}")
    print(f"   Sans coordonnées  : {stats[3]:,} ({stats[3]/stats[0]*100:.2f}%)")
    print(f"   Sans nom de voie  : {stats[4]:,}")
    
    # Échantillon normalisé
    print(f"\n Échantillon de normalisation des voies :")
    sample = con.execute(f"""
        SELECT numero, street_norm, code_postal, city_norm
        FROM read_parquet('{file}')
        WHERE street_norm LIKE '%AVENUE%' OR street_norm LIKE '%BOULEVARD%'
        LIMIT 5
    """).fetchdf()
    print(sample.to_string(index=False))

def check_croix_rouge(con):
    """Vérifie le cas d'or : Croix-Rouge Française."""
    print("\n" + "="*70)
    print(" CAS D'OR : Croix-Rouge Française (SIRET 77567227200020)")
    print("="*70)
    
    siret = "77567227200020"
    
    # Dans SIRENE
    file_sirene = f"{PARQUET_DIR}/sirene_silver.parquet"
    if os.path.exists(file_sirene):
        result_sirene = con.execute(f"""
            SELECT siret, name_norm, street_norm, code_postal, city_norm
            FROM read_parquet('{file_sirene}')
            WHERE siret = '{siret}'
        """).fetchdf()
        
        if len(result_sirene) > 0:
            print("\n Trouvée dans SIRENE normalisé :")
            print(result_sirene.to_string(index=False))
        else:
            print("\n  NON trouvée dans SIRENE normalisé")
    
    # Dans RNA (si SIRET présent)
    file_rna = f"{PARQUET_DIR}/rna_silver.parquet"
    if os.path.exists(file_rna):
        result_rna = con.execute(f"""
            SELECT id_rna, siret, title_norm, code_postal, city_norm
            FROM read_parquet('{file_rna}')
            WHERE siret = '{siret}'
        """).fetchdf()
        
        if len(result_rna) > 0:
            print("\n Trouvée dans RNA normalisé :")
            print(result_rna.to_string(index=False))
        else:
            print("\n  NON trouvée dans RNA normalisé (peut-être pas de lien SIRET)")

def compare_before_after(con):
    """Compare les données avant/après normalisation."""
    print("\n" + "="*70)
    print(" COMPARAISON AVANT/APRÈS NORMALISATION")
    print("="*70)
    
    # SIRENE
    if os.path.exists(f"{PARQUET_DIR}/sirene.parquet") and os.path.exists(f"{PARQUET_DIR}/sirene_silver.parquet"):
        before = con.execute(f"SELECT COUNT(*) FROM read_parquet('{PARQUET_DIR}/sirene.parquet')").fetchone()[0]
        after = con.execute(f"SELECT COUNT(*) FROM read_parquet('{PARQUET_DIR}/sirene_silver.parquet')").fetchone()[0]
        rejected = before - after
        print(f"\n SIRENE :")
        print(f"   Avant       : {before:,} lignes")
        print(f"   Après       : {after:,} lignes")
        print(f"   Rejetées    : {rejected:,} ({rejected/before*100:.3f}%)")
    
    # RNA
    if os.path.exists(f"{PARQUET_DIR}/rna.parquet") and os.path.exists(f"{PARQUET_DIR}/rna_silver.parquet"):
        before = con.execute(f"SELECT COUNT(*) FROM read_parquet('{PARQUET_DIR}/rna.parquet')").fetchone()[0]
        after = con.execute(f"SELECT COUNT(*) FROM read_parquet('{PARQUET_DIR}/rna_silver.parquet')").fetchone()[0]
        rejected = before - after
        print(f"\n RNA :")
        print(f"   Avant       : {before:,} lignes")
        print(f"   Après       : {after:,} lignes")
        print(f"   Rejetées    : {rejected:,} ({rejected/before*100:.3f}%)")
    
    # BAN
    if os.path.exists(f"{PARQUET_DIR}/ban.parquet") and os.path.exists(f"{PARQUET_DIR}/ban_silver.parquet"):
        before = con.execute(f"SELECT COUNT(*) FROM read_parquet('{PARQUET_DIR}/ban.parquet')").fetchone()[0]
        after = con.execute(f"SELECT COUNT(*) FROM read_parquet('{PARQUET_DIR}/ban_silver.parquet')").fetchone()[0]
        rejected = before - after
        print(f"\n📍 BAN :")
        print(f"   Avant       : {before:,} lignes")
        print(f"   Après       : {after:,} lignes")
        print(f"   Rejetées    : {rejected:,} ({rejected/before*100:.3f}%)")

if __name__ == "__main__":
    print(" VÉRIFICATION DE LA QUALITÉ DE LA NORMALISATION")
    print("="*70)
    
    # Vérifier les fichiers
    print("\n Fichiers générés :")
    files_to_check = [
        "sirene_silver.parquet",
        "rna_silver.parquet", 
        "ban_silver.parquet"
    ]
    
    all_exist = all(check_file_exists(f) for f in files_to_check)
    
    if not all_exist:
        print("\n  Tous les fichiers ne sont pas présents. Exécutez d'abord normalize.py")
        exit(1)
    
    # Connexion DuckDB
    con = create_connection()
    
    try:
        # Analyses détaillées
        compare_before_after(con)
        check_sirene_quality(con)
        check_rna_quality(con)
        check_ban_quality(con)
        check_croix_rouge(con)
        
        print("\n" + "="*70)
        print(" VÉRIFICATION TERMINÉE")
        print("="*70)
        
    except Exception as e:
        print(f"\n Erreur : {e}")
        import traceback
        traceback.print_exc()
    finally:
        con.close()
