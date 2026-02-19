"""
Script de recherche rapide par SIRET
Usage: python search_siret.py [SIRET]
"""
import sys
import duckdb

SIRET = sys.argv[1] if len(sys.argv) > 1 else "77567227221138"

print(f"\n{'='*80}")
print(f"🔍 RECHERCHE SIRET: {SIRET}")
print(f"{'='*80}\n")

con = duckdb.connect("duckdb/catalog.db", read_only=True)

# 1. Recherche dans golden_record
print("📊 GOLDEN RECORD")
print("-" * 80)

result = con.execute(f"""
    SELECT *
    FROM golden_record
    WHERE siret = '{SIRET}'
""").fetchone()

if result:
    cols = [desc[0] for desc in con.description]
    print(f"✅ TROUVÉ\n")
    for col, val in zip(cols, result):
        print(f"  {col:25} : {val}")
else:
    print(f"❌ PAS TROUVÉ dans golden_record\n")

# 2. Recherche dans SIRENE Silver
print(f"\n{'='*80}")
print("📄 SIRENE SILVER (données brutes)")
print("-" * 80)

result_sirene = con.execute(f"""
    SELECT *
    FROM 'data_parquet/sirene_silver.parquet'
    WHERE siret = '{SIRET}'
""").fetchone()

if result_sirene:
    cols = [desc[0] for desc in con.description]
    print(f"✅ TROUVÉ\n")
    for col, val in zip(cols, result_sirene):
        print(f"  {col:25} : {val}")
else:
    print(f"❌ PAS TROUVÉ dans sirene_silver\n")

# 3. Diagnostic BAN matching
if result:
    print(f"\n{'='*80}")
    print("🗺️  DIAGNOSTIC MATCHING BAN (avec city_norm)")
    print("-" * 80)
    
    ban_check = con.execute(f"""
        SELECT 
            s.siret,
            s.code_postal,
            s.city_norm AS sirene_city,
            s.numero_norm,
            s.type_voie_norm,
            s.libelle_voie_norm,
            b.city_norm AS ban_city,
            b.latitude,
            b.longitude,
            b.geo_quality
        FROM 'data_parquet/sirene_silver.parquet' s
        LEFT JOIN (
            SELECT 
                code_postal, city_norm, numero_norm, type_voie_norm, libelle_voie_norm,
                ANY_VALUE(latitude) AS latitude,
                ANY_VALUE(longitude) AS longitude,
                MAX(geo_quality) AS geo_quality
            FROM 'data_parquet/ban_silver.parquet'
            GROUP BY code_postal, city_norm, numero_norm, type_voie_norm, libelle_voie_norm
        ) b 
            ON s.code_postal = b.code_postal 
            AND s.city_norm = b.city_norm
            AND s.numero_norm = b.numero_norm
            AND COALESCE(s.type_voie_norm, '') = COALESCE(b.type_voie_norm, '')
            AND COALESCE(s.libelle_voie_norm, '') = COALESCE(b.libelle_voie_norm, '')
        WHERE s.siret = '{SIRET}'
    """).fetchone()
    
    if ban_check:
        cols = [desc[0] for desc in con.description]
        has_geo = ban_check[7] is not None
        
        print(f"{'Statut géolocalisation':<30} : {'✅ GÉOLOCALISÉ' if has_geo else '❌ NON GÉOLOCALISÉ'}\n")
        
        for col, val in zip(cols, ban_check):
            marker = "✅" if val else "❌"
            if col in ['latitude', 'longitude', 'geo_quality']:
                marker = "✅" if val else "⚠️ "
            print(f"  {marker} {col:<25} : {val}")
        
        # Diagnostic détaillé
        if not has_geo:
            print(f"\n⚠️  DIAGNOSTIC:")
            print(f"  SIRENE city_norm : '{ban_check[2]}'")
            print(f"  BAN city_norm    : {ban_check[6]}")
            
            if ban_check[2] != ban_check[6]:
                print(f"\n❌ PROBLÈME IDENTIFIÉ : city_norm incompatible !")
                print(f"   → '{ban_check[2]}' ≠ NULL ou BAN différent")
                print(f"\n💡 SOLUTION : Retirer city_norm du JOIN BAN")
                print(f"   Le code postal ({ban_check[1]}) suffit pour identifier la commune")
    
    # Test SANS city_norm
    print(f"\n{'='*80}")
    print("🗺️  TEST MATCHING BAN (SANS city_norm)")
    print("-" * 80)
    
    ban_test = con.execute(f"""
        SELECT 
            s.code_postal,
            b.city_norm AS ban_city,
            b.latitude,
            b.longitude,
            b.geo_quality
        FROM 'data_parquet/sirene_silver.parquet' s
        LEFT JOIN (
            SELECT 
                code_postal, city_norm, numero_norm, type_voie_norm, libelle_voie_norm,
                ANY_VALUE(latitude) AS latitude,
                ANY_VALUE(longitude) AS longitude,
                MAX(geo_quality) AS geo_quality
            FROM 'data_parquet/ban_silver.parquet'
            GROUP BY code_postal, city_norm, numero_norm, type_voie_norm, libelle_voie_norm
        ) b 
            ON s.code_postal = b.code_postal 
            AND s.numero_norm = b.numero_norm
            AND COALESCE(s.type_voie_norm, '') = COALESCE(b.type_voie_norm, '')
            AND COALESCE(s.libelle_voie_norm, '') = COALESCE(b.libelle_voie_norm, '')
        WHERE s.siret = '{SIRET}'
    """).fetchone()
    
    if ban_test and ban_test[2]:
        print(f"✅ SUCCÈS : Géolocalisation trouvée SANS city_norm !\n")
        print(f"  Code postal   : {ban_test[0]}")
        print(f"  Ville BAN     : {ban_test[1]}")
        print(f"  Latitude      : {ban_test[2]:.6f}")
        print(f"  Longitude     : {ban_test[3]:.6f}")
        print(f"  Geo quality   : {ban_test[4]}")
        print(f"\n💡 Retirer city_norm du JOIN améliorerait cette géolocalisation")
    else:
        print(f"❌ Aucune géolocalisation même sans city_norm")
        print(f"   (l'adresse n'existe peut-être pas dans BAN)")

# 4. Statistiques globales
print(f"\n{'='*80}")
print("📊 STATISTIQUES GLOBALES")
print("-" * 80)

stats = con.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(latitude) as with_geo,
        COUNT(*) - COUNT(latitude) as without_geo,
        ROUND(COUNT(latitude) * 100.0 / COUNT(*), 2) as pct_geo
    FROM golden_record
""").fetchone()

print(f"""
  Total établissements     : {stats[0]:,}
  Avec géolocalisation     : {stats[1]:,} ({stats[3]}%)
  Sans géolocalisation     : {stats[2]:,}
""")

con.close()
print(f"{'='*80}\n")
