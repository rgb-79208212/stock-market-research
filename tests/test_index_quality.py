import unittest
import pandas as pd


EXPECTED_INDEX_CODES = {
    "000001.SH",
    "399001.SZ",
    "000300.SH",
}


def check_index_data(index_items, index_snapshot_available=True):
    index_changes = []
    seen_index_codes = set()
    duplicate_index_codes = []
    invalid_index_codes = []

    if index_snapshot_available:
        for item in index_items:
            if not isinstance(item, dict):
                continue

            code = item.get("thscode")

            if not isinstance(code, str) or not code.strip():
                invalid_index_codes.append("代码缺失")
                continue

            if code in seen_index_codes:
                duplicate_index_codes.append(code)
                continue

            seen_index_codes.add(code)

            if code not in EXPECTED_INDEX_CODES:
                continue

            value = item.get("price_change_ratio_pct")

            try:
                value = float(value)
            except (TypeError, ValueError, OverflowError):
                invalid_index_codes.append(code)
                continue

            if not pd.notna(value):
                invalid_index_codes.append(code)
                continue

            index_changes.append({
                "code": code,
                "change_pct": value,
            })

    valid_codes = {item["code"] for item in index_changes}
    missing_codes = EXPECTED_INDEX_CODES - seen_index_codes
    invalid_or_missing_codes = EXPECTED_INDEX_CODES - valid_codes

    complete = (
        index_snapshot_available
        and not missing_codes
        and not invalid_or_missing_codes
        and not duplicate_index_codes
    )

    return complete, missing_codes, invalid_or_missing_codes


class TestIndexQuality(unittest.TestCase):

    def setUp(self):
        self.normal_data = [
            {
                "thscode": "000001.SH",
                "price_change_ratio_pct": 0.5,
            },
            {
                "thscode": "399001.SZ",
                "price_change_ratio_pct": 1.2,
            },
            {
                "thscode": "000300.SH",
                "price_change_ratio_pct": -0.2,
            },
        ]

    def test_all_three_indices_valid(self):
        result = check_index_data(self.normal_data)
        self.assertTrue(result[0])

    def test_missing_expected_index(self):
        missing_data = self.normal_data[:2]
        result = check_index_data(missing_data)

        self.assertFalse(result[0])
        self.assertIn("000300.SH", result[1])

    def test_invalid_change_ratio(self):
        invalid_data = [
            dict(item) for item in self.normal_data
        ]
        invalid_data[2]["price_change_ratio_pct"] = None

        result = check_index_data(invalid_data)

        self.assertFalse(result[0])
        self.assertIn("000300.SH", result[2])


if __name__ == "__main__":
    unittest.main()