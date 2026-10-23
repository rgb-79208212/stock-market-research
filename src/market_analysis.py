from __future__ import annotations

from typing import Any


def calculate_market_breadth(items: list[dict[str, Any]]) -> dict[str, Any]:
    """根据股票快照计算市场广度，不执行网络请求或文件读写。"""

    if not isinstance(items, list) or not items:
        raise ValueError("股票快照为空，无法计算市场广度。")

    seen_codes: set[str] = set()
    valid_changes: list[float] = []
    missing_change_count = 0

    for item in items:
        if not isinstance(item, dict):
            raise ValueError("股票快照包含格式无效的记录。")

        code = item.get("thscode")
        if not isinstance(code, str) or not code.strip():
            raise ValueError("股票快照存在缺少证券代码的记录。")

        if code in seen_codes:
            raise ValueError(f"发现重复证券代码：{code}")

        seen_codes.add(code)

        value = item.get("price_change_ratio_pct")

        # 缺失值允许排除，但不把布尔值、无穷大或 NaN 当成有效涨跌幅。
        if value is None:
            missing_change_count += 1
            continue

        if isinstance(value, bool):
            raise ValueError(f"证券 {code} 的涨跌幅格式无效。")

        try:
            change = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"证券 {code} 的涨跌幅格式无效。") from exc

        import math

        if not math.isfinite(change):
            raise ValueError(f"证券 {code} 的涨跌幅不是有限数值。")

        valid_changes.append(change)

    if not valid_changes:
        raise ValueError("没有有效涨跌幅，无法计算市场广度。")

    advancers = sum(value > 0 for value in valid_changes)
    decliners = sum(value < 0 for value in valid_changes)
    unchanged = sum(value == 0 for value in valid_changes)
    denominator = len(valid_changes)

    return {
        "source_record_count": len(items),
        "unique_code_count": len(seen_codes),
        "valid_change_count": denominator,
        "missing_change_count": missing_change_count,
        "advancers": advancers,
        "decliners": decliners,
        "unchanged": unchanged,
        "advance_ratio_pct": round(advancers / denominator * 100, 2),
        "decline_ratio_pct": round(decliners / denominator * 100, 2),
        "unchanged_ratio_pct": round(unchanged / denominator * 100, 2),
        "data_quality": {
            "no_duplicate_codes": True,
            "missing_change_records_excluded_from_breadth": True,
            "status": "preliminary",
        },
    }
