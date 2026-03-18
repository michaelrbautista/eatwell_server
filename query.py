import sqlite3
import json
from query_service import get_candidates, rerank_with_embeddings
from helper import get_nutrients, map_nutrients, get_portions
from models.meal_analysis import AnalysisIngredient
import os
import re

# source venv/bin/activate

DB_PATH = os.getenv("DB_PATH", "food.db")

def normalize_text(text):
    text = text.lower()
    text = text.replace("-", " ")  # 🔹 convert hyphens to spaces
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def reorder_modifiers(term: str) -> str:
    # Cooking methods that should be preserved and reordered
    cooking_modifiers = {
        "grilled", "fried", "baked", "roasted", "boiled", "steamed", 
        "smoked", "poached", "seared", "broiled", "scrambled", "green",
        "red", "orange", "yellow"
    }

    # Form descriptors to remove completely
    form_descriptors = {
        "sliced", "slices", "diced", "chopped", "cubed", "minced",
        "pieces", "chunks", "wedges", "halves", "quarters", "shredded",
        "whole", "peeled", "fresh"
    }

    words = term.lower().replace(",", "").split()

    # Separate cooking modifiers, form descriptors, and base words
    cooking_mods = [w for w in words if w in cooking_modifiers]
    base_words = [w for w in words if w not in cooking_modifiers and w not in form_descriptors]

    if not base_words:
        return term.lower().strip()

    # Format to match USDA naming: "food, modifier"
    reordered = " ".join(base_words)
    if cooking_mods:
        reordered += ", " + " ".join(cooking_mods)

    return reordered.strip()

def try_exact_match(term: str, conn):
    cursor = conn.cursor()
    term_norm = term.lower().strip()
    
    # Try exact match
    cursor.execute("""
        SELECT fdc_id, 'sr_legacy_food' AS data_type, description
        FROM sr_legacy_food
        WHERE LOWER(description) = ?
        LIMIT 1
    """, (term_norm,))
    
    row = cursor.fetchone()
    if row:
        return {
            "fdc_id": row[0],
            "data_type": row[1],
            "description": row[2],
            "similarity": 1.0  # Perfect match
        }
    
    # Try exact match with common variations (comma-separated)
    # e.g., "chicken grilled" should match "chicken, grilled"
    words = term_norm.split()
    if len(words) >= 2:
        # Try last word as modifier: "chicken grilled" → "chicken, grilled"
        variant1 = f"{' '.join(words[:-1])}, {words[-1]}"
        cursor.execute("""
            SELECT fdc_id, 'sr_legacy_food' AS data_type, description
            FROM sr_legacy_food
            WHERE LOWER(description) = ?
            LIMIT 1
        """, (variant1,))
        
        row = cursor.fetchone()
        if row:
            return {
                "fdc_id": row[0],
                "data_type": row[1],
                "description": row[2],
                "similarity": 0.98  # Very close match
            }
        
        # Try first word as modifier: "grilled chicken" → "chicken, grilled"
        variant2 = f"{' '.join(words[1:])}, {words[0]}"
        cursor.execute("""
            SELECT fdc_id, 'sr_legacy_food' AS data_type, description
            FROM sr_legacy_food
            WHERE LOWER(description) = ?
            LIMIT 1
        """, (variant2,))
        
        row = cursor.fetchone()
        if row:
            return {
                "fdc_id": row[0],
                "data_type": row[1],
                "description": row[2],
                "similarity": 0.98
            }
    
    # Try prefix match (only if term is reasonably specific, 5+ chars)
    if len(term_norm) >= 5:
        cursor.execute("""
            SELECT fdc_id, 'sr_legacy_food' AS data_type, description
            FROM sr_legacy_food
            WHERE LOWER(description) LIKE ? || '%'
            LIMIT 1
        """, (term_norm,))
        
        row = cursor.fetchone()
        if row:
            return {
                "fdc_id": row[0],
                "data_type": row[1],
                "description": row[2],
                "similarity": 0.95  # Good prefix match
            }
    
    return None


def build_ingredient(best_match: dict, quantity: float, conn):
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
    """, (best_match["fdc_id"],))
    
    food_row = cursor.fetchone()
    if not food_row:
        return None
    
    colnames = [desc[0] for desc in cursor.description]
    food_data = dict(zip(colnames, food_row))
    
    # Get nutrient data
    nutrients = get_nutrients(conn, food_data["fdc_id"])
    mapped_nutrients = map_nutrients(nutrients, food_data)
    
    # Get portion data
    portions = get_portions(conn, food_data["fdc_id"])
    
    selected_portion_id = 0
    selected_gram_weight = 1.0
    
    ingredient = AnalysisIngredient(
        fdc_id=food_data["fdc_id"],
        description=food_data["description"],
        amount=round(quantity / selected_gram_weight, 2),
        selected_portion_id=selected_portion_id,
        portions=portions,
        nutrients=mapped_nutrients,
        processing_score=food_data.get("processing_score"),
        bioavailability_score=food_data.get("bioavailability_score"),
        quality_score=food_data.get("quality_score")
    )
    
    return ingredient




def search_food(term: str, quantity: float):
    conn = sqlite3.connect(DB_PATH)
    
    normalized_term = normalize_text(term)
    reordered_term = reorder_modifiers(normalized_term)
    
    # 🚀 FAST PATH: Try exact match first (no embedding call needed)
    exact_match = try_exact_match(reordered_term, conn)
    if exact_match and exact_match["similarity"] >= 0.95:
        result = build_ingredient(exact_match, quantity, conn)
        conn.close()
        return result
    
    # SLOW PATH: No exact match, use embeddings
    candidates = get_candidates(reordered_term, conn)
    
    top_candidates = rerank_with_embeddings(reordered_term, candidates, conn, top_k=5)
    
    if not top_candidates:
        conn.close()
        return None
    
    # print()
    # for f in top_candidates:
    #     print({
    #         "fdc_id": f["fdc_id"],
    #         "food": f["description"],
    #         "similarity": f["similarity"]
    #     })
    # print()
    
    best = top_candidates[0]
    if best["similarity"] < 0.5:
        conn.close()
        return {
            "is_valid": False,
            "name": term,
            "quantity_in_grams": quantity
        }
    
    result = build_ingredient(best, quantity, conn)
    conn.close()
    return result

if __name__ == "__main__":
    ingredients = [
        "Green apple slices"
    ]

    valid_results = []
    for ingredient in ingredients:
        result = search_food(ingredient, 100.0)
        if isinstance(result, AnalysisIngredient):
            valid_results.append(result)
            
    print()
    for result in valid_results:
        print(result.description)
        print(result.fdc_id)
    print()

    # print(json.dumps(valid_results, indent=4))
    # print(food.model_dump_json(indent=4))
