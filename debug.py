from fastapi import FastAPI
from openai import OpenAI
import uvicorn
import os
from dotenv import load_dotenv
from pydantic import BaseModel
import json
from fastapi import HTTPException
from db.search_service import preprocess_query, fts_search, fuzzy_search
from query import search_food
from helper import get_nutrients, map_nutrients, get_portions, map_portions
from models.meal_analysis import AnalysisIngredient
import sqlite3

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
                            Analyze this image and follow these stepes:
                            1. Identify each visible food item.
                            2. Give the meal a short name that describes it's contents (Ground beef bowl, Chicken and rice, etc). If it's a single food item, return ONLY the name of the food (apple, banana, etc.).
                            2. Estimate the quantity of each item in grams as a float.
                            3. Return a name of the meal and list of ingredients in this exact format:
                            {
                                "name": "Chicken salad",
                                "ingredients": [
                                    {
                                        "name": "Chicken thigh",
                                        "quantity_in_grams": 100.0
                                    },
                                    {
                                        "name": "Rice",
                                        "quantity_in_grams": 80.0
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
    
    # Format response from OpenAI
    analysis_response = vision_completion.choices[0].message.content.strip()
    analysis_string = extract_json_from_code_block(analysis_response)

    try:
        analysis = json.loads(analysis_string)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse vision response: {e}")
    
    # Query database
    meal_name = analysis["name"]
    ingredients = analysis["ingredients"]

    database_results = []
    for ingredient in ingredients:
        query = preprocess_query(ingredient["name"])
        amount = ingredient["quantity_in_grams"]
        food = search_food(query, amount)
        database_results.append(food)

    # Return ingredients
    return {
        "name": meal_name,
        "foods": database_results
    }

# --------------------------------------------------------------------------------
# Analyze image (old)
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

# 1. Analyze image and get list of ingredients/amounts
# 2. Search USDA dataset for foods that match ingredients
# 3. Return ingredients/amounts

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

# --------------------------------------------------------------------------------
# Custom food
# --------------------------------------------------------------------------------

class CustomIngredientPortion(BaseModel):
    id: int
    gram_weight: float
    amount: float
    modifier: str

class CustomIngredientNutrients(BaseModel):
    protein_in_grams: float
    collagen_in_grams: float
    leucine_in_grams: float
    carbohydrates_in_grams: float
    omega3s_in_grams: float
    fat_in_grams: float
    zinc_in_milligrams: float
    iron_in_milligrams: float
    fermented_food_servings: float
    fiber_in_grams: float
    vitamin_c_in_milligrams: float
    vitamin_a_in_micrograms: float
    vitamin_e_in_milligrams: float
    selenium_in_micrograms: float

class CustomIngredient(BaseModel):
    fdc_id: int = 1
    description: str
    amount: float = 1.0
    selected_portion_id: int = 1
    portions: list[CustomIngredientPortion]
    nutrients: CustomIngredientNutrients

@app.post("/custom-food")
async def custom_food(name: str, amount: float, modifier: str):
    try:
        chat_completion = client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": f"Give me a food object for '{name}' like the USDA Food Central database. Set 'fdc_id' to 1 and the 'amount' field to 1.0. Create one portion for {amount} {modifier} with the appropriate gram_weight for that portion size. Provide nutrient values per 100 grams."
                }
            ],
            response_format=CustomIngredient
        )
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"Nutrient analysis failed: {str(e)}")
    
    custom_food_response = chat_completion.choices[0].message.content.strip()
    custom_food_string = extract_json_from_code_block(custom_food_response)

    try:
        custom_food = json.loads(custom_food_string)
    except json.JSONDecodeError as e:
        print(e)
        raise HTTPException(status_code=400, detail=f"Failed to parse nutrient response: {e}")
    
    return custom_food

# --------------------------------------------------------------------------------
# Get food details
# --------------------------------------------------------------------------------

@app.get("/food/{fdc_id}")
async def food_details(fdc_id: int):
    DB_PATH = "food.db"
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
    DB_PATH = "food.db"
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

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
