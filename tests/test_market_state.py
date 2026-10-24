
import unittest

from src.market_state import assess_market_state


def make_indices(changes):
    codes = ["000001.SH", "399001.SZ", "000300.SH"]
    return [
        {
            "thscode": code,
            "price_change_ratio_pct": change,
        }
        for code, change in zip(codes, changes)
    ]


class TestAssessMarketState(unittest.TestCase):

    def test_broad_strength_requires_breadth_and_index_confirmation(self):
        breadth = {
            "advance_ratio_pct": 75.0,
            "decline_ratio_pct": 20.0,
            "valid_change_count": 5000,
        }
        result = assess_market_state(
            breadth,
            make_indices([1.2, 0.8, 0.3]),
        )
        self.assertEqual(result["state"], "广泛偏强")
        self.assertEqual(result["metrics"]["positive_indices"], 3)

    def test_breadth_strength_without_index_confirmation(self):
        breadth = {
            "advance_ratio_pct": 65.0,
            "decline_ratio_pct": 30.0,
            "valid_change_count": 5000,
        }
        result = assess_market_state(
            breadth,
            make_indices([0.5, -0.2, 0.0]),
        )
        self.assertEqual(result["state"], "个股广度偏强，指数确认不足")

    def test_broad_weakness(self):
        breadth = {
            "advance_ratio_pct": 20.0,
            "decline_ratio_pct": 75.0,
            "valid_change_count": 5000,
        }
        result = assess_market_state(
            breadth,
            make_indices([-1.2, -0.8, -0.3]),
        )
        self.assertEqual(result["state"], "广泛偏弱")

    def test_middle_breadth_is_neutral_or_divergent(self):
        breadth = {
            "advance_ratio_pct": 50.0,
            "decline_ratio_pct": 45.0,
            "valid_change_count": 5000,
        }
        result = assess_market_state(
            breadth,
            make_indices([0.5, -0.2, 0.0]),
        )
        self.assertEqual(result["state"], "中性或涨跌分化")

    def test_missing_index_is_rejected(self):
        breadth = {
            "advance_ratio_pct": 60.0,
            "decline_ratio_pct": 35.0,
            "valid_change_count": 5000,
        }
        with self.assertRaisesRegex(ValueError, "不完整"):
            assess_market_state(breadth, make_indices([0.5, -0.2])[:2])

    def test_invalid_ratio_is_rejected(self):
        breadth = {
            "advance_ratio_pct": 120.0,
            "decline_ratio_pct": 10.0,
            "valid_change_count": 5000,
        }
        with self.assertRaises(ValueError):
            assess_market_state(breadth, make_indices([0.5, 0.2, 0.1]))

    def test_result_includes_evidence_and_limitations(self):
        breadth = {
            "advance_ratio_pct": 60.0,
            "decline_ratio_pct": 35.0,
            "valid_change_count": 5000,
        }
        result = assess_market_state(
            breadth,
            make_indices([0.5, 0.2, 0.1]),
        )
        self.assertTrue(result["evidence"])
        self.assertTrue(result["limitations"])
        self.assertEqual(len(result["state_switch_conditions"]), 1)
        self.assertFalse(result["method"]["historically_validated"])

    def test_switch_conditions_match_current_state_thresholds(self):
        cases = [
            {
                "advance": 75.0,
                "indices": [1.2, 0.8, 0.3],
                "expected_state": "广泛偏强",
                "expected_text": "70%",
            },
            {
                "advance": 69.9,
                "indices": [1.2, 0.8, 0.3],
                "expected_state": "偏强",
                "expected_text": "55%",
            },
            {
                "advance": 60.0,
                "indices": [1.2, 0.8, -0.3],
                "expected_state": "偏强",
                "expected_text": "55%",
            },
            {
                "advance": 20.0,
                "indices": [-1.2, -0.8, -0.3],
                "expected_state": "广泛偏弱",
                "expected_text": "30%",
            },
            {
                "advance": 40.0,
                "indices": [-1.2, -0.8, -0.3],
                "expected_state": "偏弱",
                "expected_text": "45%",
            },
            {
                "advance": 65.0,
                "indices": [0.5, -0.2, 0.0],
                "expected_state": "个股广度偏强，指数确认不足",
                "expected_text": "55%",
            },
        ]

        for case in cases:
            with self.subTest(state=case["expected_state"]):
                breadth = {
                    "advance_ratio_pct": case["advance"],
                    "decline_ratio_pct": 100.0 - case["advance"],
                    "valid_change_count": 5000,
                }

                result = assess_market_state(
                    breadth,
                    make_indices(case["indices"]),
                )

                self.assertEqual(
                    result["state"],
                    case["expected_state"],
                )
                self.assertEqual(
                    len(result["state_switch_conditions"]),
                    1,
                )
                self.assertIn(
                    case["expected_text"],
                    result["state_switch_conditions"][0],
                )


if __name__ == "__main__":
    unittest.main()
