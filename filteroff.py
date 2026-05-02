import duckdb

con = duckdb.connect()

con.execute("""
    COPY (
        SELECT *
        FROM 'food.parquet'
        WHERE list_contains(countries_tags, 'en:united-states')
    )
    TO 'food_us.parquet' (FORMAT 'parquet', COMPRESSION 'zstd')
""")

result = con.execute("SELECT COUNT(*) FROM 'food_us.parquet'").fetchone()
print(f"US foods: {result[0]:,}")

con.close()