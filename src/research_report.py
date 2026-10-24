
"""将行情质量、市场广度和规则分类整理为可审计的研究报告。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from src.market_session import assess_market_session
from src.research_applicability import (
    assess_research_applicability,
)


def _timestamp_to_iso(timestamp_ms: Any) -> str | None:
    """将 Unix 毫秒时间戳转换为 UTC ISO 8601 字符串。"""
    if isinstance(timestamp_ms, bool):
        return None

    try:
        timestamp = float(timestamp_ms) / 1000
    except (TypeError, ValueError, OverflowError):
        return None

    try:
        return datetime.fromtimestamp(
            timestamp, tz=timezone.utc
        ).isoformat()
    except (ValueError, OverflowError, OSError):
        return None


def build_research_report(
    stock_result: dict[str, Any],
    index_result: dict[str, Any],
    quality_result: dict[str, Any],
    breadth: dict[str, Any],
    state_result: dict[str, Any],
    freshness_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """组合已有分析结果，不请求网络、不调用大模型、不生成交易建议。"""

    for name, value in (
        ("stock_result", stock_result),
        ("index_result", index_result),
        ("quality_result", quality_result),
        ("breadth", breadth),
        ("state_result", state_result),
    ):
        if not isinstance(value, dict):
            raise ValueError(f"{name} 必须是字典。")

    if freshness_result is not None and not isinstance(
        freshness_result, dict
    ):
        raise ValueError("freshness_result 必须是字典或 None")

    if quality_result.get("research_ready") is not True:
        raise ValueError("数据质量门槛未通过，不能生成正式研究报告。")

    if not isinstance(stock_result.get("items"), list):
        raise ValueError("股票快照缺少有效记录列表。")

    if not isinstance(index_result.get("items"), list):
        raise ValueError("指数快照缺少有效记录列表。")

    if not isinstance(quality_result.get("checks"), dict):
        raise ValueError("缺少数据质量检查结果。")

    if not isinstance(state_result.get("state"), str):
        raise ValueError("缺少市场状态分类。")

    if not isinstance(state_result.get("evidence"), list):
        raise ValueError("缺少市场状态证据。")

    stock_time = _timestamp_to_iso(
        stock_result.get("api_timestamp_ms")
    )
    index_time = _timestamp_to_iso(
        index_result.get("api_timestamp_ms")
    )

    stock_session = assess_market_session(
        stock_result.get("api_timestamp_ms")
    )
    index_session = assess_market_session(
        index_result.get("api_timestamp_ms")
    )


    session_warnings = []

    for source_name, session in (
            ("股票接口", stock_session),
            ("指数接口", index_session),
    ):
        if session["status"] == "无法判断":
            session_warnings.append(
                f"{source_name}缺少有效时间戳，无法判断基础交易时段。"
            )
        elif session["within_regular_session"] is False:
            session_warnings.append(
                f"{source_name}时间对应“{session['status']}”；"
                "不能仅凭接口成功认定为交易时段实时行情。"
            )
        else:
            session_warnings.append(
                f"{source_name}时间落在常规连续交易时段范围内，"
                "但官方交易日历和行情新鲜度尚未验证。"
            )

    metrics = breadth
    quality_metrics = quality_result.get("metrics", {})
    state_metrics = state_result.get("metrics", {})
    method = state_result.get("method", {})

    facts = [
        {
            "claim": (
                f"股票快照包含 {len(stock_result['items'])} 条记录。"
            ),
            "source": stock_result.get("source_api", "股票快照接口"),
            "evidence_type": "api_observation",
        },
        {
            "claim": (
                f"市场广度有效样本为 "
                f"{metrics.get('valid_change_count')} 条。"
            ),
            "source": "calculate_market_breadth",
            "evidence_type": "calculated_metric",
        },
        {
            "claim": (
                f"上涨占比为 {metrics.get('advance_ratio_pct')}%，"
                f"下跌占比为 {metrics.get('decline_ratio_pct')}%，"
                f"平盘占比为 {metrics.get('unchanged_ratio_pct')}%。"
            ),
            "source": "calculate_market_breadth",
            "evidence_type": "calculated_metric",
        },
        {
            "claim": f"规则分类结果为：{state_result['state']}。",
            "source": "assess_market_state",
            "evidence_type": "rule_output",
        },
    ]

    interpretations = [
        {
            "claim": state_result.get("rationale", ""),
            "basis": list(state_result["evidence"]),
            "type": "rule_based_interpretation",
        }
    ]

    hypotheses = [
        {
            "claim": (
                "当前快照是否代表完整交易时段，"
                "以及该状态能否持续，尚无法由现有数据确认。"
            ),
            "status": "unverified",
            "reason": (
                "缺少交易时段验证和经过历史检验的状态持续性证据。"
            ),
        },
        {
            "claim": (
                "当前市场广度是否受到特定行业、"
                "市值风格或个别股票群体的集中影响，尚未验证。"
            ),
            "status": "unverified",
            "reason": (
                "现有广度按股票记录数量统计，"
                "没有行业、市值分组或风格轮动数据。"
            ),
        },
    ]

    checks = quality_result["checks"]
    passed_checks = sum(value is True for value in checks.values())
    total_checks = len(checks)

    freshness_warnings = []

    if freshness_result is not None:
        stock_freshness = freshness_result.get("stock")
        index_freshness = freshness_result.get("index")

        market_freshness_verified = (
            freshness_result.get("verified") is True
            and isinstance(stock_freshness, dict)
            and stock_freshness.get("verified") is True
            and isinstance(index_freshness, dict)
            and index_freshness.get("verified") is True
        )

        for source_name, source_key in (
            ("股票快照", "stock"),
            ("指数快照", "index"),
        ):
            source_freshness = freshness_result.get(source_key)

            if (
                not isinstance(source_freshness, dict)
                or source_freshness.get("verified") is not True
            ):
                if isinstance(source_freshness, dict):
                    status = source_freshness.get(
                        "status", "unknown"
                    )
                    age = source_freshness.get("age_seconds")
                else:
                    status = "missing_freshness_result"
                    age = None

                age_text = (
                    f"{age:.1f} 秒"
                    if isinstance(age, (int, float))
                    and not isinstance(age, bool)
                    else "不可计算"
                )

                freshness_warnings.append(
                    f"{source_name}时间戳新鲜度检查未通过："
                    f"状态={status}，年龄={age_text}。"
                )

    else:
        # 兼容尚未传入独立新鲜度结果的旧调用。
        market_freshness_verified = (
            quality_result.get("market_freshness_verified")
            is True
        )


    evidence_quality = {
        "basic_quality_gate": "passed",
        "passed_check_count": passed_checks,
        "total_check_count": total_checks,
        "page_timestamps_valid": checks.get(
            "page_timestamps_valid"
        ),
        "page_timestamp_spread_within_threshold": checks.get(
            "page_timestamp_spread_within_threshold"
        ),
        "api_timestamps_comparable": checks.get(
            "api_timestamps_comparable"
        ),
        "api_gap_within_threshold": checks.get(
            "api_gap_within_threshold"
        ),
        "page_timestamps_consistent": checks.get(
            "page_timestamps_consistent"
        ),
        "page_timestamp_spread_seconds": quality_metrics.get(
            "page_timestamp_spread_seconds"
        ),
        "stock_index_api_gap_seconds": quality_metrics.get(
            "stock_index_api_gap_seconds"
        ),

        "market_session_verified": quality_result.get(
            "market_session_verified", False
        ),
        "market_calendar_verified": False,
        "market_freshness_verified": market_freshness_verified,
        "stock_timestamp_freshness": (
            freshness_result.get("stock")
            if freshness_result is not None
            else None
        ),
        "index_timestamp_freshness": (
            freshness_result.get("index")
            if freshness_result is not None
            else None
        ),
        "freshness_max_age_seconds": (
            freshness_result.get("max_age_seconds")
            if freshness_result is not None
            else None
        ),
        "stock_market_session": stock_session,
        "index_market_session": index_session,
        "independent_source_verified": False,
        "historically_validated": method.get(
            "historically_validated", False
        ),
        "limitations": list(state_result.get("limitations", [])),
        "warnings": (
            list(quality_result.get("warnings", []))
            + session_warnings
            + freshness_warnings
        ),
    }


    research_applicability = assess_research_applicability(
        basic_quality_gate=evidence_quality["basic_quality_gate"],
        stock_session=stock_session,
        index_session=index_session,
        market_calendar_verified=evidence_quality[
            "market_calendar_verified"
        ],
        market_session_verified=evidence_quality[
            "market_session_verified"
        ],
        market_freshness_verified=evidence_quality[
            "market_freshness_verified"
        ],
    )


    confidence_basis = {
        "label": "规则分类的证据充分度：初步",
        "numeric_probability": None,
        "reasons": [
            "基础数据质量门槛已通过。",
            "状态分类有明确、可检查的规则依据。",
            "当前阈值尚未经过历史回测验证。",
            "基础时段判断不等于官方交易日历验证；"
            "行情新鲜度和独立数据源也尚未验证。",
            "现有指标不足以证明状态持续性或未来方向。",
        ],
        "interpretation": (
            "该标签描述现有证据的局限，不是统计置信概率，"
            "也不是对未来涨跌的预测。"
        ),
    }

    return {
        "report_version": "1.0",
        "research_ready": quality_result["research_ready"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "evidence_time": {
            "stock_api_time_utc": stock_time,
            "index_api_time_utc": index_time,
            "timestamps_match": (
                stock_time is not None
                and index_time is not None
                and stock_time == index_time
            ),
        },
        "facts": facts,
        "interpretations": interpretations,
        "hypotheses": hypotheses,
        "evidence_quality": evidence_quality,
        "research_applicability": research_applicability,
        "confidence_basis": confidence_basis,
        "market_state": {
            "label": state_result["state"],
            "metrics": state_metrics,
            "index_results": state_result.get("index_results", []),
            "switch_conditions": state_result.get(
                "state_switch_conditions", []
            ),
        },
        "method": method,
        "disclaimer": (
            "本报告用于描述性市场研究，不构成投资建议，"
            "不预测未来涨跌，不提供仓位建议。"
        ),
    }
