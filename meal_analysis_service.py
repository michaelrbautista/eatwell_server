import json

from fastapi import HTTPException
from pydantic import BaseModel

from helper import (
    calculate_carbohydrates,
    calculate_calcium,
    calculate_collagen,
    calculate_copper,
    calculate_fat,
    calculate_fermented_food_servings,
    calculate_fiber,
    calculate_folate,
    calculate_iron,
    calculate_leucine,
    calculate_magnesium,
    calculate_manganese,
    calculate_omega3s,
    calculate_phosphorus,
    calculate_protein,
    calculate_quality_score,
    calculate_selenium,
    calculate_sodium,
    calculate_potassium,
    calculate_vitamin_a,
    calculate_vitamin_b1,
    calculate_vitamin_b2,
    calculate_vitamin_b3,
    calculate_vitamin_b5,
    calculate_vitamin_b6,
    calculate_vitamin_b12,
    calculate_vitamin_c,
    calculate_vitamin_e,
    calculate_vitamin_k,
    calculate_zinc,
)
from models.meal_analysis import AnalysisIngredient, AnalysisMeal
from query_utils import search_food

DEFAULT_INGREDIENT_GRAMS = 100.0


class TextMealAnalysisRequest(BaseModel):
    description: str


def extract_json_from_code_block(text: str) -> str:
    """
    Extract raw JSON from a markdown-formatted code block.
    """
    if text.startswith("```json") or text.startswith("```"):
        lines = text.strip().split("\n")
        if len(lines) >= 3:
            return "\n".join(lines[1:-1])
    return text.strip()


def _coerce_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _analysis_value(analysis: dict, *keys: str, default: float = 0.0) -> float:
    for key in keys:
        if key in analysis and analysis[key] is not None:
            return _coerce_float(analysis[key], default)
    return default


def _is_composite_analysis(analysis: dict) -> bool:
    return "protein_in_grams" in analysis or "protein_float" in analysis


def _normalize_ingredients(raw_ingredients) -> list[dict]:
    normalized = []
    if not raw_ingredients:
        return normalized

    for ingredient in raw_ingredients:
        name = str(ingredient.get("name", "")).strip()
        if not name:
            continue

        quantity = _analysis_value(
            ingredient,
            "quantity_in_grams",
            "quantity",
            "amount",
            default=DEFAULT_INGREDIENT_GRAMS,
        )
        normalized.append(
            {
                "name": name,
                "quantity_in_grams": quantity if quantity > 0 else DEFAULT_INGREDIENT_GRAMS,
            }
        )

    return normalized


