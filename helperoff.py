import os
import sqlite3

from models.meal_analysis import AllNutrients, FoodPortion, AnalysisIngredient

def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def get_off_food_by_code(conn, code: str):
    """
    Fetch a single OFF food row by `code` and return it as a dict.
    Returns None when no matching row exists.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT *
        FROM off_food
        WHERE code = ?
        LIMIT 1
    """, (code,))

    row = cursor.fetchone()
    if not row:
        return None

    colnames = [desc[0] for desc in cursor.description]
    return dict(zip(colnames, row))


def get_off_nutrients(food: dict) -> AllNutrients:
    """Map flat off_food columns → AllNutrients. All values are per 100g."""
    def v(key):
        return food.get(key) or 0.0

    def micronutrient_value(key):
        raw = food.get(key)
        if raw is None:
            return 0.0

        try:
            return float(raw)
        except (TypeError, ValueError):
            return 0.0

    return AllNutrients(
        protein_in_grams=v("protein_100g"),
        leucine_in_grams=v("leucine_100g"),
        carbohydrates_in_grams=v("carbohydrates_100g"),
        fat_in_grams=v("fat_100g"),
        fiber_in_grams=v("fiber_100g"),
        sodium_in_milligrams=micronutrient_value("sodium_100g"),
        vitamin_c_in_milligrams=micronutrient_value("vitamin_c_100g"),
        vitamin_a_in_micrograms=micronutrient_value("vitamin_a_100g"),
        vitamin_e_in_milligrams=micronutrient_value("vitamin_e_100g"),
        vitamin_d_in_micrograms=micronutrient_value("vitamin_d_100g"),
        vitamin_k_in_micrograms=micronutrient_value("vitamin_k_100g"),
        vitamin_b6_in_milligrams=micronutrient_value("vitamin_b6_100g"),
        vitamin_b12_in_micrograms=micronutrient_value("vitamin_b12_100g"),
        vitamin_b1_in_milligrams=micronutrient_value("vitamin_b1_100g"),
        vitamin_b2_in_milligrams=micronutrient_value("vitamin_b2_100g"),
        vitamin_b3_in_milligrams=micronutrient_value("vitamin_b3_100g"),
        vitamin_b5_in_milligrams=micronutrient_value("vitamin_b5_100g"),
        folate_in_micrograms=micronutrient_value("folate_100g"),
        calcium_in_milligrams=micronutrient_value("calcium_100g"),
        iron_in_milligrams=micronutrient_value("iron_100g"),
        magnesium_in_milligrams=micronutrient_value("magnesium_100g"),
        phosphorus_in_milligrams=micronutrient_value("phosphorus_100g"),
        potassium_in_milligrams=micronutrient_value("potassium_100g"),
        zinc_in_milligrams=micronutrient_value("zinc_100g"),
        copper_in_milligrams=micronutrient_value("copper_100g"),
        manganese_in_milligrams=micronutrient_value("manganese_100g"),
        selenium_in_micrograms=micronutrient_value("selenium_100g"),
        omega3s_in_grams=v("omega3_100g"),
        # OFF has no collagen or fermented data
        collagen_in_grams=0.0,
        fermented_food_servings=0.0,
    )


def get_off_portions(food: dict) -> list[FoodPortion]:
    """
    Always include a base 'grams' portion (id=0).
    If the product has a serving size, add it as id=1.
    """
    portions = [
        FoodPortion(id=0, gram_weight=1.0, amount=1.0, modifier="grams")
    ]

    gram_weight = _as_float(food.get("serving_quantity"))  # numeric grams, most reliable
    serving_label = food.get("serving_size")    # e.g. "30g", "1 cup (240ml)"

    if gram_weight and gram_weight > 0:
        modifier = serving_label if serving_label else "serving"
        portions.append(
            FoodPortion(id=1, gram_weight=float(gram_weight), amount=1.0, modifier=modifier)
        )

    return portions

if __name__ == "__main__":
    DB_PATH = os.getenv("DB_PATH", "food.db")
    conn = sqlite3.connect(DB_PATH)
    print(get_off_food_by_code(conn, code="0732153028074"))
