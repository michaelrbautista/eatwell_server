from fastapi import FastAPI
from openai import OpenAI
import uvicorn
import os
from dotenv import load_dotenv
from pydantic import BaseModel
# from supabase import create_client, Client
import json

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

@app.post("/analyze")
async def analyze_meal(payload: AnalyzeRequest):
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
                                Analyze this meal image and follow these stepes:
                                1. Identify each visible food item.
                                2. Give the meal a short title less than 5 words that describes it's contents (Ground beef bowl, chicken salad).
                                2. Estimate the quantity of each item (ONLY respond with oz., g, mg, cups, tbsp., tsp., or ser. (number of servings)).
                                3. ONLY respond with a JSON object that contains the name and an array of objects following this format exactly:
                                {
                                    "title": "Chicken salad",
                                    "ingredients": [
                                        {
                                            "name": "grilled chicken breast",
                                            "quantity": "4",
                                            "unit": "oz."
                                        },
                                        {
                                            "name": "sauerkraut",
                                            "quantity": "1",
                                            "unit": "ser."
                                        },
                                        ...
                                    ]
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

        ingredients_response = vision_completion.choices[0].message.content.strip()
        ingredients_string = extract_json_from_code_block(ingredients_response)

        try:
            ingredients = json.loads(ingredients_string)
        except json.JSONDecodeError as e:
            return {
                "error": f"Failed to parse vision response as JSON: {e}",
                "raw": ingredients_string
            }
        
        chat_completion = client.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {
                    "role": "user", 
                    "content": """
                    Based on the ingredients in this meal, give me a nutrient analysis. Return the amount of protein in grams, the amount of collagen in grams, the amount of leucine in grams, the amount of carbohydrates in grams, the amount of omega-3s in grams, the amount of fat in grams, the amount of zinc in milligrams, the amount of iron in milligrams, the number of fermented food servings, and the amount of fiber in grams.
                    """
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
            "meal_analysis": ingredients,
            "nutrients": nutrients
        }

    except Exception as e:
        return {
            "error": str(e)
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

@app.post("/edit")
async def analyze_edited_meal():
    try:
        chat_completion = client.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {
                    "role": "user", 
                    "content": """
                    Based on the ingredients in this meal, give me a nutrient analysis. Return a list of ingredients with name, amount, and unit of measurement, a title for the meal, the amount of protein in grams, the amount of collagen in grams, the amount of leucine in grams, the amount of carbohydrates in grams, the amount of omega-3s in grams, the amount of fat in grams, the amount of zinc in milligrams, the amount of iron in milligrams, the number of fermented food servings, and the amount of fiber in grams.
                    """
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
