import pandas as pd
import sqlite3
import glob
import os

DB_PATH = "../food.db"

# Remove old DB if you want a fresh build
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

# Connect (or create) SQLite database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# List of CSV files (adjust path)
csv_files = glob.glob("../data/*.csv")

for csv_file in csv_files:
    # Use the filename (without extension) as table name
    table_name = os.path.splitext(os.path.basename(csv_file))[0]
    print(f"Importing {csv_file} into table {table_name}...")
    
    # Load CSV into DataFrame
    df = pd.read_csv(csv_file)
    
    # Write to SQLite
    df.to_sql(table_name, conn, if_exists="replace", index=False)

# --- Create FTS5 virtual table for Food descriptions ---
print("Creating FTS5 index...")

# Drop if exists (for rebuilds)
cursor.execute("DROP TABLE IF EXISTS food_search;")

# Create virtual FTS table linked to Food
cursor.execute("""
    CREATE VIRTUAL TABLE food_search
    USING fts5(description, data_type, content='');
""")

# Insert Foundation foods
# cursor.execute("""
#     INSERT INTO food_search(rowid, description, data_type)
#     SELECT fdc_id, description, 'foundation_food'
#     FROM foundation_food
#     WHERE description IS NOT NULL;
# """)

# Insert SR Legacy foods
cursor.execute("""
    INSERT INTO food_search(rowid, description, data_type)
    SELECT fdc_id, description, 'sr_legacy_food'
    FROM sr_legacy_food
    WHERE description IS NOT NULL;
""")

conn.commit()
conn.close()
print("Database with FTS5 created successfully!")
