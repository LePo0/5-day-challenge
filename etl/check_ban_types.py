import duckdb

con = duckdb.connect()
result = con.execute("""
SELECT 
    certification_commune, 
    typeof(certification_commune), 
    COUNT(*) as cnt
FROM 'data_parquet/ban_silver.parquet' 
GROUP BY 1, 2 
ORDER BY cnt DESC
LIMIT 10
""").fetchall()

for row in result:
    print(f"Value: {row[0]:<15} Type: {row[1]:<15} Count: {row[2]:,}")

con.close()
