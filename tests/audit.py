import duckdb

con = duckdb.connect("duckdb/catalog.db")

df = con.execute("""
SELECT
    upper(type_voie) AS type_voie,
    count(*) AS nb
FROM 'data_parquet/sirene.parquet'
WHERE type_voie IS NOT NULL
GROUP BY 1
ORDER BY nb DESC
""").fetchall()

print(df)
