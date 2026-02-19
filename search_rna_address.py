"""
Script de recherche d'association RNA par adresse EXACTE
Usage: python search_rna_address.py
"""
import duckdb
import sys

# Paramètres de recherche PRÉCIS
NUMERO = "98"
TYPE_VOIE = "RUE"
LIBELLE_VOIE = "DIDOT"
VILLE = "PARIS"
CODE_POSTAL = "75014"

print(f"\n{'='*80}")
print(f"🔍 RECHERCHE PRÉCISE ASSOCIATION RNA")
print(f"{'='*80}")
print(f"  Adresse exacte : {NUMERO} {TYPE_VOIE} {LIBELLE_VOIE}, {VILLE} {CODE_POSTAL}\n")

con = duckdb.connect(":memory:")

# Recherche EXACTE avec tous les critères normalisés
print("=" * 80)
print("📊 RECHERCHE EXACTE AVEC CRITÈRES NORMALISÉS")
print("-" * 80)

result = con.execute(f"""
    SELECT 
        id_rna,
        titre_asso,
        objet,
        siret,
        numero,
        type_voie,
        libelle_voie,
        ville,
        code_postal,
        numero_norm,
        type_voie_norm,
        libelle_voie_norm,
        city_norm,
        date_creat
    FROM 'data_parquet/rna_silver.parquet'
    WHERE code_postal = '{CODE_POSTAL}'
      AND numero_norm = '{NUMERO}'
      AND type_voie_norm = '{TYPE_VOIE}'
      AND libelle_voie_norm = '{LIBELLE_VOIE}'
      AND city_norm LIKE '%{VILLE}%'
""").fetchall()

if result:
    cols = [desc[0] for desc in con.description]
    print(f"✅ {len(result)} résultat(s) EXACT(S) trouvé(s)\n")
    
    for idx, row in enumerate(result, 1):
        data = dict(zip(cols, row))
        print(f"{'='*80}")
        print(f"RÉSULTAT #{idx}")
        print(f"{'='*80}\n")
        
        print(f"🏢 IDENTITÉ")
        print(f"  ID RNA              : {data['id_rna']}")
        print(f"  Titre               : {data['titre_asso']}")
        print(f"  SIRET               : {data['siret']}")
        print(f"  Date création       : {data['date_creat']}")
        
        print(f"\n📍 ADRESSE BRUTE")
        print(f"  {data['numero']} {data['type_voie']} {data['libelle_voie']}")
        print(f"  {data['code_postal']} {data['ville']}")
        
        print(f"\n🔧 ADRESSE NORMALISÉE")
        print(f"  Numéro              : {data['numero_norm']}")
        print(f"  Type voie           : {data['type_voie_norm']}")
        print(f"  Libellé voie        : {data['libelle_voie_norm']}")
        print(f"  Ville normalisée    : {data['city_norm']}")
        
        print(f"\n📝 OBJET")
        print(f"  {data['objet'][:200] if data['objet'] else 'N/A'}...")
        print()
