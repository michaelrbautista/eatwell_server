from fastapi import FastAPI, HTTPException, Query
from openai import OpenAI
import uvicorn
import os
from dotenv import load_dotenv
from pydantic import BaseModel
import json
from query_service import fts_search, fuzzy_search
from query import search_food
from helper import get_nutrients, map_nutrients, get_portions, map_portions, calculate_protein, calculate_leucine, calculate_carbohydrates, calculate_omega3s, calculate_fat, calculate_iron, calculate_zinc, calculate_fermented_food_servings, calculate_fiber, calculate_collagen, calculate_vitamin_c, calculate_vitamin_a, calculate_vitamin_e, calculate_selenium, calculate_quality_score
from models.meal_analysis import AnalysisIngredient, AnalysisMeal
import sqlite3
import re
from rapidfuzz import fuzz

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
            model="gpt-4o",
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
                            1. Identify all visible foods in the image, using the most natural, specific food names you would give to a person (e.g. call diced steak simply "steak" instead of "beef cubes").
                            2. If the meal consists of distinct, separable foods, return each ingredient.
                                - - If a visible item is a simple combination of distinct ingredients (e.g. avocado toast → toast + avocado, bread with butter → bread + butter), list the individual ingredients instead of the combined food name.
                            3. If the meal is a composite food made of multiple ingredients (e.g. muffin, pizza, sandwich, smoothie, pasta, burrito, soup, etc), return that food’s **name** and **nutrients** in the format below. Base the quality_score from 0 to 100 based on how processed the food is and the bioavailabiltity of its nutrients.
                            4. Output format:
                                - **If the meal has distinct ingredients:**
                                {
                                    "name": "Chicken and rice",
                                    "ingredients": [
                                        {"name": "Grilled chicken thigh", "quantity_in_grams": 100.0},
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

    # return analysis
    meal_name = analysis["name"]

    is_composite = "protein_in_grams" in analysis

    if is_composite:
        return AnalysisMeal(
            name=meal_name,
            ingredients_new=[],
            protein_float=analysis["protein_in_grams"],
            leucine_float=analysis["leucine_in_grams"],
            carbohydrates_float=analysis["carbohydrates_in_grams"],
            omega3s_float=analysis["omega3s_in_grams"],
            fat_float=analysis["fat_in_grams"],
            iron_float=analysis["iron_in_milligrams"],
            zinc_float=analysis["zinc_in_milligrams"],
            fermented_food_servings_float=analysis["fermented_food_servings"],
            fiber_float=analysis["fiber_in_grams"],
            collagen_float=analysis["collagen_in_grams"],
            vitamin_c_float=analysis["vitamin_c_in_milligrams"],
            vitamin_a_float=analysis["vitamin_a_in_micrograms"],
            vitamin_e_float=analysis["vitamin_e_in_milligrams"],
            selenium_float=analysis["selenium_in_micrograms"],
            quality_score=analysis["quality_score"]
        )
    else:
        # Query database
        ingredients = analysis["ingredients"]

        print(ingredients)

        valid_results = []
        for food in ingredients:
            result = search_food(food["name"], food["quantity_in_grams"])
            if isinstance(result, AnalysisIngredient):
                valid_results.append(result)

        return AnalysisMeal(
            name=meal_name,
            ingredients_new=valid_results,
            protein_float=calculate_protein(valid_results),
            leucine_float=calculate_leucine(valid_results),
            carbohydrates_float=calculate_carbohydrates(valid_results),
            omega3s_float=calculate_omega3s(valid_results),
            fat_float=calculate_fat(valid_results),
            iron_float=calculate_iron(valid_results),
            zinc_float=calculate_zinc(valid_results),
            fermented_food_servings_float=calculate_fermented_food_servings(valid_results),
            fiber_float=calculate_fiber(valid_results),
            collagen_float=calculate_collagen(valid_results),
            vitamin_c_float=calculate_vitamin_c(valid_results),
            vitamin_a_float=calculate_vitamin_a(valid_results),
            vitamin_e_float=calculate_vitamin_e(valid_results),
            selenium_float=calculate_selenium(valid_results),
            quality_score=calculate_quality_score(valid_results)
        )

# Helper function
def extract_json_from_code_block(text: str) -> str:
    """
    Extracts raw JSON from a markdown-formatted code block (e.g. ```json\n...\n```)
    """
    if text.startswith("```json") or text.startswith("```"):
        # Remove the triple backticks and optional 'json' language label
        lines = text.strip().split('\n')
        if len(lines) >= 3:
            return '\n'.join(lines[1:-1])  # Remove first and last line
    return text.strip()

# --------------------------------------------------------------------------------
# Custom food
# --------------------------------------------------------------------------------

@app.post("/custom-food")
async def custom_food(name: str, amount: float, modifier: str):
    try:
        chat_completion = client.beta.chat.completions.parse(
            model="gpt-4o",
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
               CAST(bioavailability_score AS REAL) AS bioavailability_score,
               CAST(quality_score AS REAL) AS quality_score
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
        quality_score=food_data.get("quality_score")
    )

    conn.close()
    return ingredient

# --------------------------------------------------------------------------------
# Search for food (analysis)
# --------------------------------------------------------------------------------

@app.post("/search-foods")
async def search_foods(term: str):
    DB_PATH = os.getenv("DB_PATH", "food.db")
    
    conn = sqlite3.connect(DB_PATH)
    fts_results = fts_search(term, conn, limit=10)
    fuzzy_results = fuzzy_search(term, conn, limit=10)

    seen = set()
    candidates = []
    for fdc_id, data_type, description in fts_results + fuzzy_results:
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
                CAST(bioavailability_score AS REAL) AS bioavailability_score,
                CAST(quality_score AS REAL) AS quality_score
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
            "quality_score": row[2] if row else None,
        })

    conn.close()
    return {
        "foods": foods
    }

