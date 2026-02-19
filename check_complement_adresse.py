import duckdb

# Connexion à DuckDB
conn = duckdb.connect()

# Lecture des 100 premiers éléments de sirene_silver avec le complément d'adresse
query = """
SELECT 
    siret,
    siren,
    nom,
    complement_adresse,
    numero,
    type_voie,
    libelle_voie,
    code_postal,
    ville
FROM read_parquet('data_parquet/sirene_silver.parquet')
LIMIT 100
"""

result = conn.execute(query).fetchall()

print(f"{'='*120}")
print(f"Complément d'adresse des 100 premiers éléments de sirene_silver")
print(f"{'='*120}\n")

for idx, row in enumerate(result, 1):
    siret, siren, denom, complement, numero, type_v, libelle_v, cp, commune = row
    
    print(f"{idx}. SIRET: {siret}")
    print(f"   Dénomination: {denom}")
    print(f"   Complément adresse: {complement if complement else '(vide)'}")
    print(f"   Adresse: {numero or ''} {type_v or ''} {libelle_v or ''}")
    print(f"   {cp} {commune}")
    print()

# Statistiques sur les compléments d'adresse
stats_query = """
SELECT 
    COUNT(*) as total,
    COUNT(CASE WHEN complement_adresse IS NOT NULL AND TRIM(complement_adresse) != '' THEN 1 END) as avec_complement,
    COUNT(*) - COUNT(CASE WHEN complement_adresse IS NOT NULL AND TRIM(complement_adresse) != '' THEN 1 END) as sans_complement,
    ROUND(
        100.0 * COUNT(CASE WHEN complement_adresse IS NOT NULL AND TRIM(complement_adresse) != '' THEN 1 END) / COUNT(*),
        2
    ) as pct_avec_complement
FROM (
    SELECT complement_adresse
    FROM read_parquet('data_parquet/sirene_silver.parquet')
    LIMIT 100
)
"""

stats = conn.execute(stats_query).fetchone()
print(f"\n{'='*120}")
print(f"Statistiques sur les 100 premiers éléments:")
print(f"  - Total: {stats[0]}")
print(f"  - Avec complément: {stats[1]}")
print(f"  - Sans complément: {stats[2]}")
print(f"  - Pourcentage avec complément: {stats[3]}%")
print(f"{'='*120}")

conn.close()
