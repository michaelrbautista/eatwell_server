from pydantic import BaseModel

class FoodPortion(BaseModel):
    id: int
    gram_weight: float
    amount: float
    modifier: str

class AllNutrients(BaseModel):
    protein_in_grams: float
    leucine_in_grams: float
    carbohydrates_in_grams: float
    omega3s_in_grams: float
    fat_in_grams: float
    iron_in_milligrams: float
    zinc_in_milligrams: float
    fermented_food_servings: float
    fiber_in_grams: float
    collagen_in_grams: float
    vitamin_c_in_milligrams: float
    vitamin_a_in_micrograms: float
    vitamin_e_in_milligrams: float
    selenium_in_micrograms: float

class AnalysisIngredient(BaseModel):
    fdc_id: int
    description: str
    amount: float
    selected_portion_id: int
    portions: list[FoodPortion]
    nutrients: AllNutrients

class AnalysisMeal(BaseModel):
    name: str
    ingredients: list[AnalysisIngredient]

    protein_float: float
    leucine_float: float
    carbohydrates_float: float
    omega3s_float: float
    fat_float: float
    iron_float: float
    zinc_float: float
    fermented_food_servings_float: float
    fiber_float: float
    collagen_float: float
    vitamin_c_float: float
    vitamin_a_float: float
    vitamin_e_float: float
    selenium_float: float

class InvalidIngredients(BaseModel):
    ingredients: list[AnalysisIngredient]