# --------------------------------------------------------------------------------
# Search for food (database)
# --------------------------------------------------------------------------------

@app.post("/search-database")
async def search_database(term: str, limit: int = Query(10, ge=1, le=50)):
    if not term or not term.strip():
        return {"foods": []}

    db_path = os.getenv("DB_PATH", "food.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT fdc_id, 'sr_legacy_food' AS data_type, description
        FROM sr_legacy_food
        WHERE LOWER(description) = ?
        LIMIT 5
    """, (term.lower().strip(),))
    exact_matches = cursor.fetchall()
    combined_results = exact_matches + fts_search(term, conn, limit=limit) + fuzzy_search(term, conn, limit=limit)
    candidates = _dedupe_candidates(combined_results)
    ranked = _rank_candidates(term, candidates, limit)
    foods = _score_candidates(conn, ranked)
    conn.close()
    return {"foods": foods}

def _normalize_search_text(value: str) -> str:
    cleaned = value.lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def _dedupe_candidates(results: list[tuple[int, str, str]]) -> list[dict]:
    seen = set()
    candidates = []
    for fdc_id, data_type, description in results:
        key = (fdc_id, data_type)
        if key not in seen:
            candidates.append({"fdc_id": fdc_id, "data_type": data_type, "description": description})
            seen.add(key)
    return candidates

def _rank_candidates(term: str, candidates: list[dict], limit: int) -> list[dict]:
    normalized_term = _normalize_search_text(term)
    term_tokens = set(normalized_term.split()) if normalized_term else set()

    scored = []
    for candidate in candidates:
        desc_norm = _normalize_search_text(candidate["description"])
        score = 0.0
        if normalized_term and desc_norm == normalized_term:
            score += 50
        if normalized_term and desc_norm.startswith(normalized_term):
            score += 30
        if term_tokens and term_tokens.issubset(set(desc_norm.split())):
            score += 20
        ratio = fuzz.token_sort_ratio(normalized_term, desc_norm) / 100 if normalized_term else 0
        score += ratio * 10
        scored.append({**candidate, "rank_score": score})

    scored.sort(key=lambda c: c["rank_score"], reverse=True)
    return scored[:limit]

def _score_candidates(conn: sqlite3.Connection, candidates: list[dict]) -> list[dict]:
    cursor = conn.cursor()
    foods = []
    for candidate in candidates:
        cursor.execute("""
            SELECT
                CAST(processing_score AS REAL) AS processing_score,
                CAST(bioavailability_score AS REAL) AS bioavailability_score,
                CAST(quality_score AS REAL) AS quality_score
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
            "quality_score": row[2] if row else None,
        })
    return foods

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
