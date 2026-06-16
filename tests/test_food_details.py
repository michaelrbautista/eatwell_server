import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test")

from fastapi.testclient import TestClient

import app as app_module
import query_utils


class FoodDetailsAndSearchScoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self._build_db(self.db_path)

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

    def _build_db(self, path: str):
        conn = sqlite3.connect(path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE sr_legacy_food (
                fdc_id INTEGER PRIMARY KEY,
                data_type TEXT,
                description TEXT,
                fermented_food_serving_size REAL,
                collagen REAL,
                processing_score REAL,
                bioavailability_score REAL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE sr_legacy_food_portion (
                id INTEGER PRIMARY KEY,
                fdc_id INTEGER,
                gram_weight REAL,
                amount REAL,
                modifier TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE sr_legacy_nutrient (
                id INTEGER PRIMARY KEY,
                nutrient_nbr TEXT,
                name TEXT,
                unit_name TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE sr_legacy_food_nutrient (
                id INTEGER PRIMARY KEY,
                fdc_id INTEGER,
                nutrient_id INTEGER,
                amount REAL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE off_food (
                code TEXT PRIMARY KEY,
                product_name TEXT,
                vitamin_d_100g REAL
            )
            """
        )

        cursor.execute(
            """
            INSERT INTO sr_legacy_food (
                fdc_id, data_type, description, fermented_food_serving_size,
                collagen, processing_score, bioavailability_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (123, "SR Legacy", "Test Food", 25.0, 1.5, 42.0, 88.5),
        )
        cursor.executemany(
            """
            INSERT INTO sr_legacy_food (
                fdc_id, data_type, description, fermented_food_serving_size,
                collagen, processing_score, bioavailability_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (124, "SR Legacy", "Bread", 25.0, 0.0, 10.0, 20.0),
                (125, "SR Legacy", "Bread, whole wheat", 25.0, 0.0, 11.0, 21.0),
                (126, "SR Legacy", "Bread, white", 25.0, 0.0, 12.0, 22.0),
                (127, "SR Legacy", "Breadfruit", 25.0, 0.0, 13.0, 23.0),
                (128, "SR Legacy", "Breadsticks", 25.0, 0.0, 14.0, 24.0),
            ],
        )
        cursor.execute(
            """
            INSERT INTO sr_legacy_food_portion (id, fdc_id, gram_weight, amount, modifier)
            VALUES (?, ?, ?, ?, ?)
            """,
            (9001, 123, 150.0, 1.0, "cup"),
        )
        cursor.execute(
            """
            INSERT INTO sr_legacy_nutrient (id, nutrient_nbr, name, unit_name)
            VALUES (?, ?, ?, ?)
            """,
            (1, "203", "Protein", "g"),
        )
        cursor.executemany(
            """
            INSERT INTO sr_legacy_nutrient (id, nutrient_nbr, name, unit_name)
            VALUES (?, ?, ?, ?)
            """,
            [
                (2, "324", "Vitamin D (D2 + D3), International Units", "IU"),
                (3, "328", "Vitamin D (D2 + D3)", "UG"),
            ],
        )
        cursor.execute(
            """
            INSERT INTO sr_legacy_food_nutrient (id, fdc_id, nutrient_id, amount)
            VALUES (?, ?, ?, ?)
            """,
            (1, 123, 1, 10.0),
        )
        cursor.executemany(
            """
            INSERT INTO sr_legacy_food_nutrient (id, fdc_id, nutrient_id, amount)
            VALUES (?, ?, ?, ?)
            """,
            [
                (2, 123, 2, 40.0),
                (3, 123, 3, 2.5),
            ],
        )
        cursor.execute(
            """
            INSERT INTO off_food (code, product_name, vitamin_d_100g)
            VALUES (?, ?, ?)
            """,
            ("OFF123", "Off Test Food", 4.2),
        )

        conn.commit()
        conn.close()

    def test_food_details_returns_bioavailability_score(self):
        with patch.dict(os.environ, {"DB_PATH": self.db_path}, clear=False):
            client = TestClient(app_module.app)
            response = client.get("/food/123")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["processing_score"], 42.0)
        self.assertEqual(data["bioavailability_score"], 88.5)
        self.assertEqual(data["quality_score"], 42.0)

    def test_food_details_returns_vitamin_d(self):
        with patch.dict(os.environ, {"DB_PATH": self.db_path}, clear=False):
            client = TestClient(app_module.app)
            response = client.get("/food/123")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["nutrients"]["vitamin_d_in_micrograms"], 2.5)

    def test_off_food_details_returns_vitamin_d(self):
        with patch.dict(os.environ, {"DB_PATH": self.db_path}, clear=False):
            client = TestClient(app_module.app)
            response = client.get("/food/off/OFF123")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["description"], "Off Test Food")
        self.assertEqual(data["nutrients"]["vitamin_d_in_micrograms"], 4.2)

    def test_usda_search_places_bread_and_bread_comma_rows_first(self):
        def assert_order(payload, key):
            descriptions = [food["description"] for food in payload[key]]
            self.assertEqual(
                descriptions,
                [
                    "Bread",
                    "Bread, white",
                    "Bread, whole wheat",
                    "Breadfruit",
                    "Breadsticks",
                ],
            )

        with patch.dict(os.environ, {"DB_PATH": self.db_path}, clear=False), patch(
            "query_service.fts_search",
            return_value=[
                (127, "sr_legacy_food", "Breadfruit"),
                (128, "sr_legacy_food", "Breadsticks"),
            ],
        ), patch("query_service.fuzzy_search", return_value=[]):
            client = TestClient(app_module.app)
            search_foods_response = client.post("/search-foods", params={"term": "Bread"})
            search_database_response = client.post("/search-database", params={"term": "Bread"})
            search_database_v2_response = client.post("/search-database-v2", params={"term": "Bread"})

        self.assertEqual(search_foods_response.status_code, 200)
        self.assertEqual(search_database_response.status_code, 200)
        self.assertEqual(search_database_v2_response.status_code, 200)

        assert_order(search_foods_response.json(), "foods")
        assert_order(search_database_response.json(), "foods")
        assert_order(search_database_v2_response.json(), "usda_foods")

    def test_search_food_returns_bioavailability_score(self):
        with patch.object(query_utils, "DB_PATH", self.db_path), patch.object(
            query_utils,
            "try_exact_match",
            return_value={
                "fdc_id": 123,
                "data_type": "sr_legacy_food",
                "description": "Test Food",
                "similarity": 1.0,
            },
        ):
            ingredient = query_utils.search_food("Test Food", 100.0)

        self.assertIsNotNone(ingredient)
        self.assertEqual(ingredient.processing_score, 42.0)
        self.assertEqual(ingredient.bioavailability_score, 88.5)
        self.assertEqual(ingredient.quality_score, 42.0)

    def test_search_foods_endpoint_returns_bioavailability_score(self):
        with patch.dict(os.environ, {"DB_PATH": self.db_path}, clear=False), patch(
            "query_service.fts_search",
            return_value=[(123, "SR Legacy", "Test Food")],
        ), patch("query_service.fuzzy_search", return_value=[]):
            client = TestClient(app_module.app)
            response = client.post("/search-foods", params={"term": "Test Food"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["foods"]), 1)
        food = data["foods"][0]
        self.assertEqual(food["processing_score"], 42.0)
        self.assertEqual(food["bioavailability_score"], 88.5)
        self.assertEqual(food["quality_score"], 42.0)

    def test_search_database_v2_returns_bioavailability_score_for_usda_foods(self):
        with patch.dict(os.environ, {"DB_PATH": self.db_path}, clear=False), patch(
            "query_service.fts_search",
            return_value=[(123, "SR Legacy", "Test Food")],
        ), patch("query_service.fuzzy_search", return_value=[]), patch.object(
            app_module,
            "_search_off_foods",
            return_value=[],
        ):
            client = TestClient(app_module.app)
            response = client.post("/search-database-v2", params={"term": "Test Food"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["usda_foods"]), 1)
        food = data["usda_foods"][0]
        self.assertEqual(food["processing_score"], 42.0)
        self.assertEqual(food["bioavailability_score"], 88.5)
        self.assertEqual(food["quality_score"], 42.0)
        self.assertEqual(data["off_foods"], [])


if __name__ == "__main__":
    unittest.main()
