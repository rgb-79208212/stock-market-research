
import unittest

from src.market_analysis import calculate_market_breadth


class TestCalculateMarketBreadth(unittest.TestCase):

    def test_counts_advancers_decliners_and_unchanged(self):
        items = [
            {"thscode": "AAA", "price_change_ratio_pct": 1.5},
            {"thscode": "BBB", "price_change_ratio_pct": -2.0},
            {"thscode": "CCC", "price_change_ratio_pct": 0},
        ]

        result = calculate_market_breadth(items)

        self.assertEqual(result["advancers"], 1)
        self.assertEqual(result["decliners"], 1)
        self.assertEqual(result["unchanged"], 1)
        self.assertEqual(result["advance_ratio_pct"], 33.33)
        self.assertEqual(result["decline_ratio_pct"], 33.33)
        self.assertEqual(result["unchanged_ratio_pct"], 33.33)

    def test_excludes_missing_change_from_denominator(self):
        items = [
            {"thscode": "AAA", "price_change_ratio_pct": 1.0},
            {"thscode": "BBB", "price_change_ratio_pct": -1.0},
            {"thscode": "CCC", "price_change_ratio_pct": None},
        ]

        result = calculate_market_breadth(items)

        self.assertEqual(result["valid_change_count"], 2)
        self.assertEqual(result["missing_change_count"], 1)
        self.assertEqual(result["advance_ratio_pct"], 50.0)
        self.assertEqual(result["decline_ratio_pct"], 50.0)

    def test_rejects_empty_input(self):
        with self.assertRaises(ValueError):
            calculate_market_breadth([])

    def test_rejects_duplicate_codes(self):
        items = [
            {"thscode": "AAA", "price_change_ratio_pct": 1.0},
            {"thscode": "AAA", "price_change_ratio_pct": -1.0},
        ]

        with self.assertRaisesRegex(ValueError, "重复证券代码"):
            calculate_market_breadth(items)

    def test_rejects_boolean_change(self):
        items = [
            {"thscode": "AAA", "price_change_ratio_pct": True},
        ]

        with self.assertRaises(ValueError):
            calculate_market_breadth(items)

    def test_rejects_non_finite_change(self):
        items = [
            {"thscode": "AAA", "price_change_ratio_pct": float("nan")},
        ]

        with self.assertRaises(ValueError):
            calculate_market_breadth(items)

    def test_rejects_missing_security_code(self):
        items = [
            {"price_change_ratio_pct": 1.0},
        ]

        with self.assertRaises(ValueError):
            calculate_market_breadth(items)


if __name__ == "__main__":
    unittest.main()
