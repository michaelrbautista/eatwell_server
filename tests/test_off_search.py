import os
import sqlite3
import unittest


os.environ.setdefault("OPENAI_API_KEY", "test")

from app import _search_off_foods
from query_utils import _build_nonempty_choices


class OffSearchNullHandlingTests(unittest.TestCase):
    def _make_conn(self):
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE off_food (
                rowid INTEGER PRIMARY KEY,
                code TEXT,
                product_name TEXT,
                brands TEXT,
                brand_product_name TEXT,
                normalized_product_name TEXT,
                normalized_brands TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE VIRTUAL TABLE off_food_search
            USING fts5(product_name, brands, content='')
            """
        )

        cursor.execute(
            """
            INSERT INTO off_food (
                rowid, code, product_name, brands,
                brand_product_name, normalized_product_name, normalized_brands
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "4099100123173",
                "Edamame spaghetti",
                "Aldi",
                "edamame spaghetti",
                "edamame spaghetti",
                "aldi",
            ),
        )
        cursor.execute(
            "INSERT INTO off_food_search(rowid, product_name, brands) VALUES (?, ?, ?)",
            (1, "edamame spaghetti", "aldi"),
        )

        conn.commit()
        self.addCleanup(conn.close)
        return conn

    def test_nonempty_choices_ignore_null_and_blank_values(self):
        choices = _build_nonempty_choices(
            [
                (1, None),
                (2, ""),
                (3, "   "),
                (4, "edamame spaghetti"),
            ]
        )

        self.assertEqual(choices, {4: "edamame spaghetti"})

    def test_edamame_spaghetti_search_does_not_crash_on_contentless_fts_rows(self):
        conn = self._make_conn()

        results = _search_off_foods("Edamame spaghetti", conn, limit=20)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["product_name"], "Edamame spaghetti")
        self.assertEqual(results[0]["brands"], "Aldi")


if __name__ == "__main__":
    unittest.main()
