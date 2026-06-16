import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test")

from fastapi.testclient import TestClient

import app as app_module
from models.meal_analysis import AllNutrients, AnalysisIngredient, FoodPortion


class FakeChatCompletions:
    def __init__(self, content: str):
        self._content = content

    def create(self, *args, **kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self._content)
                )
            ]
        )


class FakeOpenAIClient:
    def __init__(self, content: str):
        self.chat = SimpleNamespace(completions=FakeChatCompletions(content))


def make_ingredient(description: str, quantity: float, protein_per_100g: float, quality_score: float = 88.0):
    return AnalysisIngredient(
        fdc_id=123,
        description=description,
        amount=quantity,
        selected_portion_id=0,
        portions=[
            FoodPortion(
                id=0,
                gram_weight=1.0,
                amount=1.0,
                modifier="grams",
            )
        ],
        nutrients=AllNutrients(
            protein_in_grams=protein_per_100g,
            leucine_in_grams=0.0,
            carbohydrates_in_grams=0.0,
            omega3s_in_grams=0.0,
            fat_in_grams=0.0,
            iron_in_milligrams=0.0,
            zinc_in_milligrams=0.0,
            fermented_food_servings=0.0,
            fiber_in_grams=0.0,
            collagen_in_grams=0.0,
            vitamin_c_in_milligrams=0.0,
            vitamin_a_in_micrograms=0.0,
            vitamin_e_in_milligrams=0.0,
            vitamin_d_in_micrograms=0.0,
            selenium_in_micrograms=0.0,
            vitamin_b12_in_micrograms=0.0,
            vitamin_b6_in_milligrams=0.0,
            copper_in_milligrams=0.0,
            folate_in_micrograms=0.0,
            sodium_in_milligrams=0.0,
            potassium_in_milligrams=0.0,
            magnesium_in_milligrams=0.0,
            vitamin_b1_in_milligrams=0.0,
            vitamin_b2_in_milligrams=0.0,
            vitamin_b3_in_milligrams=0.0,
            vitamin_b5_in_milligrams=0.0,
            vitamin_k_in_micrograms=0.0,
            calcium_in_milligrams=0.0,
            manganese_in_milligrams=0.0,
            phosphorus_in_milligrams=0.0,
        ),
        processing_score=quality_score,
        quality_score=quality_score,
    )


class MealDescriptionEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app_module.app)

    def test_explicit_quantities_are_used_and_shape_matches_analysis_meal(self):
        content = """
        {
          "name": "Chicken and rice",
          "ingredients": [
            {"name": "Chicken thigh", "quantity_in_grams": 80.0},
            {"name": "White rice", "quantity_in_grams": 120.0}
          ]
        }
        """

        calls = []

        def fake_search_food(name, quantity):
            calls.append((name, quantity))
            if name == "Chicken thigh":
                return make_ingredient(name, quantity, protein_per_100g=2.0)
            return make_ingredient(name, quantity, protein_per_100g=1.0)

        with patch.object(app_module, "client", FakeOpenAIClient(content)), patch.object(
            app_module, "search_food", fake_search_food
        ):
            response = self.client.post("/meal-description", json={"description": "80g chicken thigh and 120g white rice"})

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("ingredients_new", data)
        self.assertIn("protein_float", data)
        self.assertIn("quality_score", data)
        self.assertEqual(calls, [("Chicken thigh", 80.0), ("White rice", 120.0)])
        self.assertEqual(data["name"], "Chicken and rice")
        self.assertAlmostEqual(data["protein_float"], 2.8, places=2)
        self.assertEqual(len(data["ingredients_new"]), 2)

    def test_missing_quantities_default_to_100g(self):
        content = """
        {
          "name": "Apple and yogurt",
          "ingredients": [
            {"name": "Apple"},
            {"name": "Greek yogurt"}
          ]
        }
        """

        calls = []

        def fake_search_food(name, quantity):
            calls.append((name, quantity))
            return make_ingredient(name, quantity, protein_per_100g=1.0)

        with patch.object(app_module, "client", FakeOpenAIClient(content)), patch.object(
            app_module, "search_food", fake_search_food
        ):
            response = self.client.post("/meal-description", json={"description": "apple and yogurt"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, [("Apple", 100.0), ("Greek yogurt", 100.0)])

    def test_quantity_changes_scale_nutrients(self):
        one_hundred = """
        {
          "name": "Chicken",
          "ingredients": [
            {"name": "Chicken thigh", "quantity_in_grams": 100.0}
          ]
        }
        """
        fifty = """
        {
          "name": "Chicken",
          "ingredients": [
            {"name": "Chicken thigh", "quantity_in_grams": 50.0}
          ]
        }
        """

        def fake_search_food(name, quantity):
            return make_ingredient(name, quantity, protein_per_100g=2.0)

        with patch.object(app_module, "search_food", fake_search_food):
            with patch.object(app_module, "client", FakeOpenAIClient(one_hundred)):
                response_100 = self.client.post("/meal-description", json={"description": "100g chicken thigh"})
            with patch.object(app_module, "client", FakeOpenAIClient(fifty)):
                response_50 = self.client.post("/meal-description", json={"description": "50g chicken thigh"})

        self.assertEqual(response_100.status_code, 200)
        self.assertEqual(response_50.status_code, 200)
        self.assertAlmostEqual(response_100.json()["protein_float"], 2.0, places=2)
        self.assertAlmostEqual(response_50.json()["protein_float"], 1.0, places=2)

    def test_composite_food_bypasses_search_food(self):
        content = """
        {
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
          "vitamin_d_in_micrograms": 0.0,
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
        }
        """

        with patch.object(app_module, "client", FakeOpenAIClient(content)), patch.object(
            app_module, "search_food"
        ) as search_food_mock:
            response = self.client.post("/meal-description", json={"description": "a muffin"})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(search_food_mock.called)
        data = response.json()
        self.assertEqual(data["name"], "Muffin")
        self.assertEqual(data["ingredients_new"], [])
        self.assertAlmostEqual(data["protein_float"], 7.2, places=2)
        self.assertAlmostEqual(data["vitamin_d_float"], 0.0, places=2)
        self.assertAlmostEqual(data["quality_score"], 30.0, places=2)

    def test_blank_description_is_rejected(self):
        response = self.client.post("/meal-description", json={"description": "   "})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Description cannot be empty.")


if __name__ == "__main__":
    unittest.main()
