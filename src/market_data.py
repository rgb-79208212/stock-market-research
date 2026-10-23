
import os
import time
import math

import requests


BASE_URL = "https://fuyao.aicubes.cn/api"
STOCK_SNAPSHOT_URL = f"{BASE_URL}/a-share/prices/snapshot"
INDEX_SNAPSHOT_URL = f"{BASE_URL}/a-share-index/prices/snapshot"

INDEX_CODES = [
    "000001.SH",
    "399001.SZ",
    "000300.SH",
]

PAGE_SIZE = 500
MAX_PAGES = 30
REQUEST_TIMEOUT = 30


class MarketDataError(Exception):
    """行情数据获取或校验失败。"""



def _create_session():
    """创建 API 会话，支持本地环境变量和 Streamlit Cloud Secrets。"""
    api_key = os.getenv("HITHINK_FINANCE_API_KEY")

    if not api_key:
        try:
            import streamlit as st

            api_key = st.secrets.get("HITHINK_FINANCE_API_KEY")
        except (ImportError, FileNotFoundError, RuntimeError):
            api_key = None

    if not api_key or not str(api_key).strip():
        raise MarketDataError(
            "未配置 HITHINK_FINANCE_API_KEY。"
            "请在本地环境变量或云端 Secrets 中配置 API Key。"
        )

    session = requests.Session()
    session.headers.update({"X-api-key": str(api_key).strip()})
    return session



def _request_json(session, url, params):
    try:
        response = session.get(
            url,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as exc:
        raise MarketDataError(
            f"行情接口请求失败：{exc}"
        ) from exc
    except ValueError as exc:
        raise MarketDataError(
            "行情接口返回的内容不是有效 JSON。"
        ) from exc

    if not isinstance(result, dict):
        raise MarketDataError("行情接口返回格式不符合预期。")

    if result.get("code") != 0:
        code = result.get("code")
        message = result.get("message", "未知错误")
        raise MarketDataError(
            f"行情接口业务错误：code={code}，message={message}"
        )

    data = result.get("data")

    if not isinstance(data, dict):
        raise MarketDataError("行情接口缺少有效 data 数据。")

    return data



def fetch_stock_snapshot():
    """获取全市场股票快照，并检查分页完整性。"""
    session = _create_session()

    all_items = []
    seen_codes = set()
    duplicate_codes = set()
    total_reported = None
    api_timestamp_ms = None

    # 必须在分页循环之前初始化，只初始化一次。
    page_timestamps = []

    try:
        for page_number in range(1, MAX_PAGES + 1):
            offset = (page_number - 1) * PAGE_SIZE

            data = _request_json(
                session,
                STOCK_SNAPSHOT_URL,
                {"limit": PAGE_SIZE, "offset": offset},
            )

            items = data.get("item")

            if not isinstance(items, list):
                raise MarketDataError(
                    f"第 {page_number} 页缺少有效 item 列表。"
                )

            if page_number == 1:
                total_reported = data.get("total")

            # 每一页都记录一次，包括缺失时间戳的情况。
            timestamp = data.get("timestamp")
            page_timestamps.append(timestamp)

            if timestamp is not None:
                api_timestamp_ms = timestamp

            if not items:
                break

            for item in items:
                if not isinstance(item, dict):
                    raise MarketDataError(
                        "股票列表中出现格式无效的记录。"
                    )

                code = item.get("thscode")

                if not code:
                    raise MarketDataError(
                        "股票快照存在缺少证券代码的记录。"
                    )

                if code in seen_codes:
                    duplicate_codes.add(code)

                seen_codes.add(code)
                all_items.append(item)

            if len(items) < PAGE_SIZE:
                break

            time.sleep(0.2)
        else:
            raise MarketDataError(
                f"达到最大分页数 {MAX_PAGES}，"
                "无法确认是否已获取完整市场数据。"
            )

    finally:
        session.close()

    if not all_items:
        raise MarketDataError("股票接口没有返回任何记录。")

    if total_reported is None:
        raise MarketDataError("股票接口未返回全市场记录总数。")

    if len(all_items) != total_reported:
        raise MarketDataError(
            f"记录数量不一致：实际 {len(all_items)} 条，"
            f"接口报告 {total_reported} 条。"
        )

    if duplicate_codes:
        raise MarketDataError(
            f"发现重复证券代码，共 {len(duplicate_codes)} 个，"
            "拒绝将其作为完整市场结果展示。"
        )

    valid_change_count = 0

    for item in all_items:
        value = item.get("price_change_ratio_pct")

        if value is None:
            continue

        if isinstance(value, bool):
            raise MarketDataError(
                f"证券 {item['thscode']} 的涨跌幅格式无效。"
            )

        try:
            numeric_value = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise MarketDataError(
                f"证券 {item['thscode']} 的涨跌幅格式无效。"
            ) from exc

        if not math.isfinite(numeric_value):
            raise MarketDataError(
                f"证券 {item['thscode']} 的涨跌幅不是有限数值。"
            )

        valid_change_count += 1

    # 只有每一页都有时间戳，且所有时间戳完全相同，
    # 才将这项检查标记为通过。
    page_timestamps_consistent = (
        bool(page_timestamps)
        and all(timestamp is not None for timestamp in page_timestamps)
        and len(set(page_timestamps)) == 1
    )

    return {
        "items": all_items,
        "api_timestamp_ms": api_timestamp_ms,
        "api_reported_total": total_reported,
        "actual_record_count": len(all_items),
        "valid_change_count": valid_change_count,
        "missing_change_count": len(all_items) - valid_change_count,
        "source_api": STOCK_SNAPSHOT_URL,
        "page_timestamps": page_timestamps,
        "page_timestamps_consistent": page_timestamps_consistent,
    }



def fetch_index_snapshot():
    """获取主要指数快照，并校验预期指数是否齐全。"""
    session = _create_session()

    try:
        data = _request_json(
            session,
            INDEX_SNAPSHOT_URL,
            {"thscodes": ",".join(INDEX_CODES)},
        )
    finally:
        session.close()

    items = data.get("item")

    if not isinstance(items, list):
        raise MarketDataError("指数接口缺少有效 item 列表。")

    by_code = {}

    for item in items:
        if not isinstance(item, dict):
            raise MarketDataError("指数列表中出现格式无效的记录。")

        code = item.get("thscode")

        if code:
            if code in by_code:
                raise MarketDataError(
                    f"指数接口返回重复证券代码：{code}"
                )

            by_code[code] = item

    missing_codes = set(INDEX_CODES) - set(by_code)

    if missing_codes:
        raise MarketDataError(
            "以下预期指数未返回："
            + ", ".join(sorted(missing_codes))
        )

    for code in INDEX_CODES:
        value = by_code[code].get("price_change_ratio_pct")

        if isinstance(value, bool):
            raise MarketDataError(
                f"指数 {code} 的涨跌幅格式无效。"
            )

        try:
            numeric_value = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise MarketDataError(
                f"指数 {code} 的涨跌幅缺失或无效。"
            ) from exc

        if not math.isfinite(numeric_value):
            raise MarketDataError(
                f"指数 {code} 的涨跌幅不是有限数值。"
            )

    return {
        "items": [by_code[code] for code in INDEX_CODES],
        "api_timestamp_ms": data.get("timestamp"),
        "source_api": INDEX_SNAPSHOT_URL,
    }
