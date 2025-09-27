from models.meal_analysis import AllNutrients, FoodPortion, AnalysisIngredient

# Convert USDA food entry to Ingredient
def map_ingredients(ingredient_list: list[dict]) -> list[AnalysisIngredient]:
    ingredients = []

    for i in ingredient_list:
        food_detail = i["food_detail"]
        amount = i["amount"]

        portions = map_portions(food_detail["portions"])
        selected_portion_id = 0
        if len(portions) > 0:
            selected_portion_id = portions[0].id

        nutrients = map_nutrients(food_detail["nutrients"], food_detail["food"])

        ingredients.append(
            AnalysisIngredient(
                fdc_id = food_detail["fdc_id"],
                description = food_detail["description"],
                amount = amount,
                selected_portion_id = selected_portion_id,
                portions=portions,
                nutrients=nutrients
            )
        )

    return ingredients

def map_portions(portion_list: list[dict]) -> list[FoodPortion]:
    portions = []

    for p in portion_list:
        portions.append(
            FoodPortion(
                id = p["id"],
                gram_weight = p["gram_weight"],
                amount = p["amount"],
                modifier = p["modifier"]
            )
        )

    return portions

def get_portions(conn, fdc_id: str):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT fp.id, fp.gram_weight, fp.amount, fp.modifier,
               mu.id, mu.name
        FROM sr_legacy_food_portion fp
        LEFT JOIN sr_legacy_measure_unit mu ON fp.measure_unit_id = mu.id
        WHERE fp.fdc_id = ?
    """, (fdc_id,))
    portions = []
    for row in cursor.fetchall():
        portions.append({
            "id": row[0],
            "gram_weight": row[1],
            "amount": row[2],
            "modifier": row[3]
        })

    if len(portions) < 1:
        portions = [{
            "id": 1,
            "gram_weight": 100.0,
            "amount": 100.0,
            "modifier": "grams"
        }]

    return portions

def map_nutrients(nutrient_list: list[dict], food: dict) -> AllNutrients:
    # Start with all zeros
    nutrient_values = AllNutrients(
        protein_in_grams=0.0,leucine_in_grams=0.0,carbohydrates_in_grams=0.0,omega3s_in_grams=0.0,fat_in_grams=0.0,zinc_in_milligrams=0.0,iron_in_milligrams=0.0,fermented_food_servings=0.0,fiber_in_grams=0.0,collagen_in_grams=0.0,vitamin_c_in_milligrams=0.0,vitamin_a_in_micrograms=0.0,vitamin_e_in_milligrams=0.0,selenium_in_micrograms=0.0
    )

    for n in nutrient_list:
        num = n["nutrient"]["number"]
        amount = n["amount"]

        if num == 203:
            nutrient_values.protein_in_grams = amount
        elif num == 504:
            nutrient_values.leucine_in_grams = amount
        elif num == 205:
            nutrient_values.carbohydrates_in_grams = amount
        elif num == 851:
            nutrient_values.omega3s_in_grams += amount
        elif num == 629:
            nutrient_values.omega3s_in_grams += amount
        elif num == 621:
            nutrient_values.omega3s_in_grams += amount
        elif num == 204:
            nutrient_values.fat_in_grams = amount
        elif num == 309:
            nutrient_values.zinc_in_milligrams = amount
        elif num == 303:
            nutrient_values.iron_in_milligrams = amount
        elif num == 291:
            nutrient_values.fiber_in_grams = amount
        elif num == 401:
            nutrient_values.vitamin_c_in_milligrams = amount
        elif num == 320:
            nutrient_values.vitamin_a_in_micrograms = amount
        elif num == 323:
            nutrient_values.vitamin_e_in_milligrams = amount
        elif num == 317:
            nutrient_values.selenium_in_micrograms = amount

    # Collagen & fermented servings are in the food table
    nutrient_values.fermented_food_servings = 0.0 if food["fermented_food_serving_size"] == None else round(100 / food["fermented_food_serving_size"], 2)
    nutrient_values.collagen_in_grams = 0.0 if food["collagen"] == None else food["collagen"] 

    return nutrient_values

def get_nutrients(conn, fdc_id: str):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT fn.id, fn.amount,
               n.id, CAST(n.nutrient_nbr AS INTEGER), n.name, n.unit_name
        FROM sr_legacy_food_nutrient fn
        JOIN sr_legacy_nutrient n ON fn.nutrient_id = n.id
        WHERE fn.fdc_id = ?
            AND CAST(n.nutrient_nbr AS INTEGER) IN (
                203, 204, 205, 291, 303, 309,
                401, 320, 323, 317, 504,
                851, 629, 621
            )
    """, (fdc_id,))
    nutrients = []
    for row in cursor.fetchall():
        nutrients.append({
            "id": row[0],
            "amount": row[1],
            "nutrient": {
                "id": row[2],
                "number": row[3],
                "name": row[4],
                "unit_name": row[5],
            }
        })

    return nutrients
