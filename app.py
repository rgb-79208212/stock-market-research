from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import hashlib
import json

import pandas as pd
import streamlit as st

from src.market_data import (
    MarketDataError,
    fetch_index_snapshot,
    fetch_stock_snapshot,
)
from src.market_analysis import calculate_market_breadth
from src.data_quality import assess_snapshot_quality
from src.market_state import assess_market_state
from src.research_report import build_research_report
from src.llm_analysis import generate_llm_interpretation, LLMAnalysisError
from src.market_session import assess_market_session
from src.research_applicability import assess_research_applicability
from src.market_freshness import assess_snapshot_freshness


# ============================================================
# 页面配置
# ============================================================

st.set_page_config(
    page_title="A股市场状态研究",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 视觉规范：极简股票交易风格
# ============================================================

st.markdown(
    """
    <style>
/* 顶栏透明化，避免遮挡自定义标题 */
header[data-testid="stHeader"] {
    background: transparent;
    backdrop-filter: none;
}

/* 为固定顶栏预留空间 */
.block-container {
    padding-top: 3.5rem;
    padding-bottom: 3rem;
    max-width: 1400px;
}

.app-header { margin: 0 0 0.8rem 0; }
.app-header h1 {
    font-size: 1.65rem;
    font-weight: 600;
    letter-spacing: 0.3px;
    margin: 0;
    line-height: 1.3;
}

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* 顶部标题 */
    .app-header { margin: 0 0 0.8rem 0; }
    .app-header h1 {
        font-size: 1.65rem;
        font-weight: 600;
        letter-spacing: 0.3px;
        margin: 0;
    }
    .app-header .subtitle {
        color: #6b7280;
        font-size: 0.84rem;
        margin-top: 0.3rem;
    }

    /* 自定义指标卡片 */
    .m-card {
        background: rgba(128, 128, 128, 0.06);
        border: 1px solid rgba(128, 128, 128, 0.18);
        border-radius: 10px;
        padding: 0.95rem 1.1rem;
        height: 100%;
    }
    .m-card .label {
        color: #6b7280;
        font-size: 0.75rem;
        letter-spacing: 0.4px;
        margin-bottom: 0.3rem;
    }
    .m-card .value {
        font-size: 1.5rem;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
        line-height: 1.15;
    }
    .m-card .delta {
        margin-top: 0.25rem;
        font-size: 0.85rem;
        font-weight: 500;
    }
    .m-card .meta {
        color: #6b7280;
        font-size: 0.72rem;
        margin-top: 0.3rem;
    }
    .up   { color: #e63a3a; }
    .down { color: #1faa5e; }
    .flat { color: #6b7280; }

    /* 状态徽章 */
    .status-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin: 0.4rem 0 1rem;
    }
    .badge {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.26rem 0.7rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 500;
    }
    .badge-ok   { background: rgba(31,170,94,0.12); color: #1faa5e; }
    .badge-warn { background: rgba(234,179,8,0.16); color: #b45309; }
    .badge-err  { background: rgba(230,58,58,0.12); color: #e63a3a; }
    .badge-mut  { background: rgba(128,128,128,0.12); color: #6b7280; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 6px; }
    .stTabs [data-baseweb="tab"] {
        padding: 0.45rem 1rem;
        font-size: 0.92rem;
    }

    hr { margin: 1rem 0; opacity: 0.6; }

    section[data-testid="stSidebar"] {
        border-right: 1px solid rgba(128,128,128,0.15);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

TIME_GAP_WARNING_SECONDS = 60

INDEX_NAMES = {
    "000001.SH": "上证指数",
    "399001.SZ": "深证成指",
    "000300.SH": "沪深300",
}


# ============================================================
# 辅助函数
# ============================================================

def format_api_time(timestamp_ms):
    if timestamp_ms is None:
        return "未提供"
    try:
        timestamp = float(timestamp_ms)
        if not pd.notna(timestamp):
            return "无效时间戳"
        dt = datetime.fromtimestamp(
            timestamp / 1000, tz=timezone.utc
        ).astimezone(ZoneInfo("Asia/Shanghai"))
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    except (ValueError, TypeError, OverflowError, OSError):
        return "无效时间戳"


def format_unix_seconds(timestamp_seconds):
    if timestamp_seconds is None:
        return "未提供"
    try:
        timestamp = float(timestamp_seconds)
        if not pd.notna(timestamp):
            return "无效时间戳"
        dt = datetime.fromtimestamp(
            timestamp, tz=timezone.utc
        ).astimezone(ZoneInfo("Asia/Shanghai"))
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    except (ValueError, TypeError, OverflowError, OSError):
        return "无效时间戳"


def format_percent(value):
    try:
        number = float(value)
        if pd.notna(number):
            return f"{number:+.2f}%"
    except (TypeError, ValueError, OverflowError):
        pass
    return "暂无数据"


def format_price(value):
    try:
        number = float(value)
        if pd.notna(number):
            return f"{number:,.2f}"
    except (TypeError, ValueError, OverflowError):
        pass
    return "暂无数据"


def timestamp_gap_seconds(timestamp_a, timestamp_b):
    if timestamp_a is None or timestamp_b is None:
        return None
    try:
        a = float(timestamp_a) / 1000
        b = float(timestamp_b) / 1000
        if not pd.notna(a) or not pd.notna(b):
            return None
        return abs(a - b)
    except (TypeError, ValueError, OverflowError):
        return None


def badge_html(label, status, kind="mut"):
    return f'<span class="badge badge-{kind}">● {label}：{status}</span>'


def index_card_html(name, code, price_text, delta_text, delta_class):
    return (
        f'<div class="m-card">'
        f'<div class="label">{name}</div>'
        f'<div class="value">{price_text}</div>'
        f'<div class="delta {delta_class}">{delta_text}</div>'
        f'<div class="meta">{code}</div>'
        f"</div>"
    )


# ============================================================
# 侧边栏：数据控制
# ============================================================

with st.sidebar:
    st.markdown("### 数据控制")
    st.caption("获取全市场股票与主要指数快照。")

    if st.button(
        "🔄 获取最新快照",
        type="primary",
        use_container_width=True,
        key="fetch_snapshot_btn",
    ):
        for key in (
            "market_result",
            "index_result",
            "market_error",
            "index_error",
        ):
            st.session_state.pop(key, None)

        with st.spinner("正在获取行情快照……"):
            try:
                st.session_state["market_result"] = fetch_stock_snapshot()
            except MarketDataError as exc:
                st.session_state["market_error"] = str(exc)
            except Exception as exc:
                st.session_state["market_error"] = (
                    f"股票数据获取失败，错误类型：{type(exc).__name__}。"
                    "请检查网络、API 服务和应用日志。"
                )

            try:
                st.session_state["index_result"] = fetch_index_snapshot()
            except MarketDataError as exc:
                st.session_state["index_error"] = str(exc)
            except Exception as exc:
                st.session_state["index_error"] = (
                    f"指数数据获取失败，错误类型：{type(exc).__name__}。"
                    "请检查网络、API 服务和应用日志。"
                )

        st.rerun()

    if "market_error" in st.session_state:
        st.error(f"股票快照失败：{st.session_state['market_error']}")
    if "index_error" in st.session_state:
        st.error(f"指数快照失败：{st.session_state['index_error']}")

    st.markdown("---")
    st.caption(
        "API Key 通过环境变量配置，无需在页面填写。"
        "全市场接口需分页请求，耗时约 10–30 秒。"
    )


# ============================================================
# 顶部页头
# ============================================================

st.markdown(
    """
    <div class="app-header">
        <h1>A股市场状态研究</h1>
        <div class="subtitle">
            行情快照 · 市场广度 · 指数表现 ·
            描述性研究，不构成投资建议
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 数据获取结果与全部计算（无 UI）
# ============================================================

stock_result = st.session_state.get("market_result")
index_result = st.session_state.get("index_result")

stock_api_ts = (
    stock_result.get("api_timestamp_ms")
    if isinstance(stock_result, dict) else None
)
index_api_ts = (
    index_result.get("api_timestamp_ms")
    if isinstance(index_result, dict) else None
)

stock_session = (
    assess_market_session(stock_api_ts)
    if stock_result is not None else None
)
index_session = (
    assess_market_session(index_api_ts)
    if index_result is not None else None
)

# ---- 数据质量 ----
quality_index_result = index_result
if (
    stock_result is not None
    and index_result is None
    and "index_error" in st.session_state
):
    quality_index_result = {}

quality_result = None
quality_error = None
if stock_result is not None:
    try:
        quality_result = assess_snapshot_quality(
            stock_result,
            index_result=quality_index_result,
            max_missing_ratio_pct=1.0,
            max_page_timestamp_spread_seconds=60.0,
            max_api_gap_seconds=60.0,
        )
    except (ValueError, TypeError, KeyError) as exc:
        quality_error = f"数据质量评估无法完成：{exc}"

# ---- 新鲜度 ----
freshness_result = None
freshness_error = None
if stock_result is not None or index_result is not None:
    now_ms = datetime.now(timezone.utc).timestamp() * 1000
    try:
        freshness_result = assess_snapshot_freshness(
            stock_result,
            index_result,
            now_ms=now_ms,
            max_age_seconds=120.0,
        )
    except (ValueError, TypeError, KeyError) as exc:
        freshness_error = f"行情新鲜度评估无法完成：{exc}"

freshness_gate_passed = (
    isinstance(freshness_result, dict)
    and freshness_result.get("verified") is True
    and isinstance(freshness_result.get("stock"), dict)
    and freshness_result["stock"].get("verified") is True
    and isinstance(freshness_result.get("index"), dict)
    and freshness_result["index"].get("verified") is True
)

# ---- 市场广度 ----
breadth = None
breadth_error = None
if (
    stock_result is not None
    and quality_result is not None
    and not quality_error
    and quality_result.get("descriptive_statistics_ready") is True
):
    try:
        breadth = calculate_market_breadth(stock_result["items"])
    except (ValueError, KeyError, TypeError) as exc:
        breadth_error = str(exc)

breadth_for_state = None
if (
    breadth is not None
    and quality_result is not None
    and quality_result.get("basic_quality_passed") is True
    and freshness_gate_passed
    and index_result is not None
):
    breadth_for_state = breadth

# ---- 市场状态 ----
state_result = None
state_error = None
if breadth_for_state is not None and index_result is not None:
    try:
        state_result = assess_market_state(
            breadth_for_state,
            index_result["items"],
        )
    except (ValueError, KeyError, TypeError) as exc:
        state_error = str(exc)

# ---- 研究报告就绪与构建 ----
report_inputs_ready = (
    stock_result is not None
    and index_result is not None
    and quality_error is None
    and quality_result is not None
    and quality_result.get("descriptive_statistics_ready") is True
    and quality_result.get("basic_quality_passed") is True
    and breadth_for_state is not None
    and isinstance(state_result, dict)
    and freshness_gate_passed
)

research_report = None
report_error = None
if report_inputs_ready:
    try:
        research_report = build_research_report(
            stock_result=stock_result,
            index_result=index_result,
            quality_result=quality_result,
            breadth=breadth_for_state,
            state_result=state_result,
            freshness_result=freshness_result,
        )
    except (ValueError, KeyError, TypeError) as exc:
        report_error = f"结构化研究报告生成失败：{exc}"

# ---- 状态适用性预检 ----
state_applicability = None
if (
    isinstance(stock_result, dict)
    and isinstance(index_result, dict)
    and quality_result is not None
    and not quality_error
    and breadth_for_state is not None
):
    try:
        state_applicability = assess_research_applicability(
            basic_quality_gate=(
                "passed"
                if quality_result.get("basic_quality_passed") is True
                else "failed"
            ),
            stock_session=stock_session,
            index_session=index_session,
            market_calendar_verified=(
                quality_result.get("market_calendar_verified", False) is True
            ),
            market_session_verified=(
                quality_result.get("market_session_verified", False) is True
            ),
            market_freshness_verified=freshness_gate_passed,
        )
    except (ValueError, TypeError, KeyError):
        pass


# ============================================================
# 状态徽章行
# ============================================================

badges = []

if stock_result is None and index_result is None:
    badges.append(badge_html("快照", "尚未获取", "mut"))
else:
    if quality_error:
        badges.append(badge_html("数据质量", "不可用", "err"))
    elif quality_result and quality_result.get("basic_quality_passed"):
        badges.append(badge_html("数据质量", "通过", "ok"))
    elif quality_result:
        badges.append(badge_html("数据质量", "未通过", "err"))

    if freshness_error:
        badges.append(badge_html("新鲜度", "不可用", "warn"))
    elif freshness_result and freshness_gate_passed:
        badges.append(badge_html("新鲜度", "通过", "ok"))
    elif freshness_result:
        badges.append(badge_html("新鲜度", "未通过", "warn"))

    if stock_session is not None:
        if stock_session["within_regular_session"]:
            badges.append(badge_html("时段", "常规交易时段", "ok"))
        elif stock_session["status"] == "周末（非交易日）":
            badges.append(badge_html("时段", "周末非交易日", "warn"))
        else:
            badges.append(badge_html("时段", "非连续交易时段", "warn"))

    if stock_result is not None:
        badges.append(
            badge_html("快照时间", format_api_time(stock_api_ts), "mut")
        )

if badges:
    st.markdown(
        '<div class="status-row">' + "".join(badges) + "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# 双 Tab 布局
# ============================================================

tab_overview, tab_diagnostics = st.tabs(
    ["📈 市场概览", "🔧 数据诊断"]
)


# ============================================================
# Tab 1：市场概览
# ============================================================

with tab_overview:
    if stock_result is None and index_result is None:
        st.info(
            "尚未获取行情快照。"
            "请点击左侧「获取最新快照」开始，"
            "全市场接口约需 10–30 秒。"
        )
    else:
        # ---------- 主要指数 ----------
        if index_result is not None:
            st.markdown("#### 主要指数")
            index_items = index_result.get("items", [])
            columns = st.columns(max(1, len(index_items)))

            for column, item in zip(columns, index_items):
                code = item.get("thscode", "未知代码")
                name = INDEX_NAMES.get(code, code)
                price_text = format_price(item.get("last_price"))
                change = item.get("price_change_ratio_pct")
                delta_text = format_percent(change)

                try:
                    change_num = float(change)
                    if pd.notna(change_num):
                        if change_num > 0:
                            delta_class = "up"
                        elif change_num < 0:
                            delta_class = "down"
                        else:
                            delta_class = "flat"
                    else:
                        delta_class = "flat"
                except (TypeError, ValueError, OverflowError):
                    delta_class = "flat"

                with column:
                    st.markdown(
                        index_card_html(
                            name, code, price_text,
                            delta_text, delta_class,
                        ),
                        unsafe_allow_html=True,
                    )

            st.caption(
                f"数据时间：{format_api_time(index_api_ts)}"
                f" · 来源：{index_result.get('source_api', '未提供')}"
            )
        else:
            st.warning("指数快照未获取，无法展示主要指数表现。")

        # ---------- 市场广度 ----------
        if stock_result is not None:
            st.markdown("#### 市场广度")

            if breadth is None:
                st.error(
                    "市场广度计算未完成，请查看「数据诊断」标签页。"
                )
            else:
                if quality_result and not quality_result.get(
                    "research_ready", False
                ):
                    st.warning(
                        "正式研究数据门槛未全部通过，"
                        "以下为本次快照的**描述性统计**。"
                    )

                m1, m2, m3 = st.columns(3)
                m1.metric("上涨标的", f"{breadth['advancers']:,}")
                m2.metric("下跌标的", f"{breadth['decliners']:,}")
                m3.metric("平盘标的", f"{breadth['unchanged']:,}")

                r1, r2, r3, r4 = st.columns(4)
                r1.metric(
                    "上涨占比", f"{breadth['advance_ratio_pct']:.2f}%"
                )
                r2.metric(
                    "下跌占比", f"{breadth['decline_ratio_pct']:.2f}%"
                )
                r3.metric(
                    "平盘占比", f"{breadth['unchanged_ratio_pct']:.2f}%"
                )
                r4.metric(
                    "有效记录", f"{breadth['valid_change_count']:,}"
                )

                chart_data = pd.DataFrame(
                    {
                        "类别": ["上涨", "下跌", "平盘"],
                        "数量": [
                            breadth["advancers"],
                            breadth["decliners"],
                            breadth["unchanged"],
                        ],
                    }
                ).set_index("类别")
                st.bar_chart(chart_data)

                st.caption(
                    "口径：涨跌幅 > 0 为上涨，< 0 为下跌，= 0 为平盘；"
                    "缺失涨跌幅不计入有效分母。"
                )

        # ---------- 市场状态研判 ----------
        st.markdown("#### 市场状态研判")

        if stock_result is None:
            st.info("请先获取行情快照。")
        elif state_error:
            st.error(f"市场状态研判未完成：{state_error}")
        elif state_result is None:
            if quality_error or quality_result is None:
                st.info("数据质量评估不可用，无法生成市场状态分类。")
            elif not quality_result.get(
                "descriptive_statistics_ready", False
            ):
                st.info("基础数据质量门槛未通过，暂不生成市场状态分类。")
            elif not quality_result.get("basic_quality_passed", False):
                st.info("基础数据质量检查未全部通过，暂不生成市场状态分类。")
            elif not freshness_gate_passed:
                st.info("行情新鲜度检查未通过，暂不生成市场状态分类。")
            elif index_result is None:
                st.info("缺少主要指数快照，无法生成市场状态分类。")
            elif breadth_for_state is None:
                st.info("市场广度计算不可用，无法生成市场状态分类。")
            else:
                st.info("市场状态分类不可用。")
        else:
            st.subheader(state_result["state"])
            st.write(state_result["rationale"])

            if state_applicability is not None:
                if state_applicability.get(
                    "current_snapshot_applicability_confirmed"
                ):
                    st.success(
                        "当前快照时点条件已验证（规则尚未经过历史回测）。"
                    )
                else:
                    st.warning(
                        "当前市场状态尚未确认，以下仅为暂定分类，"
                        "不应视为已验证的实时市场状态。"
                    )

            st.markdown("**主要证据**")
            for evidence_item in state_result["evidence"]:
                st.markdown(f"- {evidence_item}")

            st.markdown("**主要指数方向**")
            index_rows = [
                {
                    "指数": item["name"],
                    "代码": item["code"],
                    "涨跌幅": format_percent(item["change_pct"]),
                    "方向": item["direction"],
                }
                for item in state_result["index_results"]
            ]
            st.dataframe(
                pd.DataFrame(index_rows),
                use_container_width=True,
                hide_index=True,
            )

            metrics = state_result["metrics"]
            c1, c2, c3 = st.columns(3)
            c1.metric(
                "上涨占比", f"{metrics['advance_ratio_pct']:.2f}%"
            )
            c2.metric(
                "上涨指数", f"{metrics['positive_indices']} / 3"
            )
            c3.metric(
                "下跌指数", f"{metrics['negative_indices']} / 3"
            )

            st.markdown("**状态切换条件**")
            st.caption(
                "以下是规则重新评估的条件，"
                "不代表达到条件后市场必然上涨或下跌。"
            )
            for condition in state_result["state_switch_conditions"]:
                st.markdown(f"- {condition}")

            with st.expander("查看分类方法与研究限制"):
                method = state_result["method"]
                st.write(
                    f"- 广泛偏强参考阈值："
                    f"{method['breadth_strong_threshold_pct']:.0f}%"
                )
                st.write(
                    f"- 偏强参考阈值："
                    f"{method['breadth_positive_threshold_pct']:.0f}%"
                )
                st.write(
                    f"- 偏弱参考阈值："
                    f"{method['breadth_negative_threshold_pct']:.0f}%"
                )
                st.write(
                    f"- 广泛偏弱参考阈值："
                    f"{method['breadth_weak_threshold_pct']:.0f}%"
                )
                st.warning("阈值尚未通过历史回测验证。")
                st.markdown("**研究限制**")
                for limitation in state_result["limitations"]:
                    st.markdown(f"- {limitation}")

        # ---------- 结构化研究报告 ----------
        st.markdown("#### 结构化研究报告")

        if report_error:
            st.error(report_error)
        elif research_report is None:
            st.info(
                "当前无法生成正式结构化报告。"
                "请先完成行情获取并确认数据质量。"
            )
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric(
                "快照规则分类",
                research_report["market_state"]["label"],
            )
            c2.metric(
                "质量检查通过项",
                f"{research_report['evidence_quality']['passed_check_count']}"
                f" / "
                f"{research_report['evidence_quality']['total_check_count']}",
            )
            c3.metric(
                "历史回测验证",
                "已验证"
                if research_report["evidence_quality"][
                    "historically_validated"
                ]
                else "尚未验证",
            )

            st.markdown("**1. 可核查事实**")
            for item in research_report["facts"]:
                st.markdown(f"- {item['claim']}")
                st.caption(
                    f"证据类型：{item['evidence_type']}"
                    f"｜来源：{item['source']}"
                )

            st.markdown("**2. 规则解释**")
            for item in research_report["interpretations"]:
                st.write(item["claim"])
                if item["basis"]:
                    st.caption("依据")
                    for evidence in item["basis"]:
                        st.markdown(f"- {evidence}")


            st.markdown("**3. 尚未验证的假设与问题**")
            for item in research_report["hypotheses"]:
                st.markdown(f"- **{item['claim']}**")
                st.caption(f"原因：{item['reason']}")

            with st.expander("4. 证据质量与时间信息"):
                eq = research_report["evidence_quality"]
                et = research_report["evidence_time"]
                stock_ev_session = eq.get(
                    "stock_market_session", {}
                )
                index_ev_session = eq.get(
                    "index_market_session", {}
                )
                st.write(
                    {
                        "股票接口时间（UTC）": et[
                            "stock_api_time_utc"
                        ],
                        "指数接口时间（UTC）": et[
                            "index_api_time_utc"
                        ],
                        "两个接口时间戳完全相同": et[
                            "timestamps_match"
                        ],
                        "基础质量门槛": eq["basic_quality_gate"],
                        "分页时间跨度（秒）": eq[
                            "page_timestamp_spread_seconds"
                        ],
                        "股票与指数接口时间差（秒）": eq[
                            "stock_index_api_gap_seconds"
                        ],
                        "股票接口基础时段判断": stock_ev_session.get(
                            "status", "无法判断"
                        ),
                        "指数接口基础时段判断": index_ev_session.get(
                            "status", "无法判断"
                        ),
                        "官方交易日历已验证": eq.get(
                            "market_calendar_verified", False
                        ),
                        "交易时段已验证": eq[
                            "market_session_verified"
                        ],
                        "行情新鲜度已验证": eq.get(
                            "market_freshness_verified", False
                        ),
                        "独立数据源已交叉验证": eq[
                            "independent_source_verified"
                        ],
                    }
                )
                if eq["warnings"]:
                    st.markdown("**数据质量警告**")
                    for warning in eq["warnings"]:
                        st.warning(warning)

            st.markdown("**5. 研究适用性判断**")
            applicability = research_report.get(
                "research_applicability", {}
            )
            if not applicability:
                st.warning("当前报告没有研究适用性判断结果。")
            else:
                app_status = applicability.get("status", "未知")
                if app_status == "当前快照时点条件已验证":
                    st.success(app_status)
                elif app_status == "时段适用性未确认":
                    st.warning(app_status)
                else:
                    st.error(app_status)

                st.caption(
                    "该判断用于说明本次快照是否具备研究适用条件，"
                    "不代表规则经过历史回测，也不预测未来市场走势。"
                )
                st.write(
                    {
                        "允许展示快照描述性统计": applicability.get(
                            "snapshot_statistics_allowed", False
                        ),
                        "当前快照适用性已确认": applicability.get(
                            "current_snapshot_applicability_confirmed",
                            False,
                        ),
                    }
                )
                if applicability.get("reasons"):
                    st.markdown("**尚未满足或尚未验证的条件**")
                    for reason in applicability["reasons"]:
                        st.markdown(f"- {reason}")
                if applicability.get("limitations"):
                    st.markdown("**使用限制**")
                    for limitation in applicability["limitations"]:
                        st.markdown(f"- {limitation}")

            st.markdown("**6. 证据充分度说明**")
            confidence_basis = research_report["confidence_basis"]
            st.write(confidence_basis["label"])
            st.write(confidence_basis["interpretation"])
            for reason in confidence_basis["reasons"]:
                st.markdown(f"- {reason}")

            st.markdown("**7. 状态重新评估条件**")
            for condition in research_report["market_state"][
                "switch_conditions"
            ]:
                st.markdown(f"- {condition}")

            st.caption(research_report["disclaimer"])


            # ---------- DeepSeek AI 解读 ----------
            st.markdown("#### DeepSeek AI 解读")
            st.caption(
                "AI 仅依据本次结构化研究报告进行解释，"
                "不重新判断市场状态，不预测未来涨跌，"
                "也不提供交易建议。"
            )

            applicability_for_llm = research_report.get(
                "research_applicability", {}
            )
            if (
                isinstance(applicability_for_llm, dict)
                and applicability_for_llm.get(
                    "current_snapshot_applicability_confirmed"
                ) is True
            ):
                st.info(
                    "当前快照研究适用性已确认。"
                    "这不代表规则经过历史回测。"
                )
            else:
                st.warning(
                    "暂定、非正式 AI 解读："
                    "当前快照研究适用性未确认。"
                    "AI 只能解释本次快照的规则分类和已有证据。"
                )

            llm_input = {
                "market_state": research_report["market_state"],
                "facts": research_report["facts"],
                "interpretations": research_report["interpretations"],
                "hypotheses": research_report["hypotheses"],
                "evidence_time": research_report["evidence_time"],
                "evidence_quality": research_report["evidence_quality"],
                "research_applicability": research_report.get(
                    "research_applicability", {}
                ),
            }
            llm_cache_key = hashlib.sha256(
                json.dumps(
                    llm_input,
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                ).encode("utf-8")
            ).hexdigest()

            cache_key_name = "deepseek_report_cache_key"
            cache_result_name = "deepseek_report_result"

            if st.button(
                "生成 / 更新 AI 解读",
                key="generate_deepseek_interpretation",
            ):
                st.session_state.pop(cache_result_name, None)
                st.session_state.pop(cache_key_name, None)
                try:
                    with st.spinner(
                        "DeepSeek 正在分析结构化研究报告……"
                    ):
                        llm_result = generate_llm_interpretation(
                            research_report
                        )
                    st.session_state[cache_result_name] = llm_result
                    st.session_state[cache_key_name] = llm_cache_key
                except LLMAnalysisError as exc:
                    st.error(f"AI 解读生成失败：{exc}")

            if (
                st.session_state.get(cache_key_name) == llm_cache_key
                and st.session_state.get(cache_result_name)
            ):
                llm_result = st.session_state[cache_result_name]
                st.caption(
                    f"模型：{llm_result.get('model', '未知')} "
                    f"| 生成时间："
                    f"{format_unix_seconds(llm_result.get('generated_at'))}"
                )
                st.markdown(llm_result["content"])


# ============================================================
# Tab 2：数据诊断（默认全部折叠）
# ============================================================

with tab_diagnostics:
    st.caption(
        "以下为数据质量、时间戳与接口检查的技术细节，"
        "默认折叠，仅在需要时展开。"
    )

    if stock_result is None and index_result is None:
        st.info("尚无可诊断的行情快照。")
    else:
        # 1. 交易时段
        with st.expander("1. 行情时间与交易时段检查", expanded=False):
            st.caption(
                "根据接口时间戳判断基础时段；"
                "不等于交易所交易日历验证，"
                "也不能证明行情是最新的。"
            )
            session_sources = []
            if stock_result is not None:
                session_sources.append(
                    ("股票接口", stock_api_ts, stock_session)
                )
            if index_result is not None:
                session_sources.append(
                    ("指数接口", index_api_ts, index_session)
                )
            for source_name, _ts, session in session_sources:
                st.markdown(f"**{source_name}**")
                st.write(
                    f"接口时间：{session['local_time'] or '无法确认'}"
                )
                st.write(f"基础时段判断：{session['status']}")
                st.caption(session["detail"])

        # 2. 新鲜度
        with st.expander("2. 行情时间戳新鲜度", expanded=False):
            st.caption(
                "以当前 UTC 时间为参照，"
                "允许时间戳最大滞后 120 秒。"
                "通过仅表示时间戳年龄符合阈值，"
                "不证明行情源真实实时。"
            )
            if freshness_error:
                st.warning(freshness_error)
            elif freshness_result is None:
                st.info("尚无可评估的行情快照。")
            else:
                for source_name, result in (
                    ("股票快照", freshness_result["stock"]),
                    ("指数快照", freshness_result["index"]),
                ):
                    age = result["age_seconds"]
                    age_text = (
                        f"{age:.1f} 秒"
                        if isinstance(age, (int, float))
                        and not isinstance(age, bool)
                        else "不可计算"
                    )
                    if result["verified"] is True:
                        st.success(
                            f"{source_name}：检查通过，"
                            f"状态={result['status']}，年龄={age_text}"
                        )
                    else:
                        st.warning(
                            f"{source_name}：检查未通过，"
                            f"状态={result['status']}，年龄={age_text}"
                        )
                st.caption(
                    "综合新鲜度检查："
                    + (
                        "通过"
                        if freshness_result["verified"]
                        else "未通过"
                    )
                )
                st.write("股票快照：", freshness_result["stock"])
                st.write("指数快照：", freshness_result["index"])

        # 3. 接口时间差
        if stock_result is not None and index_result is not None:
            with st.expander(
                "3. 股票与指数接口时间差", expanded=False
            ):
                gap = timestamp_gap_seconds(stock_api_ts, index_api_ts)
                if gap is None:
                    st.warning("无法计算股票与指数接口的时间差。")
                else:
                    st.metric("接口时间差", f"{gap:.1f} 秒")
                    if gap <= TIME_GAP_WARNING_SECONDS:
                        st.info(
                            f"时间差未超过 "
                            f"{TIME_GAP_WARNING_SECONDS} 秒阈值。"
                        )
                    else:
                        st.warning(
                            f"时间差超过 "
                            f"{TIME_GAP_WARNING_SECONDS} 秒，"
                            "请谨慎比较两组数据。"
                        )

        # 4. 股票数据质量
        if stock_result is not None:
            with st.expander(
                "4. 全市场股票数据质量", expanded=False
            ):
                actual_count = stock_result["actual_record_count"]
                reported_count = stock_result["api_reported_total"]
                valid_count = stock_result["valid_change_count"]
                missing_count = stock_result["missing_change_count"]
                page_timestamps = stock_result["page_timestamps"]
                timestamps_consistent = stock_result[
                    "page_timestamps_consistent"
                ]

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("实际记录", f"{actual_count:,}")
                c2.metric("接口报告总数", f"{reported_count:,}")
                c3.metric("有效涨跌幅", f"{valid_count:,}")
                c4.metric("缺失涨跌幅", f"{missing_count:,}")

                if actual_count == reported_count:
                    st.success("记录数量检查通过。")
                else:
                    st.error("记录数量与接口报告总数不一致。")

                valid_timestamps = []
                for timestamp in page_timestamps:
                    try:
                        value = float(timestamp)
                        if pd.notna(value):
                            valid_timestamps.append(value)
                    except (TypeError, ValueError, OverflowError):
                        continue

                if (
                    page_timestamps
                    and len(valid_timestamps) == len(page_timestamps)
                ):
                    earliest_timestamp = min(valid_timestamps)
                    latest_timestamp = max(valid_timestamps)
                    spread = (
                        latest_timestamp - earliest_timestamp
                    ) / 1000

                    if timestamps_consistent:
                        st.success("分页时间戳一致。")
                    else:
                        st.warning("分页时间戳存在差异。")

                    st.metric("分页时间戳跨度", f"{spread:.1f} 秒")
                    st.caption(
                        f"最早：{format_api_time(earliest_timestamp)}；"
                        f"最晚：{format_api_time(latest_timestamp)}"
                    )
                else:
                    st.warning("部分分页时间戳缺失或无效。")

                st.caption(
                    f"股票接口数据时间："
                    f"{format_api_time(stock_api_ts)}"
                    f" · 来源："
                    f"{stock_result.get('source_api', '未提供')}"
                )

                with st.expander("查看逐页时间戳"):
                    timestamp_rows = [
                        {
                            "页码": page_number,
                            "原始时间戳（毫秒）": (
                                str(timestamp)
                                if timestamp is not None
                                else "缺失"
                            ),
                            "转换后的北京时间": format_api_time(
                                timestamp
                            ),
                        }
                        for page_number, timestamp in enumerate(
                            page_timestamps, start=1
                        )
                    ]
                    if timestamp_rows:
                        st.dataframe(
                            pd.DataFrame(timestamp_rows),
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.info("接口没有返回分页时间戳。")

        # 5. 统一质量评估
        if stock_result is not None:
            with st.expander(
                "5. 统一数据质量评估", expanded=False
            ):
                st.caption(
                    "阈值：涨跌幅缺失比例 ≤ 1%；"
                    "分页时间戳跨度 ≤ 60 秒；"
                    "接口时间差 ≤ 60 秒。"
                )

                if quality_error:
                    st.error(quality_error)
                elif quality_result is not None:
                    if quality_result["research_ready"]:
                        st.success("全部数据质量检查通过。")
                    elif quality_result[
                        "descriptive_statistics_ready"
                    ]:
                        st.warning(
                            "基础描述性统计门槛通过，"
                            "正式研究准入尚未全部满足。"
                        )
                    else:
                        st.error("基础描述性统计门槛未通过。")

                    check_labels = {
                        "record_count_matches": "记录数与接口报告总数一致",
                        "security_codes_valid": "证券代码有效",
                        "no_duplicate_codes": "证券代码无重复",
                        "page_timestamps_valid": "分页时间戳完整有效",
                        "page_timestamps_consistent": "分页时间戳一致",
                        "page_timestamp_spread_within_threshold":
                            "分页时间戳跨度在阈值内",
                        "change_values_valid": "非空涨跌幅数值有效",
                        "missing_ratio_within_threshold":
                            "涨跌幅缺失比例在阈值内",
                        "api_timestamps_comparable":
                            "股票与指数接口时间可比较",
                        "api_gap_within_threshold":
                            "股票与指数接口时间差在阈值内",
                    }
                    check_rows = [
                        {
                            "检查项目": label,
                            "结果": "通过"
                            if quality_result["checks"][key]
                            else "未通过",
                        }
                        for key, label in check_labels.items()
                    ]
                    st.dataframe(
                        pd.DataFrame(check_rows),
                        use_container_width=True,
                        hide_index=True,
                    )

                    if quality_result["warnings"]:
                        st.markdown("**警告**")
                        for warning in quality_result["warnings"]:
                            st.warning(warning)


# ============================================================
# 页脚：方法与免责声明
# ============================================================

st.divider()

with st.expander("📖 数据来源与研究限制", expanded=False):
    st.markdown(
        """
        **数据来源**

        - 股票快照：Fuyao A 股行情 API。
        - 指数快照：Fuyao A 股指数行情 API。
        - 涨跌幅字段：`price_change_ratio_pct`，单位为百分数。

        **质量控制**

        - 检查股票实际记录数与接口报告总数是否相符。
        - 检查证券代码重复、涨跌幅缺失和无效数值。
        - 检查分页时间戳和股票、指数接口时间差。
        - 未通过必要的数据质量检查时，不展示正式市场广度或状态结论。

        **研究限制**

        - API 数据就绪时间不一定等于交易所交易时间。
        - 分页时间戳一致不能单独证明分页属于同一个原子快照。
        - 市场广度按有效记录数量统计，不代表市值加权表现。
        - 市场状态分类依赖透明但尚未经过历史回测验证的规则。
        - 当前版本不推断未来价格，不生成买卖信号，不提供仓位建议。
        """
    )

st.caption(
    "项目定位：AI 驱动的股票市场趋势研究原型。"
    "结论应结合数据质量、来源时间与计算口径进行解读。"
)