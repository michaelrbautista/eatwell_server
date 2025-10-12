from fastapi import FastAPI
from openai import OpenAI
import uvicorn
import os
from dotenv import load_dotenv
from pydantic import BaseModel
import json
from fastapi import HTTPException
import sqlite3
from helper import get_nutrients, map_nutrients, get_portions, map_portions
from db.search_service import fuzzy_search, fts_search
from models.meal_analysis import AnalysisIngredient, InvalidIngredients, AnalysisMeal
from helper import get_nutrients, map_nutrients, get_portions, map_portions, calculate_protein, calculate_leucine, calculate_carbohydrates, calculate_omega3s, calculate_fat, calculate_iron, calculate_zinc, calculate_fermented_food_servings, calculate_fiber, calculate_collagen, calculate_vitamin_c, calculate_vitamin_a, calculate_vitamin_e, calculate_selenium
from query import search_food

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Create a FastAPI app
app = FastAPI()

# source venv/bin/activate
# uvicorn app:app --reload




# --------------------------------------------------------------------------------
# NEW analyze meal
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
                            Analyze this image and follow these stepes:
                            1. Identify the visible food items.
                                - If the meal is composed of distinct, separable foods (grilled chicken, white rice, broccoli, etc.), treat each as an ingredient.
                                - If it's a single, blended, or composite food (pizza, muffin, burger, sandwich, smoothie, soup, etc.), treat it as one unified meal and do not list ingredients.
                            2. Give the meal a short descriptive name, including cooking methods if applicable (grilled chicken, boiled eggs, etc.).
                            3. Decide the output format based on the meal type:
                                - If the meal has distinct ingredients, return an object like this:
                                {
                                    "name": "Chicken and rice",
                                    "ingredients": [
                                        {
                                            "name": "Grilled chicken thigh",
                                            "quantity_in_grams": 100.0
                                        },
                                        {
                                            "name": "White rice",
                                            "quantity_in_grams": 80.0
                                        },
                                        ...
                                    ]
                                }
                                - If the meal is a composite food, return an object like this instead:
                                {
                                    "name": "Chicken and rice",
                                    "protein_in_grams": 23.0
                                    "leucine_in_grams": 0.6
                                    "carbohydrates_in_grams": 34.0
                                    "omega3s_in_grams": 0.3
                                    "fat_in_grams": 28.0
                                    "iron_in_milligrams": 9.0
                                    "zinc_in_milligrams": 10.0
                                    "fermented_food_servings": 0.3
                                    "fiber_in_grams": 5.0
                                    "collagen_in_grams": 4.0
                                    "vitamin_c_in_milligrams": 32.0
                                    "vitamin_a_in_micrograms": 237.0
                                    "vitamin_e_in_milligrams": 6.0
                                    "selenium_in_micrograms": 31.0
                                }
                            4. If no food is visible, return this exact object:
                            {
                                "name": "Unknown",
                                "ingredients": []
                            }
                            5. All numeric values must be floats. Return only valid JSON - no extra text or explanations.
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
            selenium_float=analysis["selenium_in_micrograms"]
        )
    else:
        # Query database
        ingredients = analysis["ingredients"]

        valid_results = []
        invalid_results = []
        for food in ingredients:
            result = search_food(food["name"], food["quantity_in_grams"])
            if isinstance(result, AnalysisIngredient):
                valid_results.append(result)
            else:
                invalid_results.append(result)

        custom_foods: InvalidIngredients = InvalidIngredients(ingredients=[])

        if len(invalid_results) > 0:
            # Create custom foods for foods not in database
            try:
                chat_completion = client.beta.chat.completions.parse(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user",
                            "content": f"Given this list: {invalid_results}, give me a food object like the USDA Food Central database. For each food, set 'fdc_id' to 1 and the 'amount' field to 1.0. Create one portion for each food with the appropriate gram_weight for that portion size. Provide nutrient values per 100 grams of that food."
                        }
                    ],
                    response_format=InvalidIngredients
                )
            except Exception as e:
                print(e)
                raise HTTPException(status_code=500, detail=f"Nutrient analysis failed: {str(e)}")
            
            custom_foods = chat_completion.choices[0].message.parsed

        database_results = valid_results + custom_foods.ingredients

        return AnalysisMeal(
            name=meal_name,
            ingredients_new=database_results,
            protein_float=calculate_protein(database_results),
            leucine_float=calculate_leucine(database_results),
            carbohydrates_float=calculate_carbohydrates(database_results),
            omega3s_float=calculate_omega3s(database_results),
            fat_float=calculate_fat(database_results),
            iron_float=calculate_iron(database_results),
            zinc_float=calculate_zinc(database_results),
            fermented_food_servings_float=calculate_fermented_food_servings(database_results),
            fiber_float=calculate_fiber(database_results),
            collagen_float=calculate_collagen(database_results),
            vitamin_c_float=calculate_vitamin_c(database_results),
            vitamin_a_float=calculate_vitamin_a(database_results),
            vitamin_e_float=calculate_vitamin_e(database_results),
            selenium_float=calculate_selenium(database_results)
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
                    "content": f"Give me a food object for {name} like the USDA Food Central database. Set 'fdc_id' to 1 and the 'amount' field to 1.0. Create one portion for {amount} {modifier} with the appropriate gram_weight for that portion size. Provide nutrient values per 100 grams of {name}."
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
        SELECT fdc_id, data_type, description, fermented_food_serving_size, CAST(collagen AS REAL) AS collagen
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
        nutrients=mapped_nutrients
    )

    conn.close()
    return ingredient

