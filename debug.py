from fastapi import FastAPI
from openai import OpenAI
import uvicorn
import os
from dotenv import load_dotenv
from pydantic import BaseModel
# from supabase import create_client, Client
import json
from fastapi import HTTPException

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Create a FastAPI app
app = FastAPI()

# source venv/bin/activate
# uvicorn debug:app --reload

# testing name change




class MealImageUpdated(BaseModel):
    image_url: str

class MealIngredientUpdated(BaseModel):
    name: str
    quantity: str
    unit: str
    protein_in_grams: int
    collagen_in_grams: int
    leucine_in_grams: int
    carbohydrates_in_grams: int
    omega3s_in_milligrams: int
    fat_in_grams: int
    zinc_in_milligrams: int
    iron_in_milligrams: int
    fermented_food_servings: int
    fiber_in_grams: int
    vitamin_c_in_milligrams: int
    vitamin_a_in_micrograms: int
    vitamin_e_in_milligrams: int
    selenium_in_micrograms: int

class MealAnalysisUpdated(BaseModel):
    ingredients: list[MealIngredientUpdated]

# 1. Analyze image and get list of ingredients/amounts
# 2. Search USDA dataset for foods that match ingredients
# 3. Return ingredients/amounts
# 4. Getting nutrients for each ingredient will happen client side

# Analyze meal
@app.post("/meal-updated")
async def analyze_meal(payload: MealImageUpdated):
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
                            2. Estimate the quantity of each item (use a unit like g, oz., cup(s), tbsp., or tsp.).
                            3. ONLY respond with a JSON object that contains the name and an array of objects following this format exactly:
                            {
                                "name": "Chicken salad",
                                "ingredients": [
                                    {
                                        "name": "Grilled chicken breast",
                                        "amount": "4",
                                        "unit": "oz."
                                    },
                                    {
                                        "name": "Sauerkraut",
                                        "amount": "0.5",
                                        "unit": "cup(s)"
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
        print(e)
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
                    "content": f"Give me a nutrient analysis for each ingredient:\n{ingredients}."
                }
            ],
            response_format=MealAnalysisUpdated
        )
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"Nutrient analysis failed: {str(e)}")

    # Step 4: Parse nutrient analysis response
    analysis_response = chat_completion.choices[0].message.content.strip()
    analysis_string = extract_json_from_code_block(analysis_response)

    try:
        analysis = json.loads(analysis_string)
    except json.JSONDecodeError as e:
        print(e)
        raise HTTPException(status_code=400, detail=f"Failed to parse nutrient response: {e}")

    # print("NUTRIENTS:")
    # print(nutrients)

    return {
        "name": ingredients["name"],
        "analysis": analysis
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
