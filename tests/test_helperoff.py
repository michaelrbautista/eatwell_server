import unittest

from helperoff import get_off_nutrients


class GetOffNutrientsTests(unittest.TestCase):
    def test_missing_micronutrients_default_to_zero(self):
        nutrients = get_off_nutrients({})

        self.assertEqual(nutrients.sodium_in_milligrams, 0.0)
        self.assertEqual(nutrients.vitamin_c_in_milligrams, 0.0)
        self.assertEqual(nutrients.vitamin_a_in_micrograms, 0.0)
        self.assertEqual(nutrients.vitamin_d_in_micrograms, 0.0)

    def test_invalid_and_none_micronutrients_default_to_zero(self):
        nutrients = get_off_nutrients(
            {
                "sodium_100g": None,
                "vitamin_c_100g": "not-a-number",
                "vitamin_d_100g": "invalid",
            }
        )

        self.assertEqual(nutrients.sodium_in_milligrams, 0.0)
        self.assertEqual(nutrients.vitamin_c_in_milligrams, 0.0)
        self.assertEqual(nutrients.vitamin_d_in_micrograms, 0.0)

    def test_numeric_micronutrients_are_preserved(self):
        nutrients = get_off_nutrients(
            {
                "sodium_100g": "12.5",
                "vitamin_c_100g": 8,
                "vitamin_a_100g": 0,
                "vitamin_d_100g": 2.5,
            }
        )

        self.assertEqual(nutrients.sodium_in_milligrams, 12.5)
        self.assertEqual(nutrients.vitamin_c_in_milligrams, 8.0)
        self.assertEqual(nutrients.vitamin_a_in_micrograms, 0.0)
        self.assertEqual(nutrients.vitamin_d_in_micrograms, 2.5)


if __name__ == "__main__":
    unittest.main()
