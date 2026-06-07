from fastapi import FastAPI, HTTPException, Query
from openai import OpenAI
import uvicorn
import os
from dotenv import load_dotenv
from pydantic import BaseModel
import json
from query_service import get_usda_search_candidates
from query_utils import search_food, _build_nonempty_choices
from helper import get_nutrients, map_nutrients, get_portions, map_portions
from models.meal_analysis import AnalysisIngredient, AnalysisMeal
import sqlite3
import re
import json
from rapidfuzz import fuzz, process
from helperoff import get_off_nutrients, get_off_portions
from meal_analysis_service import (
    TextMealAnalysisRequest,
    analyze_text_meal_description,
    build_analysis_meal,
    extract_json_from_code_block,
)

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Create a FastAPI app
app = FastAPI()

# source venv/bin/activate
# uvicorn debug:app --reload




# --------------------------------------------------------------------------------
# Analyze image (updated)
# --------------------------------------------------------------------------------

class AnalyzeImageRequest(BaseModel):
    image_url: str

@app.post("/meal-updated")
async def analyze_meal_updated(payload: AnalyzeImageRequest):
    # Get list of ingredients
    try:
        vision_completion = client.chat.completions.create(
            model="gpt-5.2",
            messages=[
                {
                    "role": "system",
                    "content": "You are a nutrition expert and computer vision assistant."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """
                            Analyze this image and follow these steps:
                            1. Identify all visible foods in the image, using natural food names ("steak", "white rice", "avocado", "boiled eggs", etc).
                            2. If the meal consists of distinct, separable foods, return each ingredient.
                                - - If a visible item is a simple combination of distinct ingredients (e.g. avocado toast → toast + avocado, bread with butter → bread + butter), list the individual ingredients instead of the combined food name.
                            3. If the meal is a composite food made of multiple ingredients (e.g. muffin, pizza, sandwich, smoothie, pasta, burrito, soup, etc), return that food’s **name** and **nutrients** in the format below. Base the quality_score from 0 to 100 based on how processed the food is and the bioavailabiltity of its nutrients.
                            4. Output format:
                                - **If the meal has distinct ingredients:**
                                {
                                    "name": "Chicken and rice",
                                    "ingredients": [
                                        {"name": "Chicken thigh", "quantity_in_grams": 100.0},
                                        {"name": "White rice", "quantity_in_grams": 80.0}
                                    ]
                                }
                                - **If the meal contains a processed/composite food (only return this):**
                                {
                                    "name": "Muffin",
                                    "protein_in_grams": 7.2,
                                    "leucine_in_grams": 0.4,
                                    "carbohydrates_in_grams": 42.5,
                                    "omega3s_in_grams": 0.1,
                                    "fat_in_grams": 12.4,
                                    "iron_in_milligrams": 1.3,
                                    "zinc_in_milligrams": 0.8,
                                    "fermented_food_servings": 0.0,
                                    "fiber_in_grams": 2.8,
                                    "collagen_in_grams": 0.0,
                                    "vitamin_c_in_milligrams": 0.0,
                                    "vitamin_a_in_micrograms": 21.0,
                                    "vitamin_e_in_milligrams": 0.5,
                                    "selenium_in_micrograms": 9.0,
                                    "vitamin_b12_in_micrograms": 0.0,
                                    "vitamin_b6_in_milligrams": 0.0,
                                    "copper_in_milligrams": 0.0,
                                    "folate_in_micrograms": 0.0,
                                    "sodium_in_milligrams": 0.0,
                                    "potassium_in_milligrams": 0.0,
                                    "magnesium_in_milligrams": 0.0,
                                    "vitamin_b1_in_milligrams": 0.0,
                                    "vitamin_b2_in_milligrams": 0.0,
                                    "vitamin_b3_in_milligrams": 0.0,
                                    "vitamin_b5_in_milligrams": 0.0,
                                    "vitamin_k_in_micrograms": 0.0,
                                    "calcium_in_milligrams": 0.0,
                                    "manganese_in_milligrams": 0.0,
                                    "phosphorus_in_milligrams": 0.0,
                                    "quality_score": 30.0
                                }
                            5. If no food is visible, return exactly:
                                {
                                    "name": "Unknown",
                                    "ingredients": []
                                }
                            6. All numeric values must be floats. Return only valid JSON — no extra text or explanations.
                            """
                        },
                        {
                            "type": "image_url", 
                            "image_url": {"url": payload.image_url}
                        },
                    ],
                }
            ]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vision API call failed: {str(e)}")
    
    # Format response from OpenAI
    analysis_response = vision_completion.choices[0].message.content.strip()
    analysis_string = extract_json_from_code_block(analysis_response)

    try:
        analysis = json.loads(analysis_string)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse vision response: {e}")

    return build_analysis_meal(analysis, search_food_fn=search_food)


