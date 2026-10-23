
import unittest

from src.data_quality import assess_snapshot_quality


def make_stock_result():
    """构造 100 条模拟记录，其中 1 条缺少涨跌幅。"""
    items = [
        {
            "thscode": f"{i:06d}.SZ",
            "price_change_ratio_pct": 1.2 if i % 2 == 0 else -0.5,
        }
        for i in range(1, 100)
    ]

    items.append({
        "thscode": "900001.SH",
        "price_change_ratio_pct": None,
    })

    return {
        "items": items,
        "api_reported_total": 100,
        "actual_record_count": 100,
        "api_timestamp_ms": 10000,
        "page_timestamps": [10000, 10000],
    }


class TestSnapshotQuality(unittest.TestCase):

    def test_valid_snapshot_passes_basic_quality_gate(self):
        result = assess_snapshot_quality(make_stock_result())

        self.assertTrue(result["research_ready"])
        self.assertTrue(result["checks"]["record_count_matches"])
        self.assertTrue(result["checks"]["no_duplicate_codes"])
        self.assertEqual(result["metrics"]["valid_change_count"], 99)
        self.assertEqual(result["metrics"]["missing_change_count"], 1)
        self.assertAlmostEqual(
            result["metrics"]["missing_ratio_pct"], 1.0
        )

    def test_count_mismatch_blocks_readiness(self):
        stock = make_stock_result()
        stock["api_reported_total"] = 101

        result = assess_snapshot_quality(stock)

        self.assertFalse(result["research_ready"])
        self.assertFalse(result["checks"]["record_count_matches"])

    def test_duplicate_codes_block_readiness(self):
        stock = make_stock_result()
        stock["items"][1]["thscode"] = stock["items"][0]["thscode"]

        result = assess_snapshot_quality(stock)

        self.assertFalse(result["research_ready"])
        self.assertFalse(result["checks"]["no_duplicate_codes"])

    def test_timestamp_difference_warns_but_does_not_alone_block(self):
        stock = make_stock_result()
        stock["page_timestamps"] = [10000, 12000]

        result = assess_snapshot_quality(stock)

        self.assertTrue(result["research_ready"])
        self.assertFalse(result["metrics"]["page_timestamps_consistent"])
        self.assertEqual(
            result["metrics"]["page_timestamp_spread_seconds"], 2.0
        )
        self.assertTrue(result["warnings"])

    def test_invalid_page_timestamp_blocks_readiness(self):
        stock = make_stock_result()
        stock["page_timestamps"] = [10000, None]

        result = assess_snapshot_quality(stock)

        self.assertFalse(result["research_ready"])
        self.assertFalse(result["checks"]["page_timestamps_valid"])

    def test_market_session_is_never_assumed_verified(self):
        result = assess_snapshot_quality(make_stock_result())

        self.assertFalse(result["market_session_verified"])

    def test_page_timestamp_spread_over_threshold_blocks_readiness(self):
        stock = make_stock_result()
        stock["page_timestamps"] = [10000, 80000]

        result = assess_snapshot_quality(
            stock,
            max_page_timestamp_spread_seconds=60,
        )

        self.assertFalse(result["research_ready"])
        self.assertFalse(
            result["checks"]["page_timestamp_spread_within_threshold"]
        )

    def test_invalid_index_result_does_not_raise_unbound_local_error(self):
        result = assess_snapshot_quality(make_stock_result(), index_result={})

        self.assertFalse(result["research_ready"])
        self.assertFalse(result["checks"]["api_timestamps_comparable"])

    def test_stock_index_time_gap(self):
        stock = make_stock_result()
        index = {"api_timestamp_ms": 25000}

        result = assess_snapshot_quality(stock, index)

        self.assertEqual(
            result["metrics"]["stock_index_api_gap_seconds"], 15.0
        )


if __name__ == "__main__":
    unittest.main()
