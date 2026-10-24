
import unittest

from src.research_report import build_research_report


class TestResearchReport(unittest.TestCase):

    def make_inputs(self):
        stock = {
            "items": [{"thscode": "000001.SZ"}],
            "api_timestamp_ms": 100000,
            "source_api": "test_stock_api",
        }
        index = {
            "items": [{"thscode": "000001.SH"}],
            "api_timestamp_ms": 100000,
            "source_api": "test_index_api",
        }
        quality = {
            "research_ready": True,
            "checks": {
                "record_count_matches": True,
                "page_timestamps_valid": True,
                "page_timestamps_consistent": True,
                "page_timestamp_spread_within_threshold": True,
                "api_timestamps_comparable": True,
                "api_gap_within_threshold": True,
            },
            "metrics": {
                "page_timestamps_consistent": True,
                "page_timestamp_spread_seconds": 0.0,
                "stock_index_api_gap_seconds": 0.0,
            },
            "warnings": [],
            "market_session_verified": False,
        }
        breadth = {
            "valid_change_count": 1,
            "advance_ratio_pct": 100.0,
            "decline_ratio_pct": 0.0,
            "unchanged_ratio_pct": 0.0,
        }
        state = {
            "state": "偏强",
            "rationale": "测试分类理由",
            "evidence": ["测试证据"],
            "metrics": {"advance_ratio_pct": 100.0},
            "index_results": [],
            "state_switch_conditions": ["测试切换条件"],
            "limitations": ["尚未进行历史回测"],
            "method": {"historically_validated": False},
        }
        return stock, index, quality, breadth, state

    def test_build_report_with_quality_passed(self):
        inputs = self.make_inputs()
        report = build_research_report(*inputs)

        self.assertEqual(report["report_version"], "1.0")
        self.assertEqual(report["market_state"]["label"], "偏强")
        self.assertTrue(report["facts"])
        breadth_claims = [
            fact["claim"]
            for fact in report["facts"]
            if fact.get("source") == "calculate_market_breadth"
        ]
        self.assertTrue(
            any("平盘占比为 0.0%" in claim for claim in breadth_claims)
        )
        self.assertTrue(report["interpretations"])
        self.assertTrue(report["hypotheses"])
        self.assertIsNone(
            report["confidence_basis"]["numeric_probability"]
        )
        self.assertFalse(
            report["evidence_quality"]["historically_validated"]
        )
        evidence_quality = report["evidence_quality"]

        self.assertTrue(evidence_quality["page_timestamps_valid"])
        self.assertTrue(
            evidence_quality["page_timestamp_spread_within_threshold"]
        )
        self.assertTrue(evidence_quality["api_timestamps_comparable"])
        self.assertTrue(evidence_quality["api_gap_within_threshold"])

        self.assertTrue(evidence_quality["page_timestamps_consistent"])
        self.assertFalse(evidence_quality["market_session_verified"])
        self.assertFalse(evidence_quality["independent_source_verified"])

    def test_report_uses_consistency_gate_not_metric(self):
        inputs = list(self.make_inputs())
        inputs[2]["checks"]["page_timestamps_consistent"] = False
        inputs[2]["metrics"]["page_timestamps_consistent"] = True

        report = build_research_report(*inputs)

        self.assertFalse(
            report["evidence_quality"]["page_timestamps_consistent"]
        )

    def test_quality_failure_blocks_report(self):
        inputs = list(self.make_inputs())
        inputs[2]["research_ready"] = False

        with self.assertRaises(ValueError):
            build_research_report(*inputs)

    def test_invalid_input_type_is_rejected(self):
        inputs = list(self.make_inputs())
        inputs[3] = None

        with self.assertRaises(ValueError):
            build_research_report(*inputs)


    def test_freshness_pass_is_recorded_in_report(self):
        inputs = self.make_inputs()
        freshness = {
            "verified": True,
            "stock": {
                "verified": True,
                "status": "within_configured_age",
                "age_seconds": 10.0,
            },
            "index": {
                "verified": True,
                "status": "within_configured_age",
                "age_seconds": 12.0,
            },
            "max_age_seconds": 120.0,
        }

        report = build_research_report(
            *inputs,
            freshness_result=freshness,
        )
        quality = report["evidence_quality"]

        self.assertTrue(quality["market_freshness_verified"])
        self.assertEqual(
            quality["stock_timestamp_freshness"]["age_seconds"],
            10.0,
        )
        self.assertEqual(
            quality["index_timestamp_freshness"]["age_seconds"],
            12.0,
        )
        self.assertEqual(quality["freshness_max_age_seconds"], 120.0)

    def test_freshness_failure_adds_warning(self):
        inputs = self.make_inputs()
        freshness = {
            "verified": False,
            "stock": {
                "verified": True,
                "status": "within_configured_age",
                "age_seconds": 10.0,
            },
            "index": {
                "verified": False,
                "status": "stale_timestamp",
                "age_seconds": 180.0,
            },
            "max_age_seconds": 120.0,
        }

        report = build_research_report(
            *inputs,
            freshness_result=freshness,
        )
        quality = report["evidence_quality"]

        self.assertFalse(quality["market_freshness_verified"])
        self.assertTrue(
            any(
                "指数快照" in warning
                and "stale_timestamp" in warning
                for warning in quality["warnings"]
            )
        )

    def test_missing_freshness_result_keeps_legacy_call(self):
        inputs = self.make_inputs()

        report = build_research_report(*inputs)
        quality = report["evidence_quality"]

        self.assertIsNone(quality["stock_timestamp_freshness"])
        self.assertIsNone(quality["index_timestamp_freshness"])
        self.assertFalse(quality["market_freshness_verified"])

    def test_freshness_pass_does_not_bypass_quality_gate(self):
        inputs = list(self.make_inputs())
        inputs[2]["research_ready"] = False

        freshness = {
            "verified": True,
            "stock": {"verified": True, "status": "within_configured_age",
                      "age_seconds": 1.0},
            "index": {"verified": True, "status": "within_configured_age",
                      "age_seconds": 1.0},
            "max_age_seconds": 120.0,
        }

        with self.assertRaises(ValueError):
            build_research_report(
                *inputs,
                freshness_result=freshness,
            )




    def test_report_records_market_session_and_calendar_limits(self):
        inputs = self.make_inputs()
        report = build_research_report(*inputs)

        quality = report["evidence_quality"]

        self.assertIn("stock_market_session", quality)
        self.assertIn("index_market_session", quality)
        self.assertFalse(quality["market_session_verified"])
        self.assertFalse(quality["market_calendar_verified"])

        self.assertTrue(
            any(
                "股票接口" in warning
                for warning in quality["warnings"]
            )
        )
        self.assertTrue(
            any(
                "指数接口" in warning
                for warning in quality["warnings"]
            )
        )

    def test_weekend_timestamp_is_recorded_as_non_trading_time(self):
        inputs = list(self.make_inputs())

        # 2026-10-24 07:55:07 北京时间，对应周六。
        from datetime import datetime
        from zoneinfo import ZoneInfo

        weekend_dt = datetime(
            2026, 10, 24, 7, 55, 7,
            tzinfo=ZoneInfo("Asia/Shanghai"),
        )
        weekend_timestamp_ms = int(
            weekend_dt.timestamp() * 1000
        )

        inputs[0]["api_timestamp_ms"] = weekend_timestamp_ms
        inputs[1]["api_timestamp_ms"] = weekend_timestamp_ms

        report = build_research_report(*inputs)
        quality = report["evidence_quality"]

        self.assertEqual(
            quality["stock_market_session"]["status"],
            "周末（非交易日）",
        )
        self.assertEqual(
            quality["index_market_session"]["status"],
            "周末（非交易日）",
        )
        self.assertFalse(quality["market_calendar_verified"])
        self.assertTrue(
            any("周末" in warning for warning in quality["warnings"])
        )

    def test_missing_snapshot_freshness_cannot_pass(self):
        inputs = self.make_inputs()

        freshness = {
            "verified": True,
            "stock": {
                "verified": True,
                "status": "within_configured_age",
                "age_seconds": 10.0,
            },
            # 故意缺少指数新鲜度结果
            "max_age_seconds": 120.0,
        }

        report = build_research_report(
            *inputs,
            freshness_result=freshness,
        )

        quality = report["evidence_quality"]

        self.assertFalse(quality["market_freshness_verified"])
        self.assertIsNone(quality["index_timestamp_freshness"])
        self.assertTrue(
            any(
                "指数快照" in warning
                for warning in quality["warnings"]
            )
        )

    def test_confidence_reason_matches_page_timestamp_consistency(self):
        consistent_inputs = list(self.make_inputs())
        consistent_inputs[2]["basic_quality_passed"] = True
        consistent_inputs[2]["checks"]["page_timestamps_consistent"] = True

        inconsistent_inputs = list(self.make_inputs())
        inconsistent_inputs[2]["basic_quality_passed"] = True
        inconsistent_inputs[2]["checks"]["page_timestamps_consistent"] = False

        consistent_report = build_research_report(*consistent_inputs)
        inconsistent_report = build_research_report(*inconsistent_inputs)

        consistent_reason = consistent_report["confidence_basis"]["reasons"][0]
        inconsistent_reason = inconsistent_report["confidence_basis"]["reasons"][0]

        self.assertNotEqual(consistent_reason, inconsistent_reason)
        self.assertIn("通过", consistent_reason)
        self.assertIn("未通过", inconsistent_reason)



if __name__ == "__main__":
    unittest.main()
