
import unittest
from unittest.mock import patch

from src.market_data import (
    MarketDataError,
    _request_json,
    fetch_index_snapshot,
    fetch_stock_snapshot,
)


class TestMarketData(unittest.TestCase):

    def _stock_page(self, timestamp, codes, total):
        return {
            "timestamp": timestamp,
            "total": total,
            "item": [
                {
                    "thscode": code,
                    "price_change_ratio_pct": 1.0,
                }
                for code in codes
            ],
        }

    @patch("src.market_data.time.sleep")
    @patch("src.market_data._request_json")
    @patch("src.market_data._create_session")
    def test_stock_snapshot_uses_latest_valid_page_timestamp(
        self, mock_create_session, mock_request_json, mock_sleep
    ):
        """多页时间戳乱序时，应选择最大有效时间戳。"""
        mock_create_session.return_value.close.return_value = None
        mock_request_json.side_effect = [
            self._stock_page(
                2000,
                ["000001.SZ", "000002.SZ"],
                3,
            ),
            self._stock_page(
                1000,
                ["000003.SZ"],
                3,
            ),
        ]

        with patch("src.market_data.PAGE_SIZE", 2):
            result = fetch_stock_snapshot()

        self.assertEqual(result["api_timestamp_ms"], 2000)
        self.assertEqual(result["page_timestamps"], [2000, 1000])
        self.assertFalse(result["page_timestamps_consistent"])

    @patch("src.market_data.time.sleep")
    @patch("src.market_data._request_json")
    @patch("src.market_data._create_session")
    def test_stock_snapshot_keeps_valid_timestamp_when_last_page_missing(
        self, mock_create_session, mock_request_json, mock_sleep
    ):
        """最后一页缺少时间戳时，不应覆盖之前的有效时间戳。"""
        mock_create_session.return_value.close.return_value = None
        mock_request_json.side_effect = [
            self._stock_page(
                2000,
                ["000001.SZ", "000002.SZ"],
                3,
            ),
            self._stock_page(
                None,
                ["000003.SZ"],
                3,
            ),
        ]

        with patch("src.market_data.PAGE_SIZE", 2):
            result = fetch_stock_snapshot()

        self.assertEqual(result["api_timestamp_ms"], 2000)
        self.assertEqual(result["page_timestamps"], [2000, None])
        self.assertFalse(result["page_timestamps_consistent"])

    @patch("src.market_data.time.sleep")
    @patch("src.market_data._request_json")
    @patch("src.market_data._create_session")
    def test_stock_snapshot_returns_none_when_all_timestamps_invalid(
        self, mock_create_session, mock_request_json, mock_sleep
    ):
        """所有分页时间戳均无效时，不应生成有效时间戳。"""
        mock_create_session.return_value.close.return_value = None
        mock_request_json.side_effect = [
            self._stock_page(
                None,
                ["000001.SZ", "000002.SZ"],
                3,
            ),
            self._stock_page(
                float("nan"),
                ["000003.SZ"],
                3,
            ),
        ]

        with patch("src.market_data.PAGE_SIZE", 2):
            result = fetch_stock_snapshot()

        self.assertIsNone(result["api_timestamp_ms"])
        self.assertEqual(len(result["page_timestamps"]), 2)



    @patch("src.market_data._create_session")
    def test_stock_snapshot_rejects_duplicate_codes(self, mock_session):
        """重复证券代码应被拦截。"""
        mock_session.return_value.get.return_value.raise_for_status.return_value = None
        mock_session.return_value.get.return_value.json.return_value = {
            "code": 0,
            "data": {
                "timestamp": 1000,
                "total": 2,
                "item": [
                    {
                        "thscode": "000001.SZ",
                        "price_change_ratio_pct": 1.0,
                    },
                    {
                        "thscode": "000001.SZ",
                        "price_change_ratio_pct": 2.0,
                    },
                ],
            },
        }

        with self.assertRaisesRegex(MarketDataError, "重复证券代码"):
            fetch_stock_snapshot()

    @patch("src.market_data._create_session")
    def test_stock_snapshot_rejects_incomplete_market(self, mock_session):
        """实际记录数少于接口报告总数时应被拦截。"""
        mock_session.return_value.get.return_value.raise_for_status.return_value = None
        mock_session.return_value.get.return_value.json.return_value = {
            "code": 0,
            "data": {
                "timestamp": 1000,
                "total": 2,
                "item": [
                    {
                        "thscode": "000001.SZ",
                        "price_change_ratio_pct": 1.0,
                    }
                ],
            },
        }

        with self.assertRaisesRegex(MarketDataError, "记录数量不一致"):
            fetch_stock_snapshot()

    @patch("src.market_data._create_session")
    def test_index_snapshot_rejects_missing_index(self, mock_session):
        """缺少预期指数时应被拦截。"""
        mock_session.return_value.get.return_value.raise_for_status.return_value = None
        mock_session.return_value.get.return_value.json.return_value = {
            "code": 0,
            "data": {
                "timestamp": 1000,
                "item": [
                    {
                        "thscode": "000001.SH",
                        "price_change_ratio_pct": 1.0,
                    },
                    {
                        "thscode": "399001.SZ",
                        "price_change_ratio_pct": 2.0,
                    },
                ],
            },
        }

        with self.assertRaisesRegex(MarketDataError, "预期指数未返回"):
            fetch_index_snapshot()

    @patch("src.market_data._create_session")
    def test_index_snapshot_accepts_three_valid_indices(self, mock_session):
        """三个预期指数均返回有效涨跌幅时应成功。"""
        mock_session.return_value.get.return_value.raise_for_status.return_value = None
        mock_session.return_value.get.return_value.json.return_value = {
            "code": 0,
            "data": {
                "timestamp": 1000,
                "item": [
                    {
                        "thscode": "000001.SH",
                        "price_change_ratio_pct": 1.0,
                    },
                    {
                        "thscode": "399001.SZ",
                        "price_change_ratio_pct": 2.0,
                    },
                    {
                        "thscode": "000300.SH",
                        "price_change_ratio_pct": -0.5,
                    },
                ],
            },
        }

        result = fetch_index_snapshot()

        self.assertEqual(len(result["items"]), 3)
        self.assertEqual(
            [item["thscode"] for item in result["items"]],
            ["000001.SH", "399001.SZ", "000300.SH"],
        )


    @patch("src.market_data._create_session")
    def test_stock_snapshot_rejects_boolean_change(self, mock_session):
        """股票涨跌幅为布尔值时应被拦截。"""
        mock_session.return_value.get.return_value.raise_for_status.return_value = None
        mock_session.return_value.get.return_value.json.return_value = {
            "code": 0,
            "data": {
                "timestamp": 1000,
                "total": 1,
                "item": [
                    {
                        "thscode": "000001.SZ",
                        "price_change_ratio_pct": True,
                    }
                ],
            },
        }

        with self.assertRaisesRegex(MarketDataError, "涨跌幅格式无效"):
            fetch_stock_snapshot()

    @patch("src.market_data._create_session")
    def test_stock_snapshot_rejects_infinite_change(self, mock_session):
        """股票涨跌幅为无穷大时应被拦截。"""
        mock_session.return_value.get.return_value.raise_for_status.return_value = None
        mock_session.return_value.get.return_value.json.return_value = {
            "code": 0,
            "data": {
                "timestamp": 1000,
                "total": 1,
                "item": [
                    {
                        "thscode": "000001.SZ",
                        "price_change_ratio_pct": float("inf"),
                    }
                ],
            },
        }

        with self.assertRaisesRegex(MarketDataError, "不是有限数值"):
            fetch_stock_snapshot()

    @patch("src.market_data._create_session")
    def test_index_snapshot_rejects_duplicate_codes(self, mock_session):
        """指数接口返回重复证券代码时应被拦截。"""
        mock_session.return_value.get.return_value.raise_for_status.return_value = None
        mock_session.return_value.get.return_value.json.return_value = {
            "code": 0,
            "data": {
                "timestamp": 1000,
                "item": [
                    {"thscode": "000001.SH", "price_change_ratio_pct": 1.0},
                    {"thscode": "000001.SH", "price_change_ratio_pct": 1.1},
                    {"thscode": "399001.SZ", "price_change_ratio_pct": 2.0},
                    {"thscode": "000300.SH", "price_change_ratio_pct": -0.5},
                ],
            },
        }

        with self.assertRaisesRegex(MarketDataError, "重复证券代码"):
            fetch_index_snapshot()



if __name__ == "__main__":
    unittest.main()
