import unittest

from src.market_freshness import (
    assess_market_freshness,
    assess_snapshot_freshness,
)


NOW_MS = 1_800_000_000_000


class TestMarketFreshness(unittest.TestCase):

    def test_recent_timestamp_passes(self):
        result = assess_market_freshness(
            NOW_MS - 30_000,
            now_ms=NOW_MS,
        )
        self.assertTrue(result["verified"])
        self.assertEqual(result["status"], "within_configured_age")
        self.assertEqual(result["age_seconds"], 30.0)

    def test_timestamp_at_exact_age_limit_passes(self):
        result = assess_market_freshness(
            NOW_MS - 120_000,
            now_ms=NOW_MS,
            max_age_seconds=120,
        )
        self.assertTrue(result["verified"])
        self.assertEqual(result["age_seconds"], 120.0)

    def test_stale_timestamp_fails(self):
        result = assess_market_freshness(
            NOW_MS - 120_001,
            now_ms=NOW_MS,
            max_age_seconds=120,
        )
        self.assertFalse(result["verified"])
        self.assertEqual(result["status"], "stale_timestamp")

    def test_future_timestamp_fails_by_default(self):
        result = assess_market_freshness(
            NOW_MS + 1,
            now_ms=NOW_MS,
        )
        self.assertFalse(result["verified"])
        self.assertEqual(result["status"], "future_timestamp")

    def test_configured_future_clock_skew_is_respected(self):
        result = assess_market_freshness(
            NOW_MS + 2_000,
            now_ms=NOW_MS,
            max_future_skew_seconds=2,
        )
        self.assertTrue(result["verified"])

    def test_missing_and_invalid_timestamps_fail(self):
        for value in (None, "invalid", True, 0, -1, float("nan"),
                      float("inf"), float("-inf")):
            with self.subTest(value=value):
                result = assess_market_freshness(
                    value,
                    now_ms=NOW_MS,
                )
                self.assertFalse(result["verified"])
                self.assertEqual(
                    result["status"],
                    "invalid_or_missing_timestamp",
                )

    def test_invalid_reference_time_fails(self):
        result = assess_market_freshness(
            NOW_MS,
            now_ms=None,
        )
        self.assertFalse(result["verified"])
        self.assertEqual(result["status"], "invalid_reference_time")

    def test_invalid_threshold_raises(self):
        for value in (-1, True, float("nan"), float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    assess_market_freshness(
                        NOW_MS,
                        now_ms=NOW_MS,
                        max_age_seconds=value,
                    )

    def test_stock_and_index_are_checked_independently(self):
        result = assess_snapshot_freshness(
            {"api_timestamp_ms": NOW_MS - 30_000},
            {"api_timestamp_ms": NOW_MS - 180_000},
            now_ms=NOW_MS,
        )
        self.assertFalse(result["verified"])
        self.assertTrue(result["stock"]["verified"])
        self.assertFalse(result["index"]["verified"])
        self.assertEqual(result["index"]["status"], "stale_timestamp")

    def test_missing_index_result_fails_combined_check(self):
        result = assess_snapshot_freshness(
            {"api_timestamp_ms": NOW_MS - 30_000},
            None,
            now_ms=NOW_MS,
        )
        self.assertFalse(result["verified"])
        self.assertTrue(result["stock"]["verified"])
        self.assertFalse(result["index"]["verified"])


if __name__ == "__main__":
    unittest.main()
