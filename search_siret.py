"""
Script de recherche par SIRET dans la base SIRENE
Usage: python search_siret.py [SIRET]
"""
import sys
import duckdb
import os

DUCKDB_PATH = "duckdb/catalog.db"
GOLDEN_RECORD = "data_parquet/golden_record.parquet"

def search_siret(siret: str) -> None:
    """Recherche un SIRET dans golden_record"""
    
    # Vérifier que le SIRET est valide (14 chiffres)
    if not siret.isdigit() or len(siret) != 14:
        print(f"❌ SIRET invalide : '{siret}' (doit contenir 14 chiffres)")
        return
    
    # Connexion à DuckDB
    if os.path.exists(DUCKDB_PATH):
        con = duckdb.connect(DUCKDB_PATH, read_only=True)
        print(f"📂 Connexion à {DUCKDB_PATH}")
    else:
        con = duckdb.connect(':memory:')
        print(f"📂 Lecture directe de {GOLDEN_RECORD}")
    
    # Recherche dans golden_record
    query = f"""
    SELECT 
        siret,
        siren,
        nom,
        enseigne,
        naf,
        status,
        nature,
        code_postal,
        ville,
        num_voie,
        type_voie,
        libelle_voie,
        id_rna,
        rna_titre,
        latitude,
        longitude,
        is_ban_validated,
        geo_quality,
        match_score,
        match_methode
    FROM '{GOLDEN_RECORD}' 
    WHERE siret = '{siret}'
    """
    
    try:
        result = con.execute(query).fetchone()
        
        if result is None:
            print(f"\n❌ Aucun résultat trouvé pour SIRET: {siret}")
        else:
            print(f"\n✅ Établissement trouvé :")
            print("=" * 80)
            print(f"{'SIRET':<25} : {result[0]}")
            print(f"{'SIREN':<25} : {result[1]}")
            print(f"{'Nom':<25} : {result[2]}")
            print(f"{'Enseigne':<25} : {result[3] or '(aucune)'}")
            print(f"{'Code NAF':<25} : {result[4]}")
            print(f"{'Statut':<25} : {result[5]}")
            print(f"{'Nature':<25} : {result[6]}")
            print()
            print(f"{'Adresse':<25} :")
            print(f"  {result[9] or ''} {result[10] or ''} {result[11] or ''}")
            print(f"  {result[7]} {result[8]}")
            print()
            
            if result[12]:  # id_rna
                print(f"{'Association RNA':<25} :")
                print(f"  {'ID RNA':<23} : {result[12]}")
                print(f"  {'Titre':<23} : {result[13]}")
                print(f"  {'Score matching':<23} : {result[18]:.3f}" if result[18] else "")
                print(f"  {'Méthode':<23} : {result[19]}" if result[19] else "")
                print()
            
            if result[14] and result[15]:  # lat, lon
                print(f"{'Géolocalisation BAN':<25} :")
                print(f"  {'Latitude':<23} : {result[14]:.6f}")
                print(f"  {'Longitude':<23} : {result[15]:.6f}")
                print(f"  {'Validé BAN':<23} : {'✓' if result[16] else '✗'}")
                print(f"  {'Qualité géo':<23} : {result[17]:.2f}" if result[17] else "")
            else:
                print(f"{'Géolocalisation':<25} : ❌ Non géocodée")
            
            print("=" * 80)
            
    except Exception as e:
        print(f"\n❌ Erreur lors de la recherche : {e}")
    finally:
        con.close()


def search_in_sirene_bronze(siret: str) -> None:
    """Recherche dans sirene.parquet (données brutes)"""
    
    if not os.path.exists("data_parquet/sirene.parquet"):
        print("❌ Fichier sirene.parquet introuvable")
        return
    
    con = duckdb.connect(':memory:')
    
    query = f"""
    SELECT 
        siret,
        siren,
        nom,
        enseigne,
        naf,
        etat,
        code_postal,
        ville,
        num_voie,
        repetition,
        type_voie,
        libelle_voie,
        complement_adresse
    FROM 'data_parquet/sirene.parquet'
    WHERE siret = '{siret}'
    """
    
    try:
        result = con.execute(query).fetchone()
        
        if result is None:
            print(f"\n❌ Aucun résultat dans SIRENE brut pour: {siret}")
        else:
            print(f"\n✅ Données SIRENE brutes :")
            print("=" * 80)
            print(f"{'SIRET':<25} : {result[0]}")
            print(f"{'SIREN':<25} : {result[1]}")
            print(f"{'Nom':<25} : {result[2]}")
            print(f"{'Enseigne':<25} : {result[3] or '(aucune)'}")
            print(f"{'NAF':<25} : {result[4]}")
            print(f"{'État':<25} : {result[5]}")
            print()
            print(f"{'Adresse brute':<25} :")
            print(f"  {'Numéro':<23} : {result[8] or '(vide)'}")
            print(f"  {'Répétition':<23} : {result[9] or '(aucune)'}")
            print(f"  {'Type voie':<23} : {result[10] or '(vide)'}")
            print(f"  {'Libellé voie':<23} : {result[11] or '(vide)'}")
            print(f"  {'Complément':<23} : {result[12] or '(aucun)'}")
            print(f"  {'Code postal':<23} : {result[6]}")
            print(f"  {'Ville':<23} : {result[7]}")
            print("=" * 80)
            
    except Exception as e:
        print(f"\n❌ Erreur lors de la recherche : {e}")
    finally:
        con.close()


if __name__ == "__main__":
    print("🔍 Recherche d'établissement par SIRET\n")
    
    # Récupérer le SIRET depuis les arguments ou demander à l'utilisateur
    if len(sys.argv) > 1:
        siret = sys.argv[1]
    else:
        siret = input("Entrez le SIRET (14 chiffres) : ").strip()
    
    # Recherche dans golden_record
    search_siret(siret)
    
    # Option : voir aussi les données brutes
    if input("\n📋 Voir aussi les données SIRENE brutes ? (o/N) : ").lower() == 'o':
        search_in_sirene_bronze(siret)
