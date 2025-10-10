from models.meal_analysis import AllNutrients, FoodPortion, AnalysisIngredient

# Calculate nutrients
def calculate_protein(ingredients: list[AnalysisIngredient]) -> float:
    protein = 0.0
    for ingredient in ingredients:
        portion = get_selected_portion(ingredient)
        scale = portion.gram_weight / 100.0
        protein += (scale * ingredient.amount * ingredient.nutrients.protein_in_grams)
    return round(protein, 2)

def calculate_leucine(ingredients: list[AnalysisIngredient]) -> float:
    leucine = 0.0
    for ingredient in ingredients:
        portion = get_selected_portion(ingredient)
        scale = portion.gram_weight / 100.0
        leucine += (scale * ingredient.amount * ingredient.nutrients.leucine_in_grams)
    return round(leucine, 2)

def calculate_carbohydrates(ingredients: list[AnalysisIngredient]) -> float:
    carbohydrates = 0.0
    for ingredient in ingredients:
        portion = get_selected_portion(ingredient)
        scale = portion.gram_weight / 100.0
        carbohydrates += (scale * ingredient.amount * ingredient.nutrients.carbohydrates_in_grams)
    return round(carbohydrates, 2)

def calculate_omega3s(ingredients: list[AnalysisIngredient]) -> float:
    omega3s = 0.0
    for ingredient in ingredients:
        portion = get_selected_portion(ingredient)
        scale = portion.gram_weight / 100.0
        omega3s += (scale * ingredient.amount * ingredient.nutrients.omega3s_in_grams)
    return round(omega3s, 2)

def calculate_fat(ingredients: list[AnalysisIngredient]) -> float:
    fat = 0.0
    for ingredient in ingredients:
        portion = get_selected_portion(ingredient)
        scale = portion.gram_weight / 100.0
        fat += (scale * ingredient.amount * ingredient.nutrients.fat_in_grams)
    return round(fat, 2)

def calculate_iron(ingredients: list[AnalysisIngredient]) -> float:
    iron = 0.0
    for ingredient in ingredients:
        portion = get_selected_portion(ingredient)
        scale = portion.gram_weight / 100.0
        iron += (scale * ingredient.amount * ingredient.nutrients.iron_in_milligrams)
    return round(iron, 2)

def calculate_zinc(ingredients: list[AnalysisIngredient]) -> float:
    zinc = 0.0
    for ingredient in ingredients:
        portion = get_selected_portion(ingredient)
        scale = portion.gram_weight / 100.0
        zinc += (scale * ingredient.amount * ingredient.nutrients.zinc_in_milligrams)
    return round(zinc, 2)

def calculate_fermented_food_servings(ingredients: list[AnalysisIngredient]) -> float:
    servings = 0.0
    for ingredient in ingredients:
        portion = get_selected_portion(ingredient)
        scale = portion.gram_weight / 100.0
        servings += (scale * ingredient.amount * ingredient.nutrients.fermented_food_servings)
    return round(servings, 2)

def calculate_fiber(ingredients: list[AnalysisIngredient]) -> float:
    fiber = 0.0
    for ingredient in ingredients:
        portion = get_selected_portion(ingredient)
        scale = portion.gram_weight / 100.0
        fiber += (scale * ingredient.amount * ingredient.nutrients.fiber_in_grams)
    return round(fiber, 2)

def calculate_collagen(ingredients: list[AnalysisIngredient]) -> float:
    collagen = 0.0
    for ingredient in ingredients:
        portion = get_selected_portion(ingredient)
        scale = portion.gram_weight / 100.0
        collagen += (scale * ingredient.amount * ingredient.nutrients.collagen_in_grams)
    return round(collagen, 2)

def calculate_vitamin_c(ingredients: list[AnalysisIngredient]) -> float:
    vitamin_c = 0.0
    for ingredient in ingredients:
        portion = get_selected_portion(ingredient)
        scale = portion.gram_weight / 100.0
        vitamin_c += (scale * ingredient.amount * ingredient.nutrients.vitamin_c_in_milligrams)
    return round(vitamin_c, 2)

def calculate_vitamin_a(ingredients: list[AnalysisIngredient]) -> float:
    vitamin_a = 0.0
    for ingredient in ingredients:
        portion = get_selected_portion(ingredient)
        scale = portion.gram_weight / 100.0
        vitamin_a += (scale * ingredient.amount * ingredient.nutrients.vitamin_a_in_micrograms)
    return round(vitamin_a, 2)

def calculate_vitamin_e(ingredients: list[AnalysisIngredient]) -> float:
    vitamin_e = 0.0
    for ingredient in ingredients:
        portion = get_selected_portion(ingredient)
        scale = portion.gram_weight / 100.0
        vitamin_e += (scale * ingredient.amount * ingredient.nutrients.vitamin_e_in_milligrams)
    return round(vitamin_e, 2)

def calculate_selenium(ingredients: list[AnalysisIngredient]) -> float:
    selenium = 0.0
    for ingredient in ingredients:
        portion = get_selected_portion(ingredient)
        scale = portion.gram_weight / 100.0
        selenium += (scale * ingredient.amount * ingredient.nutrients.selenium_in_micrograms)
    return round(selenium, 2)

def get_selected_portion(ingredient: AnalysisIngredient) -> FoodPortion:
    for portion in ingredient.portions:
        if portion.id == ingredient.selected_portion_id:
            return portion

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
        SELECT fp.id, fp.gram_weight, fp.amount, fp.modifier
        FROM sr_legacy_food_portion fp
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
        protein_in_grams=0.0,leucine_in_grams=0.0,carbohydrates_in_grams=0.0,omega3s_in_grams=0.0,fat_in_grams=0.0,iron_in_milligrams=0.0,zinc_in_milligrams=0.0,fermented_food_servings=0.0,fiber_in_grams=0.0,collagen_in_grams=0.0,vitamin_c_in_milligrams=0.0,vitamin_a_in_micrograms=0.0,vitamin_e_in_milligrams=0.0,selenium_in_micrograms=0.0
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

if __name__ == "__main__":
    ingredient = AnalysisIngredient(
        fdc_id=170392,
        description="Kimchi",
        amount=1.0,
        selected_portion_id=86554,
        portions=[
            FoodPortion(
                id=86554,
                gram_weight=150.0,
                amount=1.0,
                modifier="cup"
            )
        ],
        nutrients=AllNutrients(
            protein_in_grams=1.1,
            leucine_in_grams=0.0,
            carbohydrates_in_grams=2.4,
            omega3s_in_grams=0.0,
            fat_in_grams=0.5,
            iron_in_milligrams=2.5,
            zinc_in_milligrams=0.22,
            fermented_food_servings=3.33,
            fiber_in_grams=1.6,
            collagen_in_grams=0.0,
            vitamin_c_in_milligrams=0.0,
            vitamin_a_in_micrograms=5.0,
            vitamin_e_in_milligrams=0.11,
            selenium_in_micrograms=0.5
        )
    )

    protein = calculate_fermented_food_servings([ingredient])
    print(protein)