@app.post("/meal-description")
async def analyze_meal_description(payload: TextMealAnalysisRequest):
    description = payload.description.strip()
    if not description:
        raise HTTPException(status_code=400, detail="Description cannot be empty.")

    return analyze_text_meal_description(client, description, search_food_fn=search_food)

# --------------------------------------------------------------------------------
# Custom food
# --------------------------------------------------------------------------------

@app.post("/custom-food")
async def custom_food(name: str, amount: float, modifier: str):
    try:
        chat_completion = client.beta.chat.completions.parse(
            model="gpt-5.2",
            messages=[
                {
                    "role": "user",
                    "content": f"Give me a food object for {name} like the USDA Food Central database. Set 'fdc_id' to 1 and the 'amount' field to 1.0. Create one portion for {amount} {modifier} with the appropriate gram_weight for that portion size. Provide nutrient values per 100 grams of {name}. Base the quality_score from 0 to 100 based on how processed the food is and the bioavailabiltity of its nutrients."
                }
            ],
            response_format=AnalysisIngredient
        )
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"Nutrient analysis failed: {str(e)}")
    
    return chat_completion.choices[0].message.parsed

# --------------------------------------------------------------------------------
# Get food details
# --------------------------------------------------------------------------------

@app.get("/food/{fdc_id}")
async def food_details(fdc_id: int):
    DB_PATH = os.getenv("DB_PATH", "food.db")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT fdc_id, data_type, description,
               fermented_food_serving_size,
               CAST(collagen AS REAL) AS collagen,
               CAST(processing_score AS REAL) AS processing_score,
               CAST(bioavailability_score AS REAL) AS bioavailability_score
        FROM sr_legacy_food
        WHERE fdc_id = ?
    """, (fdc_id,))
    food_row = cursor.fetchone()
    colnames = [desc[0] for desc in cursor.description]

    if not food_row:
        conn.close()
        return None

    food_data = dict(zip(colnames, food_row))

    # --- 3. Nutrients (cast nutrient_nbr to INTEGER) ---
    food_data["food_nutrients"] = get_nutrients(conn, fdc_id)

    # --- 4. Portions ---
    food_data["food_portions"] = get_portions(conn, fdc_id)

    # Get nutrient data
    nutrients = get_nutrients(conn, fdc_id)
    mapped_nutrients = map_nutrients(nutrients, food_data)

    # Get portion data
    portions = get_portions(conn, fdc_id)
    mapped_portions = map_portions(portions)

    # Get first portion
    selected_portion_id = 1
    if len(mapped_portions) > 0:
        selected_portion_id = mapped_portions[0].id

    ingredient = AnalysisIngredient(
        fdc_id=food_data["fdc_id"],
        description=food_data["description"],
        amount=1.0,
        selected_portion_id=selected_portion_id,
        portions=mapped_portions,
        nutrients=mapped_nutrients,
        processing_score=food_data.get("processing_score"),
        bioavailability_score=food_data.get("bioavailability_score"),
        quality_score=food_data.get("processing_score")
    )

    conn.close()
    return ingredient

@app.get("/food/off/{code}")
async def off_food_details(code: str):
    DB_PATH = os.getenv("DB_PATH", "food.db")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM off_food WHERE code = ?", (code,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    colnames = [desc[0] for desc in cursor.description]
    food = dict(zip(colnames, row))

    nutrients = get_off_nutrients(food)
    portions = get_off_portions(food)

    return AnalysisIngredient(
        fdc_id=0,           # OFF foods don't have an fdc_id; Swift side uses `code`
        description=food["product_name"],
        amount=1.0,
        selected_portion_id=portions[0].id if portions else 0,
        portions=portions,
        nutrients=nutrients,
        processing_score=None,
        bioavailability_score=None,
        quality_score=None
    )

# --------------------------------------------------------------------------------
# Search for food (analysis)
# --------------------------------------------------------------------------------

@app.post("/search-foods")
async def search_foods(term: str):
    DB_PATH = os.getenv("DB_PATH", "food.db")
    
    conn = sqlite3.connect(DB_PATH)
    usda_results = get_usda_search_candidates(term, conn, limit=10)

    seen = set()
    candidates = []
    for fdc_id, data_type, description in usda_results:
        key = (fdc_id, data_type)
        if key not in seen:
            candidates.append({"fdc_id": fdc_id, "data_type": data_type, "description": description})
            seen.add(key)

    cursor = conn.cursor()
    foods = []
    for candidate in candidates:
        cursor.execute("""
            SELECT
                CAST(processing_score AS REAL) AS processing_score,
                CAST(bioavailability_score AS REAL) AS bioavailability_score
            FROM sr_legacy_food
            WHERE fdc_id = ?
        """, (candidate["fdc_id"],))
        row = cursor.fetchone()
        foods.append({
            "fdc_id": candidate["fdc_id"],
            "data_type": candidate["data_type"],
            "description": candidate["description"],
            "processing_score": row[0] if row else None,
            "bioavailability_score": row[1] if row else None,
            "quality_score": row[0] if row else None,
        })

    conn.close()
    return {
        "foods": foods
    }

# --------------------------------------------------------------------------------
# Search for food (split USDA + OFF)
# --------------------------------------------------------------------------------

@app.post("/search-database-v2")
async def search_foods_split(term: str):
    DB_PATH = os.getenv("DB_PATH", "food.db")

    conn = sqlite3.connect(DB_PATH)
    usda_results = _search_usda_foods(term, conn, limit=20)
    off_results = _search_off_foods(term, conn, limit=20)
    conn.close()

    return {
        "usda_foods": usda_results,
        "off_foods": off_results
    }

def _search_usda_foods(term: str, conn, limit: int = 20) -> list[dict]:
    """
    Search strategy:
    1. Exact and USDA-style prefix matches first
    2. FTS (BM25)
    3. Fuzzy fallback
    4. Dedup, fetch processing_score in one batch query
    """
    term = term.strip()
    if not term:
        return []

    usda_results = get_usda_search_candidates(term, conn, limit=limit)

    seen = set()
    candidates = []
    for row in usda_results:
        fdc_id = row[0]
        if fdc_id not in seen:
            candidates.append({"fdc_id": fdc_id, "data_type": row[1], "description": row[2]})
            seen.add(fdc_id)

    if not candidates:
        return []

    # Batch fetch processing_score instead of one query per food
    fdc_ids = [c["fdc_id"] for c in candidates]
    placeholders = ",".join("?" * len(fdc_ids))
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT
            fdc_id,
            CAST(processing_score AS REAL) AS processing_score,
            CAST(bioavailability_score AS REAL) AS bioavailability_score
        FROM sr_legacy_food
        WHERE fdc_id IN ({placeholders})
        """,
        fdc_ids,
    )
    scores = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

    return [
        {
            **c,
            "processing_score": scores.get(c["fdc_id"], (None, None))[0],
            "bioavailability_score": scores.get(c["fdc_id"], (None, None))[1],
            "quality_score": scores.get(c["fdc_id"], (None, None))[0],
        }
        for c in candidates
    ][:limit]

