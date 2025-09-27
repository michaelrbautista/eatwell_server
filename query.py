import sqlite3
import json
from db.search_service import get_candidates, rerank_with_embeddings
from helper import get_nutrients, map_nutrients, get_portions, map_portions
from models.meal_analysis import AnalysisIngredient

DB_PATH = "food.db"

def search_food(term: str, quantity: float):
    conn = sqlite3.connect(DB_PATH)
    candidates = get_candidates(term, conn)
    top_candidates = rerank_with_embeddings(term, candidates, conn, top_k=5)

    # Fetch full row data for the top-ranked candidate only
    if not top_candidates:
        conn.close()
        return None  # No match found

    best = top_candidates[0]  # first = closest match
    if best["similarity"] < 0.6:
        return {
        "food": "None",
        "similarity": 0.0
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

    # return {
    #     "food": food_data["description"],
    #     "similarity": round(float(best["similarity"]), 2)
    # }

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

with open("test_data.json", "r") as f:
    data = json.load(f)

test_vision_response = {
    "name": "Chicken salad",
    "ingredients": [
        {
            "name": "Yogurt",
            "quantity_in_grams": 150.0
        },
        {
            "name": "Kiwi",
            "quantity_in_grams": 50.0
        }
    ]
}

if __name__ == "__main__":
    food = search_food("greek yogurt", 100.0)
    # print(json.dumps(food, indent=4))
    # print(json.dumps(results, indent=4))
    print(food.model_dump_json(indent=4))
