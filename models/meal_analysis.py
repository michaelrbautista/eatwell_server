from pydantic import BaseModel, Field

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
    vitamin_b12_in_micrograms: float
    iodine_in_micrograms: float
    vitamin_b6_in_milligrams: float
    copper_in_milligrams: float
    folate_in_micrograms: float
    sodium_in_milligrams: float
    potassium_in_milligrams: float
    magnesium_in_milligrams: float
    vitamin_b1_in_milligrams: float
    vitamin_b2_in_milligrams: float
    vitamin_b3_in_milligrams: float
    vitamin_b5_in_milligrams: float
    vitamin_k_in_micrograms: float
    calcium_in_milligrams: float
    manganese_in_milligrams: float
    phosphorus_in_milligrams: float

class AnalysisIngredient(BaseModel):
    fdc_id: int
    description: str
    amount: float
    selected_portion_id: int
    portions: list[FoodPortion]
    nutrients: AllNutrients
    processing_score: float | None = None
    bioavailability_score: float | None = None
    quality_score: float | None = None

class AnalysisMeal(BaseModel):
    id: str = ""
    created_at: str = ""
    user_id: str = ""
    name: str
    image_path: str = ""

    ingredients_new: list[AnalysisIngredient]

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
    vitamin_b12_float: float = 0.0
    iodine_float: float = 0.0
    vitamin_b6_float: float = 0.0
    copper_float: float = 0.0
    folate_float: float = 0.0
    sodium_float: float = 0.0
    potassium_float: float = 0.0
    magnesium_float: float = 0.0
    vitamin_b1_float: float = 0.0
    vitamin_b2_float: float = 0.0
    vitamin_b3_float: float = 0.0
    vitamin_b5_float: float = 0.0
    vitamin_k_float: float = 0.0
    calcium_float: float = 0.0
    manganese_float: float = 0.0
    phosphorus_float: float = 0.0
    quality_score: float

    class Config:
        validate_by_name = True

class InvalidIngredients(BaseModel):
    ingredients: list[AnalysisIngredient]