def _normalize_off_search_text(value: str) -> str:
    cleaned = value.lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

# Keep the search projection narrow so `/search-foods-v2` only exposes the
# product identity fields. The detail endpoint uses the full projection below.
OFF_SEARCH_COLUMNS = """
    rowid, code, product_name, brands
"""

OFF_DETAIL_COLUMNS = """
    rowid, code, product_name, brands, categories, nova_group, nutriscore_grade,
    ingredients_text, serving_size, serving_quantity,
    protein_100g, leucine_100g, carbohydrates_100g, fat_100g, fiber_100g,
    sodium_100g, vitamin_c_100g, vitamin_a_100g, vitamin_e_100g, vitamin_k_100g,
    vitamin_b6_100g, vitamin_b12_100g, vitamin_b1_100g, vitamin_b2_100g,
    vitamin_b3_100g, vitamin_b5_100g, folate_100g, calcium_100g, iron_100g,
    magnesium_100g, phosphorus_100g, potassium_100g, zinc_100g, copper_100g,
    manganese_100g, selenium_100g, omega3_100g
"""

def _search_off_foods(term: str, conn, limit: int = 20) -> list[dict]:
    normalized_term = _normalize_off_search_text(term)
    if not normalized_term:
        return []

    cursor = conn.cursor()
    foods_by_key: dict[int, dict] = {}

    def _fetch_and_store(rowids: list[int]):
        unseen = [r for r in rowids if r not in foods_by_key]
        if not unseen:
            return
        placeholders = ",".join("?" * len(unseen))
        cursor.execute(f"SELECT {OFF_SEARCH_COLUMNS} FROM off_food WHERE rowid IN ({placeholders})", unseen)
        for row in cursor.fetchall():
            if row[0] not in foods_by_key:
                foods_by_key[row[0]] = _format_off_search_row(row)

    def _exclude_clause():
        if not foods_by_key:
            return "NULL", []
        return ",".join("?" * len(foods_by_key)), list(foods_by_key.keys())

    def _fts_query(extra_limit: int):
        prefix_term = " ".join(f'"{w}"*' for w in normalized_term.split())
        exclude, exclude_ids = _exclude_clause()
        for query in [prefix_term, normalized_term]:
            if len(foods_by_key) >= limit:
                return
            try:
                cursor.execute(f"""
                    SELECT f.rowid
                    FROM off_food_search s
                    JOIN off_food f ON f.rowid = s.rowid
                    WHERE s.off_food_search MATCH ?
                      AND f.rowid NOT IN ({exclude})
                    ORDER BY bm25(s.off_food_search)
                    LIMIT ?
                """, (query, *exclude_ids, extra_limit))
                _fetch_and_store([r[0] for r in cursor.fetchall()])
                if foods_by_key:
                    return
            except Exception:
                continue

    # Tier 1: exact match on brand_product_name
    cursor.execute(f"""
        SELECT {OFF_SEARCH_COLUMNS} FROM off_food
        WHERE brand_product_name = ?
        LIMIT ?
    """, (normalized_term, limit))
    for row in cursor.fetchall():
        foods_by_key[row[0]] = _format_off_search_row(row)

    # Tier 2: prefix match on brand_product_name
    # Covers "chobani greek" → "chobani greek yogurt mango" and "greek yogurt" → same
    if len(foods_by_key) < limit:
        cursor.execute(f"""
            SELECT {OFF_SEARCH_COLUMNS} FROM off_food
            WHERE brand_product_name LIKE ? || '%'
              AND brand_product_name != ?
            LIMIT ?
        """, (normalized_term, normalized_term, limit - len(foods_by_key)))
        for row in cursor.fetchall():
            if row[0] not in foods_by_key:
                foods_by_key[row[0]] = _format_off_search_row(row)

    # Tier 3: prefix match on normalized_product_name alone
    # Catches cases where brand isn't part of the query
    if len(foods_by_key) < limit:
        exclude, exclude_ids = _exclude_clause()
        cursor.execute(f"""
            SELECT {OFF_SEARCH_COLUMNS} FROM off_food
            WHERE normalized_product_name LIKE ? || '%'
              AND rowid NOT IN ({exclude})
            LIMIT ?
        """, (normalized_term, *exclude_ids, limit - len(foods_by_key)))
        for row in cursor.fetchall():
            if row[0] not in foods_by_key:
                foods_by_key[row[0]] = _format_off_search_row(row)

    # Tier 4: FTS across product_name + brands (handles multi-word, out-of-order queries)
    if len(foods_by_key) < limit:
        _fts_query(limit - len(foods_by_key))

    # Tier 5: fuzzy over FTS candidates — never a full table scan
    if len(foods_by_key) < limit:
        try:
            cursor.execute("""
                SELECT
                    s.rowid,
                    COALESCE(f.product_name, '') || ' ' || COALESCE(f.brands, '') AS combined
                FROM off_food_search s
                JOIN off_food f ON f.rowid = s.rowid
                WHERE s.off_food_search MATCH ?
                ORDER BY bm25(s.off_food_search)
                LIMIT 200
            """, (normalized_term,))
            candidates = cursor.fetchall()
        except Exception:
            candidates = []

        if candidates:
            choices = _build_nonempty_choices(candidates)
            matches = process.extract(
                normalized_term, choices,
                scorer=fuzz.token_sort_ratio,
                limit=limit - len(foods_by_key),
            )
            _fetch_and_store([
                rowid for _, score, rowid in matches
                if score >= 60 and rowid not in foods_by_key
            ])

    return list(foods_by_key.values())[:limit]


