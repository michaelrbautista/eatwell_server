import pandas as pd
import sqlite3
import glob
import os
import re
import pyarrow.parquet as pq

DB_PATH = "../food.db"
OFF_PARQUET_PATH = "../food_us.parquet"

# How to create updated database
# 1. Download .csv from Google Sheets
# 2. Put .csv in Food Database/Prod folder
# 3. Run python clean_sr_legacy.py
# 4. Put cleaned data into /data folder
# 5. Run python filteroff.py to generate food_us.parquet
# 6. Run python database.py

# Upload food.db to Render
# cd /var/data
# change end of dropbox url to dl=1
# curl -L -o food.db "https://dropboxlink.com"

# --- Normalization helper ---
def normalize(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def normalize_text(text):
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _pick_localized_text(values, preferred_langs=("main", "en")):
    if not values:
        return None

    for lang in preferred_langs:
        for value in values:
            if value.get("lang") == lang and value.get("text"):
                return value["text"]

    for value in values:
        text = value.get("text")
        if text:
            return text

    return None


OFF_NUTRIENT_MAP = {
    "proteins": ("protein_100g", "g"),
    "leucine": ("leucine_100g", "g"),
    "carbohydrates": ("carbohydrates_100g", "g"),
    "fat": ("fat_100g", "g"),
    "fiber": ("fiber_100g", "g"),
    "sodium": ("sodium_100g", "mg"),
    "vitamin-c": ("vitamin_c_100g", "mg"),
    "vitamin-a": ("vitamin_a_100g", "ug"),
    "vitamin-e": ("vitamin_e_100g", "mg"),
    "vitamin-k": ("vitamin_k_100g", "ug"),
    "vitamin-b6": ("vitamin_b6_100g", "mg"),
    "vitamin-b12": ("vitamin_b12_100g", "ug"),
    "vitamin-b1": ("vitamin_b1_100g", "mg"),
    "vitamin-b2": ("vitamin_b2_100g", "mg"),
    "vitamin-b3": ("vitamin_b3_100g", "mg"),
    "pantothenic-acid": ("vitamin_b5_100g", "mg"),
    "folates": ("folate_100g", "ug"),
    "calcium": ("calcium_100g", "mg"),
    "iron": ("iron_100g", "mg"),
    "magnesium": ("magnesium_100g", "mg"),
    "phosphorus": ("phosphorus_100g", "mg"),
    "potassium": ("potassium_100g", "mg"),
    "zinc": ("zinc_100g", "mg"),
    "copper": ("copper_100g", "mg"),
    "manganese": ("manganese_100g", "mg"),
    "selenium": ("selenium_100g", "ug"),
    "omega-3-fat": ("omega3_100g", "g"),
}


def _normalize_mass_unit(unit):
    if not unit:
        return None

    normalized = str(unit).strip().lower()
    if normalized in {"µg", "ug", "mcg", "μg"}:
        return "ug"
    if normalized in {"g", "gram", "grams"}:
        return "g"
    if normalized in {"mg", "milligram", "milligrams"}:
        return "mg"
    if normalized in {"kg", "kilogram", "kilograms"}:
        return "kg"
    if normalized in {"l", "liter", "liters"}:
        return "l"
    if normalized in {"ml", "milliliter", "milliliters"}:
        return "ml"
    return normalized


def _mass_to_grams(value, unit):
    normalized = _normalize_mass_unit(unit)
    if normalized == "g":
        return float(value)
    if normalized == "mg":
        return float(value) / 1000.0
    if normalized == "ug":
        return float(value) / 1_000_000.0
    if normalized == "kg":
        return float(value) * 1000.0
    return None


def _grams_to_unit(value_in_grams, target_unit):
    normalized = _normalize_mass_unit(target_unit)
    if normalized == "g":
        return value_in_grams
    if normalized == "mg":
        return value_in_grams * 1000.0
    if normalized == "ug":
        return value_in_grams * 1_000_000.0
    if normalized == "kg":
        return value_in_grams / 1000.0
    return value_in_grams


def _extract_off_nutrient_amount(nutriments_by_name, nutrient_name, target_unit):
    item = nutriments_by_name.get(nutrient_name)
    if not item:
        return None

    value = item.get("value")
    if value is None:
        value = item.get("100g")

    if value is None:
        return None

    source_unit = item.get("unit") or item.get("value_unit") or item.get("unit_name")
    normalized_source_unit = _normalize_mass_unit(source_unit)
    normalized_target_unit = _normalize_mass_unit(target_unit)

    if normalized_source_unit and normalized_target_unit and normalized_source_unit == normalized_target_unit:
        return float(value)

    grams = _mass_to_grams(value, source_unit)
    if grams is None:
        return float(value)

    return _grams_to_unit(grams, target_unit)


def _derive_sodium_from_salt(nutriments_by_name):
    salt_item = nutriments_by_name.get("salt")
    if not salt_item:
        return None

    salt_value = salt_item.get("value")
    if salt_value is None:
        salt_value = salt_item.get("100g")

    if salt_value is None:
        return None

    salt_unit = salt_item.get("unit") or salt_item.get("value_unit") or salt_item.get("unit_name")

    # OFF commonly stores salt and sodium as mass units. Convert salt to grams,
    # derive sodium in grams, then convert to the sodium target unit (mg).
    salt_in_grams = _mass_to_grams(salt_value, salt_unit)
    if salt_in_grams is None:
        return None

    sodium_in_grams = salt_in_grams / 2.5
    return _grams_to_unit(sodium_in_grams, "mg")


def _coerce_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

# Remove old DB if you want a fresh build
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

# Connect (or create) SQLite database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# --- Import SR Legacy CSVs ---
csv_files = glob.glob("../data/*.csv")

for csv_file in csv_files:
    table_name = os.path.splitext(os.path.basename(csv_file))[0]
    print(f"Importing {csv_file} into table {table_name}...")
    df = pd.read_csv(csv_file)
    df.to_sql(table_name, conn, if_exists="replace", index=False)

# --- Create FTS5 index for SR Legacy ---
print("Creating FTS5 index for SR Legacy...")

cursor.execute("ALTER TABLE sr_legacy_food ADD COLUMN normalized_description TEXT;")

cursor.execute("SELECT fdc_id, description FROM sr_legacy_food WHERE description IS NOT NULL;")
rows = cursor.fetchall()

for fdc_id, desc in rows:
    norm = normalize_text(desc)
    cursor.execute(
        "UPDATE sr_legacy_food SET normalized_description = ? WHERE fdc_id = ?",
        (norm, fdc_id)
    )

cursor.execute("DROP TABLE IF EXISTS food_search;")
cursor.execute("""
    CREATE VIRTUAL TABLE food_search
    USING fts5(description, data_type, content='');
""")
cursor.execute("""
    INSERT INTO food_search(rowid, description, data_type)
    SELECT fdc_id, normalized_description, 'sr_legacy_food'
    FROM sr_legacy_food
    WHERE normalized_description IS NOT NULL;
""")

# --- Import OFF data from Parquet ---
print("Importing OFF data from Parquet...")

cursor.execute("DROP TABLE IF EXISTS off_food;")
cursor.execute("""
    CREATE TABLE off_food (
        code TEXT PRIMARY KEY,
        product_name TEXT,
        normalized_product_name TEXT,
        brands TEXT,
        normalized_brands TEXT,
        brand_product_name TEXT,
        categories TEXT,
        nova_group INTEGER,
        nutriscore_grade TEXT,
        ingredients_text TEXT,
        serving_size TEXT,
        serving_quantity REAL,
        -- nutrients per 100g
        protein_100g REAL,
        leucine_100g REAL,
        carbohydrates_100g REAL,
        fat_100g REAL,
        fiber_100g REAL,
        sodium_100g REAL,
        vitamin_c_100g REAL,
        vitamin_a_100g REAL,
        vitamin_e_100g REAL,
        vitamin_k_100g REAL,
        vitamin_b6_100g REAL,
        vitamin_b12_100g REAL,
        vitamin_b1_100g REAL,
        vitamin_b2_100g REAL,
        vitamin_b3_100g REAL,
        vitamin_b5_100g REAL,
        folate_100g REAL,
        calcium_100g REAL,
        iron_100g REAL,
        magnesium_100g REAL,
        phosphorus_100g REAL,
        potassium_100g REAL,
        zinc_100g REAL,
        copper_100g REAL,
        manganese_100g REAL,
        selenium_100g REAL,
        omega3_100g REAL,
        source TEXT DEFAULT 'off'
    );
""")

off_columns = [
    "code",
    "product_name",
    "brands",
    "categories",
    "nova_group",
    "nutriscore_grade",
    "ingredients_text",
    "serving_size",
    "serving_quantity",
    "nutriments",
]

off_parquet = pq.ParquetFile(OFF_PARQUET_PATH)
off_insert = []
off_loaded = 0

def _flush_off_rows(rows):
    if not rows:
        return
    cursor.executemany("""
        INSERT OR REPLACE INTO off_food (
            code, product_name, normalized_product_name, brands, normalized_brands, brand_product_name,
            categories, nova_group, nutriscore_grade, ingredients_text, serving_size, serving_quantity,
            protein_100g, leucine_100g, carbohydrates_100g, fat_100g, fiber_100g, sodium_100g,
            vitamin_c_100g, vitamin_a_100g, vitamin_e_100g, vitamin_k_100g,
            vitamin_b6_100g, vitamin_b12_100g, vitamin_b1_100g, vitamin_b2_100g,
            vitamin_b3_100g, vitamin_b5_100g, folate_100g, calcium_100g, iron_100g,
            magnesium_100g, phosphorus_100g, potassium_100g, zinc_100g, copper_100g,
            manganese_100g, selenium_100g, omega3_100g
        ) VALUES (
            ?,?,?,?,?,?,?,?,?,?,
            ?,?,?,?,?,?,?,?,?,?,
            ?,?,?,?,?,?,?,?,?,?,
            ?,?,?,?,?,?,?,?,?
        )
    """, rows)


for batch in off_parquet.iter_batches(columns=off_columns, batch_size=5000):
    for record in batch.to_pylist():
        code = record.get("code")
        product_name = _pick_localized_text(record.get("product_name"))
        if not code or not product_name:
            continue

        ingredient_text = _pick_localized_text(record.get("ingredients_text"), preferred_langs=("en", "main"))
        nutrient_items = record.get("nutriments") or []
        nutriments_by_name = {
            item.get("name"): item
            for item in nutrient_items
            if item and item.get("name")
        }

        nutrients = {
            column_name: _extract_off_nutrient_amount(nutriments_by_name, nutrient_name, target_unit)
            for nutrient_name, (column_name, target_unit) in OFF_NUTRIENT_MAP.items()
        }

        if nutrients["sodium_100g"] is None:
            nutrients["sodium_100g"] = _derive_sodium_from_salt(nutriments_by_name)

        brands_raw = record.get("brands")
        normalized_brands = normalize_text(brands_raw or "")
        normalized_product = normalize_text(product_name or "")
        brand_product_name = (normalized_brands + " " + normalized_product).strip()

        has_macros = any(nutrients[k] is not None for k in ("protein_100g", "fat_100g", "carbohydrates_100g"))

        if not has_macros:
            continue

        off_insert.append((
            code,
            product_name,
            normalized_product,
            brands_raw,
            normalized_brands,
            brand_product_name,
            record.get("categories"),
            record.get("nova_group"),
            record.get("nutriscore_grade"),
            ingredient_text,
            record.get("serving_size"),
            _coerce_float(record.get("serving_quantity")),
            nutrients["protein_100g"],
            nutrients["leucine_100g"],
            nutrients["carbohydrates_100g"],
            nutrients["fat_100g"],
            nutrients["fiber_100g"],
            nutrients["sodium_100g"],
            nutrients["vitamin_c_100g"],
            nutrients["vitamin_a_100g"],
            nutrients["vitamin_e_100g"],
            nutrients["vitamin_k_100g"],
            nutrients["vitamin_b6_100g"],
            nutrients["vitamin_b12_100g"],
            nutrients["vitamin_b1_100g"],
            nutrients["vitamin_b2_100g"],
            nutrients["vitamin_b3_100g"],
            nutrients["vitamin_b5_100g"],
            nutrients["folate_100g"],
            nutrients["calcium_100g"],
            nutrients["iron_100g"],
            nutrients["magnesium_100g"],
            nutrients["phosphorus_100g"],
            nutrients["potassium_100g"],
            nutrients["zinc_100g"],
            nutrients["copper_100g"],
            nutrients["manganese_100g"],
            nutrients["selenium_100g"],
            nutrients["omega3_100g"],
        ))
        off_loaded += 1

        if len(off_insert) >= 5000:
            _flush_off_rows(off_insert)
            off_insert.clear()

_flush_off_rows(off_insert)

print(f"  Loaded {off_loaded:,} OFF products")

cursor.execute("""
    SELECT
        COUNT(*) AS total_rows,
        SUM(
            CASE
                WHEN protein_100g IS NOT NULL
                  OR fat_100g IS NOT NULL
                  OR carbohydrates_100g IS NOT NULL
                  OR sodium_100g IS NOT NULL
                THEN 1
                ELSE 0
            END
        ) AS rows_with_macro_values
    FROM off_food
""")
total_rows, rows_with_macro_values = cursor.fetchone()
if total_rows and rows_with_macro_values == 0:
    raise RuntimeError("OFF import produced no populated macro nutrients; check nutriment mapping.")

print(f"  Inserted {off_loaded:,} rows into off_food")

# --- Create indexes for OFF search columns ---
print("Creating indexes...")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_off_normalized_product ON off_food(normalized_product_name);")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_off_normalized_brands ON off_food(normalized_brands);")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_off_brand_product ON off_food(brand_product_name);")

# --- Create FTS5 index for OFF ---
print("Creating FTS5 index for OFF...")

cursor.execute("DROP TABLE IF EXISTS off_food_search;")
cursor.execute("""
    CREATE VIRTUAL TABLE off_food_search
    USING fts5(product_name, brands, content='');
""")
cursor.execute("""
    INSERT INTO off_food_search(rowid, product_name, brands)
    SELECT rowid, normalized_product_name, normalized_brands
    FROM off_food
    WHERE normalized_product_name IS NOT NULL;
""")

conn.commit()
conn.close()
print("Database with FTS5 created successfully!")