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
# uvicorn app:app --reload

# supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

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

class AnalyzeRequest(BaseModel):
    image_url: str

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
                            2. Give the meal a short title less than 5 words that describes it's contents (Ground beef bowl, chicken salad, etc). If it's a single food item, return ONLY the name of the food (apple, banana, etc.).
                            2. Estimate the quantity of each item (ONLY respond with oz., g, mg, cup(s), tbsp., tsp., or ser. (number of servings)).
                            3. ONLY respond with a JSON object that contains the name and an array of objects following this format exactly:
                            {
                                "title": "Chicken salad",
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
                                "title": "Unknown",
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

    print("INGREDIENTS:")
    print(ingredients)

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

    print("NUTRIENTS:")
    print(nutrients)

    return {
        "meal_analysis": ingredients,
        "nutrients": nutrients
    }
    
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




class Ingredient(BaseModel):
    name: str
    quantity: str
    unit: str

class UpdateRequest(BaseModel):
    ingredients: list[Ingredient]

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
    
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
