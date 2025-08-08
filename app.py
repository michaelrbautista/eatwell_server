from fastapi import FastAPI
from openai import OpenAI
import uvicorn
import os
from dotenv import load_dotenv
from pydantic import BaseModel
import random
from supabase import create_client, Client
from typing import Literal

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Create a FastAPI app
app = FastAPI()

# source venv/bin/activate
# uvicorn app:app --reload

supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

class Ingredient(BaseModel):
    name: str
    amount: float
    unit: Literal["", "lbs.", "oz.", "fl oz.", "g", "mg", "cups", "tbsp.", "tsp.", "ser."]

class MealResponse(BaseModel):
    ingredients: list[Ingredient]
    title: str
    protein: int
    collagen: int
    leucine: int
    carbohydrates: int
    omega3s: int
    fat: int
    zinc: int
    iron: int
    fermentedFoodServings: int
    fiber: int
    percentWholeFoods: int
    percentHealthyFats: int

@app.post("/meal")
async def analyze_meal():
    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "user", 
                    "content": """
                        Give me a nutrient analysis based on the given image of a meal. Return a list of ingredients (include ingredient name, amount, and unit of measurement), a simple title for the meal, the amount of protein in grams, the amount of collagen in grams, the amount of leucine in grams, the amount of carbohydrates in grams, the amount of omega-3s in grams, the amount of fat in grams, the amount of zinc in milligrams, the amount of iron in milligrams, the number of fermented food servings, the amount of fiber in grams, the percentage of the meal that is whole foods, and the percentage of the meal that is healthy fats (saturated and monounsaturated are healthy, polyunsaturated and trans are unhealthy).
                    """
                }
            ],
            response_format=MealResponse
        )

        return completion.choices[0].message.parsed

    except Exception as e:
        return {"error": str(e)}

class IngredientResponse(BaseModel):
    ingredients: list[Ingredient]
    protein: int
    collagen: int
    leucine: int
    carbohydrates: int
    omega3s: int
    fat: int
    zinc: int
    iron: int
    fermentedFoodServings: int
    fiber: int
    percentWholeFoods: int
    percentHealthyFats: int

@app.post("/meal")
async def analyze_meal():
    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "user", 
                    "content": """
                        Based on the ingredients in this meal, give me a nutrient analysis. Return a simple title for the meal, the amount of protein in grams, the amount of collagen in grams, the amount of leucine in grams, the amount of carbohydrates in grams, the amount of omega-3s in grams, the amount of fat in grams, the amount of zinc in milligrams, the amount of iron in milligrams, the number of fermented food servings, the amount of fiber in grams, the percentage of the meal that is whole foods, and the percentage of the meal that is healthy fats (saturated and monounsaturated are healthy, polyunsaturated and trans are unhealthy).
                    """
                }
            ],
            response_format=IngredientResponse
        )

        return completion.choices[0].message.parsed

    except Exception as e:
        return {"error": str(e)}
    
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
