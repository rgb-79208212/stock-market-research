
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from src.market_session import assess_market_session


SHANGHAI = ZoneInfo("Asia/Shanghai")


def to_timestamp_ms(date_time_text):
    dt = datetime.strptime(
        date_time_text,
        "%Y-%m-%d %H:%M:%S",
    ).replace(tzinfo=SHANGHAI)
    return int(dt.timestamp() * 1000)


class TestAssessMarketSession(unittest.TestCase):

    def test_weekend_is_not_regular_trading_session(self):
        result = assess_market_session(
            to_timestamp_ms("2026-10-24 07:55:07")
        )
        self.assertEqual(result["status"], "周末（非交易日）")
        self.assertTrue(result["is_weekend"])
        self.assertFalse(result["within_regular_session"])

    def test_weekday_morning_session(self):
        result = assess_market_session(
            to_timestamp_ms("2026-10-26 10:00:00")
        )
        self.assertTrue(result["within_regular_session"])
        self.assertIn("未核验节假日", result["status"])

    def test_weekday_afternoon_session(self):
        result = assess_market_session(
            to_timestamp_ms("2026-10-26 14:00:00")
        )
        self.assertTrue(result["within_regular_session"])

    def test_lunch_break_is_outside_regular_session(self):
        result = assess_market_session(
            to_timestamp_ms("2026-10-26 12:00:00")
        )
        self.assertFalse(result["within_regular_session"])
        self.assertIn("非连续交易时段", result["status"])

    def test_before_open_is_outside_regular_session(self):
        result = assess_market_session(
            to_timestamp_ms("2026-10-26 09:00:00")
        )
        self.assertFalse(result["within_regular_session"])

    def test_after_close_is_outside_regular_session(self):
        result = assess_market_session(
            to_timestamp_ms("2026-10-26 16:00:00")
        )
        self.assertFalse(result["within_regular_session"])

    def test_missing_timestamp_cannot_be_verified(self):
        result = assess_market_session(None)
        self.assertEqual(result["status"], "无法判断")
        self.assertIsNone(result["within_regular_session"])

    def test_invalid_timestamp_cannot_be_verified(self):
        result = assess_market_session("invalid")
        self.assertEqual(result["status"], "无法判断")


if __name__ == "__main__":
    unittest.main()
