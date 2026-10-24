
"""基于市场广度和主要指数快照，生成可解释的市场状态分类。"""

from __future__ import annotations

import math
from typing import Any


INDEX_NAMES = {
    "000001.SH": "上证指数",
    "399001.SZ": "深证成指",
    "000300.SH": "沪深300",
}

# 项目第一版的研究阈值，不是经过历史回测验证的投资信号。
BREADTH_STRONG_THRESHOLD = 70.0
BREADTH_POSITIVE_THRESHOLD = 55.0
BREADTH_NEGATIVE_THRESHOLD = 45.0
BREADTH_WEAK_THRESHOLD = 30.0


def _finite_number(value: Any) -> float:
    """将输入转换为有限数值；拒绝布尔值和无效数值。"""
    if isinstance(value, bool) or value is None:
        raise ValueError("指标值缺失或无效。")

    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("指标值必须是有效数值。") from exc

    if not math.isfinite(number):
        raise ValueError("指标值必须是有限数值。")

    return number


def _index_direction(change_pct: float) -> str:
    if change_pct > 0:
        return "上涨"
    if change_pct < 0:
        return "下跌"
    return "平盘"


def assess_market_state(
    breadth: dict[str, Any],
    index_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """归纳当前快照状态，并返回证据、局限和规则切换条件。

    本函数仅进行描述性分类，不预测未来走势，不生成交易建议。
    调用方应先完成数据质量检查。
    """
    if not isinstance(breadth, dict):
        raise ValueError("breadth 必须是字典。")

    if not isinstance(index_items, list) or not index_items:
        raise ValueError("指数数据为空，无法进行完整的状态归纳。")

    valid_count = breadth.get("valid_change_count")
    if (
        isinstance(valid_count, bool)
        or not isinstance(valid_count, int)
        or valid_count <= 0
    ):
        raise ValueError("有效涨跌幅样本数必须是正整数。")

    advance_ratio = _finite_number(breadth.get("advance_ratio_pct"))
    decline_ratio = _finite_number(breadth.get("decline_ratio_pct"))

    if not 0 <= advance_ratio <= 100 or not 0 <= decline_ratio <= 100:
        raise ValueError("上涨占比和下跌占比必须在 0% 至 100% 之间。")

    # 两个比例来自同一组有效样本时，其合计不能超过 100%。
    # 允许两位小数分别四舍五入带来的微小误差。
    if advance_ratio + decline_ratio > 100.02:
        raise ValueError("上涨占比和下跌占比之和超过合理范围。")

    unchanged_value = breadth.get("unchanged_ratio_pct")
    if unchanged_value is not None:
        unchanged_ratio = _finite_number(unchanged_value)

        if not 0 <= unchanged_ratio <= 100:
            raise ValueError("平盘占比必须在 0% 至 100% 之间。")

        if abs(
                advance_ratio + decline_ratio + unchanged_ratio - 100
        ) > 0.03:
            raise ValueError("上涨、下跌和平盘占比之和不等于 100%。")
    index_by_code: dict[str, dict[str, Any]] = {}

    for item in index_items:
        if not isinstance(item, dict):
            raise ValueError("指数记录格式无效。")

        code = item.get("thscode")
        if code not in INDEX_NAMES:
            continue

        if code in index_by_code:
            raise ValueError(f"指数代码重复：{code}")

        change = _finite_number(item.get("price_change_ratio_pct"))
        index_by_code[code] = {
            "code": code,
            "name": INDEX_NAMES[code],
            "change_pct": change,
            "direction": _index_direction(change),
        }

    expected_codes = set(INDEX_NAMES)
    if set(index_by_code) != expected_codes:
        missing = sorted(expected_codes - set(index_by_code))
        raise ValueError(f"主要指数数据不完整，缺少：{', '.join(missing)}")

    index_results = list(index_by_code.values())
    positive_indices = sum(x["change_pct"] > 0 for x in index_results)
    negative_indices = sum(x["change_pct"] < 0 for x in index_results)
    unchanged_indices = sum(x["change_pct"] == 0 for x in index_results)

    evidence = [
        f"上涨占比为 {advance_ratio:.2f}%，下跌占比为 {decline_ratio:.2f}%。",
        (
            f"纳入市场广度计算的有效涨跌幅样本为 "
            f"{valid_count:,} 条。"
        ),
        (
            f"三个主要指数中，{positive_indices} 个上涨、"
            f"{negative_indices} 个下跌、{unchanged_indices} 个平盘。"
        ),
    ]

    limitations = [
        "本分类只描述当前获取的快照，不代表未来走势。",
        "第一版阈值是透明的项目规则，尚未经过历史回测验证。",
        "市场广度按记录数量统计，不代表市值加权表现。",
        "指数与股票快照的时间差和分页一致性仍受数据源限制。",
    ]

    if advance_ratio >= BREADTH_STRONG_THRESHOLD and positive_indices >= 2:
        state = "广泛偏强"
        rationale = "上涨占比达到强势阈值，且至少两个主要指数上涨。"
    elif advance_ratio >= BREADTH_POSITIVE_THRESHOLD and positive_indices >= 2:
        state = "偏强"
        rationale = "上涨占比偏高，且至少两个主要指数上涨。"
    elif advance_ratio <= BREADTH_WEAK_THRESHOLD and negative_indices >= 2:
        state = "广泛偏弱"
        rationale = "上涨占比处于弱势区间，且至少两个主要指数下跌。"
    elif advance_ratio <= BREADTH_NEGATIVE_THRESHOLD and negative_indices >= 2:
        state = "偏弱"
        rationale = "上涨占比偏低，且至少两个主要指数下跌。"
    elif advance_ratio >= BREADTH_POSITIVE_THRESHOLD:
        state = "个股广度偏强，指数确认不足"
        rationale = "个股上涨占比较高，但主要指数未形成一致的上涨确认。"
    elif advance_ratio <= BREADTH_NEGATIVE_THRESHOLD:
        state = "个股广度偏弱，指数确认不足"
        rationale = "个股上涨占比较低，但主要指数未形成一致的下跌确认。"
    else:
        state = "中性或涨跌分化"
        rationale = "上涨占比位于中间区间，未满足偏强或偏弱的分类条件。"

    evidence.append(f"分类依据：{rationale}")

    if state == "广泛偏强":
        state_switch_conditions = [
            f"上涨占比低于 {BREADTH_STRONG_THRESHOLD:.0f}%，"
            f"或上涨指数少于两个时，重新评估当前分类。"
        ]
    elif state == "偏强":
        state_switch_conditions = [
            f"上涨占比低于 {BREADTH_POSITIVE_THRESHOLD:.0f}%，"
            "或上涨指数少于两个时，重新评估当前分类。"
        ]
    elif state == "广泛偏弱":
        state_switch_conditions = [
            f"上涨占比高于 {BREADTH_WEAK_THRESHOLD:.0f}%，"
            "或下跌指数少于两个时，重新评估当前分类。"
        ]
    elif state == "偏弱":
        state_switch_conditions = [
            f"上涨占比高于 {BREADTH_NEGATIVE_THRESHOLD:.0f}%，"
            "或下跌指数少于两个时，重新评估当前分类。"
        ]
    elif state == "个股广度偏强，指数确认不足":
        state_switch_conditions = [
            f"至少两个主要指数上涨，或上涨占比低于 "
            f"{BREADTH_POSITIVE_THRESHOLD:.0f}% 时，重新评估当前分类。"
        ]
    elif state == "个股广度偏弱，指数确认不足":
        state_switch_conditions = [
            f"至少两个主要指数下跌，或上涨占比高于 "
            f"{BREADTH_NEGATIVE_THRESHOLD:.0f}% 时，重新评估当前分类。"
        ]
    else:
        state_switch_conditions = [
            f"上涨占比达到 {BREADTH_POSITIVE_THRESHOLD:.0f}% "
            "且至少两个主要指数上涨，或上涨占比降至 "
            f"{BREADTH_NEGATIVE_THRESHOLD:.0f}% 及以下且至少两个"
            "主要指数下跌时，重新评估分类。"
        ]

    return {
        "state": state,
        "rationale": rationale,
        "evidence": evidence,
        "metrics": {
            "advance_ratio_pct": advance_ratio,
            "decline_ratio_pct": decline_ratio,
            "valid_change_count": valid_count,
            "positive_indices": positive_indices,
            "negative_indices": negative_indices,
            "unchanged_indices": unchanged_indices,
        },
        "index_results": index_results,
        "state_switch_conditions": state_switch_conditions,
        "limitations": limitations,
        "method": {
            "breadth_strong_threshold_pct": BREADTH_STRONG_THRESHOLD,
            "breadth_positive_threshold_pct": BREADTH_POSITIVE_THRESHOLD,
            "breadth_negative_threshold_pct": BREADTH_NEGATIVE_THRESHOLD,
            "breadth_weak_threshold_pct": BREADTH_WEAK_THRESHOLD,
            "historically_validated": False,
        },
    }
