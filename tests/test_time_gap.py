import unittest

from src.time_utils import calculate_time_gap_seconds


class TestTimeGap(unittest.TestCase):

    def test_normal_timestamps(self):
        self.assertEqual(
            calculate_time_gap_seconds(
                1792779328000, 1792780355000
            ),
            1027.0,
        )

    def test_missing_timestamp(self):
        self.assertIsNone(
            calculate_time_gap_seconds(
                None, 1792780355000
            )
        )

    def test_invalid_format(self):
        self.assertIsNone(
            calculate_time_gap_seconds(
                "invalid", 1792780355000
            )
        )

    def test_nan(self):
        self.assertIsNone(
            calculate_time_gap_seconds(
                float("nan"), 1792780355000
            )
        )

    def test_infinity(self):
        self.assertIsNone(
            calculate_time_gap_seconds(
                float("inf"), 1792780355000
            )
        )

    def test_same_timestamp(self):
        self.assertEqual(
            calculate_time_gap_seconds(
                100000, 100000
            ),
            0.0,
        )


if __name__ == "__main__":
    unittest.main()