def build_analysis_meal(analysis: dict, *, search_food_fn=search_food) -> AnalysisMeal:
    meal_name = str(analysis.get("name", "Unknown")).strip() or "Unknown"

    if _is_composite_analysis(analysis):
        return AnalysisMeal(
            name=meal_name,
            ingredients_new=[],
            protein_float=_analysis_value(analysis, "protein_in_grams", "protein_float"),
            leucine_float=_analysis_value(analysis, "leucine_in_grams", "leucine_float"),
            carbohydrates_float=_analysis_value(
                analysis, "carbohydrates_in_grams", "carbohydrates_float"
            ),
            omega3s_float=_analysis_value(analysis, "omega3s_in_grams", "omega3s_float"),
            fat_float=_analysis_value(analysis, "fat_in_grams", "fat_float"),
            iron_float=_analysis_value(analysis, "iron_in_milligrams", "iron_float"),
            zinc_float=_analysis_value(analysis, "zinc_in_milligrams", "zinc_float"),
            fermented_food_servings_float=_analysis_value(
                analysis, "fermented_food_servings", "fermented_food_servings_float"
            ),
            fiber_float=_analysis_value(analysis, "fiber_in_grams", "fiber_float"),
            collagen_float=_analysis_value(analysis, "collagen_in_grams", "collagen_float"),
            vitamin_c_float=_analysis_value(
                analysis, "vitamin_c_in_milligrams", "vitamin_c_float"
            ),
            vitamin_a_float=_analysis_value(
                analysis, "vitamin_a_in_micrograms", "vitamin_a_float"
            ),
            vitamin_e_float=_analysis_value(
                analysis, "vitamin_e_in_milligrams", "vitamin_e_float"
            ),
            selenium_float=_analysis_value(
                analysis, "selenium_in_micrograms", "selenium_float"
            ),
            vitamin_b12_float=_analysis_value(
                analysis,
                "vitamin_b12_in_micrograms",
                "vitamin_b12_in_milligrams",
                "vitamin_b12_float",
            ),
            vitamin_b6_float=_analysis_value(
                analysis, "vitamin_b6_in_milligrams", "vitamin_b6_float"
            ),
            copper_float=_analysis_value(analysis, "copper_in_milligrams", "copper_float"),
            folate_float=_analysis_value(analysis, "folate_in_micrograms", "folate_float"),
            sodium_float=_analysis_value(analysis, "sodium_in_milligrams", "sodium_float"),
            potassium_float=_analysis_value(
                analysis, "potassium_in_milligrams", "potassium_float"
            ),
            magnesium_float=_analysis_value(
                analysis, "magnesium_in_milligrams", "magnesium_float"
            ),
            vitamin_b1_float=_analysis_value(
                analysis, "vitamin_b1_in_milligrams", "vitamin_b1_float"
            ),
            vitamin_b2_float=_analysis_value(
                analysis, "vitamin_b2_in_milligrams", "vitamin_b2_float"
            ),
            vitamin_b3_float=_analysis_value(
                analysis, "vitamin_b3_in_milligrams", "vitamin_b3_float"
            ),
            vitamin_b5_float=_analysis_value(
                analysis, "vitamin_b5_in_milligrams", "vitamin_b5_float"
            ),
            vitamin_k_float=_analysis_value(
                analysis, "vitamin_k_in_micrograms", "vitamin_k_float"
            ),
            calcium_float=_analysis_value(
                analysis, "calcium_in_milligrams", "calcium_float"
            ),
            manganese_float=_analysis_value(
                analysis, "manganese_in_milligrams", "manganese_float"
            ),
            phosphorus_float=_analysis_value(
                analysis, "phosphorus_in_milligrams", "phosphorus_float"
            ),
            quality_score=_analysis_value(analysis, "quality_score", default=0.0),
        )

    valid_results: list[AnalysisIngredient] = []
    for food in _normalize_ingredients(analysis.get("ingredients", [])):
        result = search_food_fn(food["name"], food["quantity_in_grams"])
        if isinstance(result, AnalysisIngredient):
            valid_results.append(result)

    return AnalysisMeal(
        name=meal_name,
        ingredients_new=valid_results,
        protein_float=calculate_protein(valid_results),
        leucine_float=calculate_leucine(valid_results),
        carbohydrates_float=calculate_carbohydrates(valid_results),
        omega3s_float=calculate_omega3s(valid_results),
        fat_float=calculate_fat(valid_results),
        iron_float=calculate_iron(valid_results),
        zinc_float=calculate_zinc(valid_results),
        fermented_food_servings_float=calculate_fermented_food_servings(valid_results),
        fiber_float=calculate_fiber(valid_results),
        collagen_float=calculate_collagen(valid_results),
        vitamin_c_float=calculate_vitamin_c(valid_results),
        vitamin_a_float=calculate_vitamin_a(valid_results),
        vitamin_e_float=calculate_vitamin_e(valid_results),
        selenium_float=calculate_selenium(valid_results),
        vitamin_b12_float=calculate_vitamin_b12(valid_results),
        vitamin_b6_float=calculate_vitamin_b6(valid_results),
        copper_float=calculate_copper(valid_results),
        folate_float=calculate_folate(valid_results),
        sodium_float=calculate_sodium(valid_results),
        potassium_float=calculate_potassium(valid_results),
        magnesium_float=calculate_magnesium(valid_results),
        vitamin_b1_float=calculate_vitamin_b1(valid_results),
        vitamin_b2_float=calculate_vitamin_b2(valid_results),
        vitamin_b3_float=calculate_vitamin_b3(valid_results),
        vitamin_b5_float=calculate_vitamin_b5(valid_results),
        vitamin_k_float=calculate_vitamin_k(valid_results),
        calcium_float=calculate_calcium(valid_results),
        manganese_float=calculate_manganese(valid_results),
        phosphorus_float=calculate_phosphorus(valid_results),
        quality_score=calculate_quality_score(valid_results) or 0.0,
    )