# --------------------------------------------------------------------------------
# Search for food
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
    
    return {
        "foods": candidates
    }

# --------------------------------------------------------------------------------
# OLD analyze meal
# --------------------------------------------------------------------------------

class IngredientResponse(BaseModel):
    protein_in_grams: int
    collagen_in_grams: int
    leucine_in_grams: int
    carbohydrates_in_grams: int
    omega3s_in_grams: int
    fat_in_grams: int
    zinc_in_milligrams: int
    iron_in_milligrams: int
    fermented_food_servings: int
    fiber_in_grams: int
    vitamin_c_in_milligrams: int
    vitamin_a_in_micrograms: int
    vitamin_e_in_milligrams: int
    selenium_in_micrograms: int

class AnalyzeRequest(BaseModel):
    image_url: str

class Ingredient(BaseModel):
    name: str
    quantity: str
    unit: str

class UpdateRequest(BaseModel):
    ingredients: list[Ingredient]

# NEED TO KEEP - ADD NEW ENDPOINT FOR UPDATED MODEL
# Analyze meal
@app.post("/meal")
async def analyze_meal(payload: AnalyzeRequest):
    # Step 1: Call vision completion
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
                            Analyze this image and follow these stepes:
                            1. Identify each visible food item.
                            2. Give the meal a short name less than 5 words that describes it's contents (Ground beef bowl, chicken salad, etc). If it's a single food item, return ONLY the name of the food (apple, banana, etc.).
                            2. Estimate the quantity of each item (ONLY respond with oz., g, mg, cup(s), tbsp., tsp., or ser. (number of servings)).
                            3. ONLY respond with a JSON object that contains the name and an array of objects following this format exactly:
                            {
                                "name": "Chicken salad",
                                "ingredients": [
                                    {
                                        "name": "Grilled chicken breast",
                                        "quantity": "4",
                                        "unit": "oz."
                                    },
                                    {
                                        "name": "Sauerkraut",
                                        "quantity": "1",
                                        "unit": "ser."
                                    },
                                    ...
                                ]
                            }
                            4. If there are no food items in the image, return this EXACT object:
                            {
                                "name": "Unknown",
                                "ingredients": []
                            }
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

    # Step 2: Parse JSON from vision completion
    ingredients_response = vision_completion.choices[0].message.content.strip()
    ingredients_string = extract_json_from_code_block(ingredients_response)

    try:
        ingredients = json.loads(ingredients_string)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse vision response: {e}")

    # print("INGREDIENTS:")
    # print(ingredients)

    # Step 3: Call chat completion for nutrient analysis
    try:
        chat_completion = client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": f"Based on these ingredients, give me a nutrient analysis:\n{ingredients}."
                }
            ],
            response_format=IngredientResponse
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nutrient analysis failed: {str(e)}")

    # Step 4: Parse nutrient analysis response
    nutrients_response = chat_completion.choices[0].message.content.strip()
    nutrients_string = extract_json_from_code_block(nutrients_response)

    try:
        nutrients = json.loads(nutrients_string)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse nutrient response: {e}")

    # print("NUTRIENTS:")
    # print(nutrients)

    return {
        "meal_analysis": ingredients,
        "nutrients": nutrients
    }

# Update meal with new ingredients
@app.post("/ingredients")
async def analyze_edited_meal(payload: UpdateRequest):
    try:
        chat_completion = client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {
                    "role": "user", 
                    "content": f"Based on these ingredients, give me a nutrient analysis:\n{payload.ingredients}. 'ser.' is equal to serving(s)."
                }
            ],
            response_format=IngredientResponse
        )

        nutrients_response = chat_completion.choices[0].message.content.strip()
        nutrients_string = extract_json_from_code_block(nutrients_response)

        try:
            nutrients = json.loads(nutrients_string)
        except json.JSONDecodeError as e:
            return {
                "error": f"Failed to parse chat response as JSON: {e}",
                "raw": nutrients_string
            }

        return {
            "nutrients": nutrients
        }

    except Exception as e:
        return {
            "error": str(e)
        }

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
    
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