else:
    print(f"❌ AUCUN résultat trouvé avec ces critères EXACTS\n")
    
    # Diagnostic : essayer critère par critère
    print(f"\n{'='*80}")
    print("🔍 DIAGNOSTIC - Recherche par critère")
    print("-" * 80)
    
    # Test 1 : Code postal seul
    count_cp = con.execute(f"""
        SELECT COUNT(*) FROM 'data_parquet/rna_silver.parquet'
        WHERE code_postal = '{CODE_POSTAL}'
    """).fetchone()[0]
    print(f"  Code postal {CODE_POSTAL}             : {count_cp:,} résultats")
    
    # Test 2 : + numéro
    count_num = con.execute(f"""
        SELECT COUNT(*) FROM 'data_parquet/rna_silver.parquet'
        WHERE code_postal = '{CODE_POSTAL}'
          AND numero_norm = '{NUMERO}'
    """).fetchone()[0]
    print(f"  + numéro {NUMERO}                      : {count_num:,} résultats")
    
    # Test 3 : + type voie
    count_type = con.execute(f"""
        SELECT COUNT(*) FROM 'data_parquet/rna_silver.parquet'
        WHERE code_postal = '{CODE_POSTAL}'
          AND numero_norm = '{NUMERO}'
          AND type_voie_norm = '{TYPE_VOIE}'
    """).fetchone()[0]
    print(f"  + type voie {TYPE_VOIE}                 : {count_type:,} résultats")
    
    # Test 4 : + libellé voie
    count_lib = con.execute(f"""
        SELECT COUNT(*) FROM 'data_parquet/rna_silver.parquet'
        WHERE code_postal = '{CODE_POSTAL}'
          AND numero_norm = '{NUMERO}'
          AND type_voie_norm = '{TYPE_VOIE}'
          AND libelle_voie_norm = '{LIBELLE_VOIE}'
    """).fetchone()[0]
    print(f"  + libellé voie {LIBELLE_VOIE}           : {count_lib:,} résultats")
    
    # Test 5 : + ville
    count_ville = con.execute(f"""
        SELECT COUNT(*) FROM 'data_parquet/rna_silver.parquet'
        WHERE code_postal = '{CODE_POSTAL}'
          AND numero_norm = '{NUMERO}'
          AND type_voie_norm = '{TYPE_VOIE}'
          AND libelle_voie_norm = '{LIBELLE_VOIE}'
          AND city_norm LIKE '%{VILLE}%'
    """).fetchone()[0]
    print(f"  + ville {VILLE}                     : {count_ville:,} résultats")
    
    # Voir les valeurs distinctes de city_norm pour ce code postal
    print(f"\n  Valeurs city_norm distinctes pour {CODE_POSTAL} avec 98 RUE DIDOT:")
    cities = con.execute(f"""
        SELECT DISTINCT city_norm 
        FROM 'data_parquet/rna_silver.parquet'
        WHERE code_postal = '{CODE_POSTAL}'
          AND numero_norm = '{NUMERO}'
          AND type_voie_norm = '{TYPE_VOIE}'
          AND libelle_voie_norm = '{LIBELLE_VOIE}'
        LIMIT 10
    """).fetchall()
    
    if cities:
        for city in cities:
            print(f"    - {city[0]}")
    else:
        print(f"    (aucune)")

# Vérifier si l'adresse existe dans BAN
print(f"\n{'='*80}")
print("🗺️  VÉRIFICATION DANS BAN")
print("-" * 80)

ban_check = con.execute(f"""
    SELECT 
        numero,
        numero_norm,
        type_voie_norm,
        libelle_voie_norm,
        code_postal,
        nom_commune,
        city_norm,
        lat,
        lon
    FROM 'data_parquet/ban_silver.parquet'
    WHERE code_postal = '{CODE_POSTAL}'
      AND numero_norm = '{NUMERO}'
      AND type_voie_norm = '{TYPE_VOIE}'
      AND libelle_voie_norm = '{LIBELLE_VOIE}'
    LIMIT 5
""").fetchall()

if ban_check:
    print(f"✅ {len(ban_check)} adresse(s) correspondante(s) dans BAN\n")
    
    for idx, row in enumerate(ban_check, 1):
        print(f"  BAN #{idx}")
        print(f"    Numéro         : {row[0]} (norm: {row[1]})")
        print(f"    Type voie      : {row[2]}")
        print(f"    Libellé voie   : {row[3]}")
        print(f"    Code postal    : {row[4]}")
        print(f"    Commune        : {row[5]}")
        print(f"    City norm      : {row[6]}")
        print(f"    Coordonnées    : {row[7]:.6f}, {row[8]:.6f}")
        print()
else:
    print(f"❌ Adresse non trouvée dans BAN avec ces critères exacts\n")

con.close()
print(f"{'='*80}\n")

con.close()
print(f"{'='*80}\n")
