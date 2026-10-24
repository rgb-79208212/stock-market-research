
"""Deterministic assessment of research applicability."""

from typing import Any


def _quality_gate_passed(value: Any) -> bool:
    """Normalize existing quality-gate representations."""
    if value is True:
        return True

    if isinstance(value, str):
        return value.strip().lower() in {
            "passed",
            "pass",
            "通过",
        }

    return False


def assess_research_applicability(
    *,
    basic_quality_gate: Any,
    stock_session: dict | None,
    index_session: dict | None,
    market_calendar_verified: bool = False,
    market_session_verified: bool = False,
    market_freshness_verified: bool = False,
) -> dict:
    """
    Assess whether a snapshot is suitable for current-state interpretation.

    This function does not assess future returns or historical validity.
    """
    quality_passed = _quality_gate_passed(basic_quality_gate)

    reasons: list[str] = []

    if not quality_passed:
        reasons.append("基础数据质量门槛未通过。")

        return {
            "status": "不可用于正式状态研判",
            "snapshot_statistics_allowed": False,
            "current_snapshot_applicability_confirmed": False,
            "reasons": reasons,
            "limitations": [
                "不得将本次数据用于正式市场状态研判。",
                "本判断不涉及未来走势或历史回测有效性。",
            ],
        }

    # Passing the quality gate permits descriptive statistics only.
    reasons_for_time: list[str] = []

    sessions = (
        ("股票接口", stock_session),
        ("指数接口", index_session),
    )

    for source_name, session in sessions:
        if not isinstance(session, dict):
            reasons_for_time.append(
                f"{source_name}缺少有效的基础时段信息。"
            )
            continue

        if session.get("status") == "无法判断":
            reasons_for_time.append(
                f"{source_name}无法判断基础交易时段。"
            )
        elif session.get("within_regular_session") is not True:
            status = session.get("status", "未知")
            reasons_for_time.append(
                f"{source_name}不满足常规连续交易时段条件"
                f"（{status}）。"
            )

    if market_calendar_verified is not True:
        reasons_for_time.append("官方交易日历尚未验证。")

    if market_session_verified is not True:
        reasons_for_time.append("交易时段尚未得到验证。")

    if market_freshness_verified is not True:
        reasons_for_time.append("行情新鲜度尚未验证。")

    if reasons_for_time:
        return {
            "status": "时段适用性未确认",
            "snapshot_statistics_allowed": True,
            "current_snapshot_applicability_confirmed": False,
            "reasons": reasons_for_time,
            "limitations": [
                "允许展示通过基础质量门槛的快照描述性统计。",
                "不得将规则分类表述为已确认的当前市场状态。",
                "本判断不代表规则已通过历史回测验证。",
            ],
        }

    return {
        "status": "当前快照时点条件已验证",
        "snapshot_statistics_allowed": True,
        "current_snapshot_applicability_confirmed": True,
        "reasons": [],
        "limitations": [
            "时点条件验证不代表市场状态规则已通过历史回测。",
            "时点条件验证不代表可以预测未来走势。",
        ],
    }