def _meal_description_prompt(description: str) -> str:
    return f"""
Analyze this meal description and follow these steps:
1. Identify all foods in the meal using natural food names.
2. If the meal consists of distinct, separable foods, return each ingredient separately.
3. If the meal is a composite food made of multiple ingredients (for example pizza, sandwich, smoothie, pasta, burrito, soup), return only the composite food object and its nutrients.
4. If a quantity is explicitly stated for an ingredient, include it as `quantity_in_grams`.
5. If no quantity is provided for an ingredient, return a standard serving size for that ingredient as `quantity_in_grams`.
6. Use this output format:
   - Distinct ingredients:
     {{
       "name": "Chicken and rice",
       "ingredients": [
         {{"name": "Chicken thigh", "quantity_in_grams": 100.0}},
         {{"name": "White rice", "quantity_in_grams": 80.0}}
       ]
     }}
   - Composite food:
     {{
       "name": "Muffin",
       "protein_in_grams": 7.2,
       "leucine_in_grams": 0.4,
       "carbohydrates_in_grams": 42.5,
       "omega3s_in_grams": 0.1,
       "fat_in_grams": 12.4,
       "iron_in_milligrams": 1.3,
       "zinc_in_milligrams": 0.8,
       "fermented_food_servings": 0.0,
       "fiber_in_grams": 2.8,
       "collagen_in_grams": 0.0,
       "vitamin_c_in_milligrams": 0.0,
       "vitamin_a_in_micrograms": 21.0,
       "vitamin_e_in_milligrams": 0.5,
       "selenium_in_micrograms": 9.0,
       "vitamin_b12_in_micrograms": 0.0,
       "vitamin_b6_in_milligrams": 0.0,
       "copper_in_milligrams": 0.0,
       "folate_in_micrograms": 0.0,
       "sodium_in_milligrams": 0.0,
       "potassium_in_milligrams": 0.0,
       "magnesium_in_milligrams": 0.0,
       "vitamin_b1_in_milligrams": 0.0,
       "vitamin_b2_in_milligrams": 0.0,
       "vitamin_b3_in_milligrams": 0.0,
       "vitamin_b5_in_milligrams": 0.0,
       "vitamin_k_in_micrograms": 0.0,
       "calcium_in_milligrams": 0.0,
       "manganese_in_milligrams": 0.0,
       "phosphorus_in_milligrams": 0.0,
       "quality_score": 30.0
     }}
7. If no food is mentioned, return exactly:
   {{
     "name": "Unknown",
     "ingredients": []
   }}
8. All numeric values must be floats.
9. Return only valid JSON.

Meal description:
{description}
""".strip()


def analyze_text_meal_description(client, description: str, *, search_food_fn=search_food) -> AnalysisMeal:
    try:
        completion = client.chat.completions.create(
            model="gpt-5.2",
            messages=[
                {
                    "role": "system",
                    "content": "You are a nutrition expert who extracts meal ingredients and estimates quantities from text.",
                },
                {"role": "user", "content": _meal_description_prompt(description)},
            ],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text analysis API call failed: {str(e)}")

    analysis_response = completion.choices[0].message.content.strip()
    analysis_string = extract_json_from_code_block(analysis_response)

    try:
        analysis = json.loads(analysis_string)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse meal description response: {e}")

    return build_analysis_meal(analysis, search_food_fn=search_food_fn)
