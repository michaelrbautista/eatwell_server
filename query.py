import sqlite3
import json
from db.search_service import get_candidates, rerank_with_embeddings
from helper import get_nutrients, map_nutrients, get_portions, map_portions
from models.meal_analysis import AnalysisIngredient
import os
import re

# source venv/bin/activate

DB_PATH = os.getenv("DB_PATH", "food.db")

def normalize_text(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def search_food(term: str, quantity: float):
    conn = sqlite3.connect(DB_PATH)
    normalized_term = normalize_text(term)
    candidates = get_candidates(normalized_term, conn)
    top_candidates = rerank_with_embeddings(normalized_term, candidates, conn, top_k=5)

    if not top_candidates:
        conn.close()
        return None  # No match found
    
    for f in top_candidates:
        print({
            "fdc_id": f["fdc_id"],
            "food": f["description"],
            "similarity": f["similarity"]
        })
    print()

    best = top_candidates[0]  # first = closest match
    if best["similarity"] < 0.5:
        return {
            "is_valid": False,
            "name": term,
            "quantity_in_grams": quantity
        }

    cursor = conn.cursor()
    cursor.execute("""
        SELECT fdc_id, data_type, description, fermented_food_serving_size, CAST(collagen AS REAL) AS collagen
        FROM sr_legacy_food
        WHERE fdc_id = ?
    """, (best["fdc_id"],))
    food_row = cursor.fetchone()
    colnames = [desc[0] for desc in cursor.description]

    if not food_row:
        conn.close()
        return None

    food_data = dict(zip(colnames, food_row))

    # Get nutrient data
    nutrients = get_nutrients(conn, food_data["fdc_id"])
    mapped_nutrients = map_nutrients(nutrients, food_data)

    # Get portion data
    portions = get_portions(conn, food_data["fdc_id"])
    mapped_portions = map_portions(portions)

    # Get first portion
    selected_portion_id = 1
    selected_gram_weight = 100
    if len(mapped_portions) > 0:
        selected_portion_id = mapped_portions[0].id
        selected_gram_weight = mapped_portions[0].gram_weight

    ingredient = AnalysisIngredient(
        fdc_id=food_data["fdc_id"],
        description=food_data["description"],
        amount=round(quantity / selected_gram_weight, 2),
        selected_portion_id=selected_portion_id,
        portions=mapped_portions,
        nutrients=mapped_nutrients
    )

    conn.close()

    return ingredient

if __name__ == "__main__":
    ingredients = [
        "carrots"
    ]

    valid_results = []
    invalid_results = []
    for ingredient in ingredients:
        result = search_food(ingredient, 100.0)
        if isinstance(result, AnalysisIngredient):
            valid_results.append(result)
        else:
            invalid_results.append(result)
            
    # for result in valid_results:
    #     print()
    #     print(result.description)
    #     print(result.fdc_id)

    # print(json.dumps(valid_results, indent=4))
    # print(food.model_dump_json(indent=4))
