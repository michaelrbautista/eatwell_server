import pandas as pd
import sqlite3
import glob
import os
import re

DB_PATH = "../food.db"

# Upload food.db to Render
# cd /var/data
# curl -L -o food.db "https://dropboxlink.com"

# --- Normalization helper ---
def normalize(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

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

# Add normalized_description column
cursor.execute("ALTER TABLE sr_legacy_food ADD COLUMN normalized_description TEXT;")

def normalize_text(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

cursor.execute("SELECT fdc_id, description FROM sr_legacy_food WHERE description IS NOT NULL;")
rows = cursor.fetchall()

for fdc_id, desc in rows:
    norm = normalize_text(desc)
    cursor.execute(
        "UPDATE sr_legacy_food SET normalized_description = ? WHERE fdc_id = ?",
        (norm, fdc_id)
    )

# Drop if exists (for rebuilds)
cursor.execute("DROP TABLE IF EXISTS food_search;")

# Create virtual FTS table linked to Food
cursor.execute("""
    CREATE VIRTUAL TABLE food_search
    USING fts5(description, data_type, content='');
""")

# cursor.execute("""
#     INSERT INTO food_search(rowid, description, data_type)
#     SELECT fdc_id, description, 'sr_legacy_food'
#     FROM sr_legacy_food
#     WHERE description IS NOT NULL;
# """)

cursor.execute("""
    INSERT INTO food_search(rowid, description, data_type)
    SELECT fdc_id, normalized_description, 'sr_legacy_food'
    FROM sr_legacy_food
    WHERE normalized_description IS NOT NULL;
""")

# print("First 5 rows of sr_legacy_food:")
# cursor.execute("SELECT * FROM sr_legacy_food LIMIT 5;")
# rows = cursor.fetchall()
# for row in rows:
#     print(row)

conn.commit()
conn.close()
print("Database with FTS5 created successfully!")