def _format_off_search_row(row) -> dict:
    rowid, code, product_name, brands = row

    return {
        "fdc_id": rowid,
        "code": code,
        "data_type": "Open Food Facts",
        "product_name": product_name,
        "brands": brands or "Open Food Facts",
    }

# --------------------------------------------------------------------------------
# Search for food (database)
# --------------------------------------------------------------------------------

@app.post("/search-database")
async def search_database(term: str, limit: int = Query(20, ge=1, le=50)):
    if not term or not term.strip():
        return {"foods": []}

    db_path = os.getenv("DB_PATH", "food.db")
    conn = sqlite3.connect(db_path)
    usda_results = get_usda_search_candidates(term, conn, limit=limit)
    candidates = _dedupe_candidates(usda_results)
    foods = _score_candidates(conn, candidates)
    conn.close()
    return {"foods": foods}

def _dedupe_candidates(results: list[tuple[int, str, str]]) -> list[dict]:
    seen = set()
    candidates = []
    for fdc_id, data_type, description in results:
        key = (fdc_id, data_type)
        if key not in seen:
            candidates.append({"fdc_id": fdc_id, "data_type": data_type, "description": description})
            seen.add(key)
    return candidates

def _score_candidates(conn: sqlite3.Connection, candidates: list[dict]) -> list[dict]:
    if not candidates:
        return []

    fdc_ids = [c["fdc_id"] for c in candidates]
    placeholders = ",".join("?" * len(fdc_ids))
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT fdc_id, CAST(processing_score AS REAL) FROM sr_legacy_food WHERE fdc_id IN ({placeholders})",
        fdc_ids,
    )
    scores = {row[0]: row[1] for row in cursor.fetchall()}

    return [
        {
            "fdc_id": c["fdc_id"],
            "data_type": c["data_type"],
            "description": c["description"],
            "processing_score": scores.get(c["fdc_id"]),
            "quality_score": scores.get(c["fdc_id"]),
        }
        for c in candidates
    ]

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
