
import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app import format_unix_seconds


class TestUnixSecondsFormatting(unittest.TestCase):

    def test_formats_timestamp_as_beijing_time(self):
        """Unix 秒级时间戳应转换为北京时间。"""
        timestamp = datetime(
            2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc
        ).timestamp()

        result = format_unix_seconds(timestamp)

        expected = datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        ).astimezone(ZoneInfo("Asia/Shanghai"))

        self.assertEqual(
            result,
            expected.strftime("%Y-%m-%d %H:%M:%S %Z"),
        )

    def test_none_returns_missing_label(self):
        """时间戳缺失时应返回明确提示。"""
        self.assertEqual(format_unix_seconds(None), "未提供")

    def test_invalid_timestamp_returns_error_label(self):
        """无法转换的输入应返回无效时间提示。"""
        self.assertEqual(
            format_unix_seconds("not-a-timestamp"),
            "无效时间戳",
        )


if __name__ == "__main__":
    unittest.main()
