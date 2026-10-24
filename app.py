
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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
from src.research_applicability import (
    assess_research_applicability,
)
from src.market_freshness import assess_snapshot_freshness


import hashlib
import json



# ============================================================
# 页面配置
# ============================================================

st.set_page_config(
    page_title="A股市场状态研究",
    page_icon="📊",
    layout="wide",
)

TIME_GAP_WARNING_SECONDS = 60

INDEX_NAMES = {
    "000001.SH": "上证指数",
    "399001.SZ": "深证成指",
    "000300.SH": "沪深300",
}

st.title("A股市场状态研究")
st.caption(
    "AI 驱动的市场状态研究原型｜描述性分析，不构成投资建议"
)


# ============================================================
# 辅助函数
# ============================================================

def format_api_time(timestamp_ms):
    """将 API 毫秒时间戳转换为北京时间。"""
    if timestamp_ms is None:
        return "未提供"

    try:
        timestamp = float(timestamp_ms)
        if not pd.notna(timestamp):
            return "无效时间戳"

        dt = datetime.fromtimestamp(
            timestamp / 1000,
            tz=timezone.utc,
        ).astimezone(ZoneInfo("Asia/Shanghai"))

        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")

    except (ValueError, TypeError, OverflowError, OSError):
        return "无效时间戳"

def format_unix_seconds(timestamp_seconds):
    """将 Unix 秒级时间戳转换为北京时间。"""
    if timestamp_seconds is None:
        return "未提供"

    try:
        timestamp = float(timestamp_seconds)

        if not pd.notna(timestamp):
            return "无效时间戳"

        dt = datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        ).astimezone(ZoneInfo("Asia/Shanghai"))

        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")

    except (ValueError, TypeError, OverflowError, OSError):
        return "无效时间戳"


def format_percent(value):
    """格式化百分数。"""
    try:
        number = float(value)
        if pd.notna(number):
            return f"{number:+.2f}%"
    except (TypeError, ValueError, OverflowError):
        pass

    return "暂无数据"


def format_price(value):
    """格式化价格。"""
    try:
        number = float(value)
        if pd.notna(number):
            return f"{number:,.2f}"
    except (TypeError, ValueError, OverflowError):
        pass

    return "暂无数据"


def timestamp_gap_seconds(timestamp_a, timestamp_b):
    """计算两个 API 毫秒时间戳的差值。"""
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


# ============================================================
# 数据获取
# ============================================================

st.subheader("行情快照")

st.write(
    "点击按钮获取全市场股票快照和三个主要指数的快照。"
    "股票全市场接口需要分页请求，获取过程可能需要一些时间。"
)

if st.button("获取行情快照", type="primary"):
    # 重新获取前清除旧结果，防止请求失败后沿用旧行情。
    for key in (
        "market_result",
        "index_result",
        "market_error",
        "index_error",
    ):
        st.session_state.pop(key, None)

    with st.spinner("正在获取全市场股票和指数数据，请稍候……"):
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
    st.error(f"股票快照获取失败：{st.session_state['market_error']}")

if "index_error" in st.session_state:
    st.error(f"指数快照获取失败：{st.session_state['index_error']}")


stock_result = st.session_state.get("market_result")
index_result = st.session_state.get("index_result")


# ============================================================
# 基础交易时段检查
# ============================================================

if stock_result is not None or index_result is not None:
    st.divider()
    st.subheader("行情时间与交易时段检查")

    st.caption(
        "根据接口返回的时间戳判断基础时段；"
        "本检查不等于交易所交易日历验证，也不能证明行情是最新的。"
    )

    session_sources = []

    if stock_result is not None:
        session_sources.append(
            (
                "股票接口",
                stock_result.get("api_timestamp_ms"),
            )
        )

    if index_result is not None:
        session_sources.append(
            (
                "指数接口",
                index_result.get("api_timestamp_ms"),
            )
        )

    for source_name, timestamp_ms in session_sources:
        session = assess_market_session(timestamp_ms)

        st.markdown(f"**{source_name}**")
        st.write(f"接口时间：{session['local_time'] or '无法确认'}")
        st.write(f"基础时段判断：{session['status']}")
        st.caption(session["detail"])

        if session["status"] == "周末（非交易日）":
            st.warning(
                f"{source_name}的接口时间落在周末。"
                "请勿将本次结果直接描述为交易时段实时行情。"
            )
        elif session["status"] == "无法判断":
            st.warning(
                f"{source_name}缺少有效时间戳，"
                "无法完成基础交易时段判断。"
            )
        elif session["within_regular_session"]:
            st.info(
                f"{source_name}的时间处于常规连续交易时段范围内，"
                "但尚未核验节假日、临时休市或行情新鲜度。"
            )
        else:
            st.warning(
                f"{source_name}的时间不在常规连续交易时段内。"
                "这可能是盘前、午间休市或盘后数据。"
            )

    st.warning(
        "本版本尚未接入官方交易日历。"
        "接口时间戳可能是数据生成时间或接口处理时间，"
        "不能单独证明行情对应的真实交易时点。"
    )




# 如果股票获取成功，但指数请求失败，传入无效哨兵值，
# 让数据质量模块明确判定指数比较不可用。
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

# 独立评估股票和指数快照的时间戳新鲜度。
# 使用同一个参考时刻，确保两份结果可以直接比较。
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

st.divider()
st.subheader("行情时间戳新鲜度")

st.caption(
    "本检查以当前 UTC 时间为参照，默认允许时间戳最大滞后 120 秒。"
    "通过只表示时间戳年龄符合阈值，不证明行情源真实实时，"
    "也不代表交易日历已经核实。"
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
            if isinstance(age, (int, float)) and not isinstance(age, bool)
            else "不可计算"
        )

        if result["verified"] is True:
            st.success(
                f"{source_name}：时间戳年龄检查通过，"
                f"状态={result['status']}，年龄={age_text}"
            )
        else:
            st.warning(
                f"{source_name}：时间戳年龄检查未通过，"
                f"状态={result['status']}，年龄={age_text}"
            )

    st.caption(
        "综合新鲜度检查："
        + ("通过" if freshness_result["verified"] else "未通过")
    )


if stock_result is None and index_result is None:
    st.info(
        "尚未获取本次会话的行情快照。点击上方按钮开始获取。"
        "API Key 不需要填写在页面中。"
    )


# ============================================================
# 主要指数表现
# ============================================================

if index_result is not None:
    st.divider()
    st.subheader("主要指数表现")

    index_items = index_result["items"]
    columns = st.columns(3)

    for column, item in zip(columns, index_items):
        code = item.get("thscode", "未知代码")
        name = INDEX_NAMES.get(code, code)

        with column:
            st.metric(
                label=name,
                value=format_price(item.get("last_price")),
                delta=format_percent(
                    item.get("price_change_ratio_pct")
                ),
            )
            st.caption(f"证券代码：{code}")

    st.caption(
        "指数接口数据时间："
        f"{format_api_time(index_result.get('api_timestamp_ms'))}"
    )
    st.caption(
        f"来源：{index_result.get('source_api', '未提供')}"
    )


# ============================================================
# 全市场股票数据质量
# ============================================================

if stock_result is not None:
    st.divider()
    st.subheader("全市场股票数据质量")

    actual_count = stock_result["actual_record_count"]
    reported_count = stock_result["api_reported_total"]
    valid_count = stock_result["valid_change_count"]
    missing_count = stock_result["missing_change_count"]
    page_timestamps = stock_result["page_timestamps"]
    timestamps_consistent = stock_result["page_timestamps_consistent"]

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("实际获取记录", f"{actual_count:,}")
    col2.metric("接口报告总数", f"{reported_count:,}")
    col3.metric("有效涨跌幅", f"{valid_count:,}")
    col4.metric("缺失涨跌幅", f"{missing_count:,}")

    count_matches = actual_count == reported_count

    if count_matches:
        st.success("记录数量检查通过：实际记录数与接口报告总数相符。")
    else:
        st.error("记录数量检查未通过：实际记录数与接口报告总数不一致。")

    valid_timestamps = []

    for timestamp in page_timestamps:
        try:
            value = float(timestamp)
            if pd.notna(value):
                valid_timestamps.append(value)
        except (TypeError, ValueError, OverflowError):
            continue

    if page_timestamps and len(valid_timestamps) == len(page_timestamps):
        earliest_timestamp = min(valid_timestamps)
        latest_timestamp = max(valid_timestamps)
        timestamp_spread_seconds = (
            latest_timestamp - earliest_timestamp
        ) / 1000

        if timestamps_consistent:
            st.success("分页时间戳检查通过：所有页面的时间戳相同。")
            st.caption(
                "注意：时间戳相同不能单独证明所有分页来自同一个原子快照。"
            )
        else:
            st.warning(
                "分页时间戳存在差异。不能仅凭该差异断定数据无效，"
                "但也不能据此确认所有分页属于同一行情时点。"
            )

        st.metric(
            "分页时间戳跨度",
            f"{timestamp_spread_seconds:.1f} 秒",
        )
        st.caption(
            f"最早：{format_api_time(earliest_timestamp)}；"
            f"最晚：{format_api_time(latest_timestamp)}"
        )
    else:
        st.warning(
            "部分分页时间戳缺失或无效，无法确认全部分页的时间范围。"
        )

    st.caption(
        "股票接口数据时间："
        f"{format_api_time(stock_result.get('api_timestamp_ms'))}"
    )
    st.caption(
        f"来源：{stock_result.get('source_api', '未提供')}"
    )

    with st.expander("查看逐页时间戳"):
        timestamp_rows = [
            {
                "页码": page_number,
                "原始时间戳（毫秒）": (
                    str(timestamp) if timestamp is not None else "缺失"
                ),
                "转换后的北京时间": format_api_time(timestamp),
            }
            for page_number, timestamp in enumerate(
                page_timestamps,
                start=1,
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


# ============================================================
# 股票与指数接口时间差
# ============================================================

if stock_result is not None and index_result is not None:
    st.divider()
    st.subheader("接口时间差检查")

    gap = timestamp_gap_seconds(
        stock_result.get("api_timestamp_ms"),
        index_result.get("api_timestamp_ms"),
    )

    if gap is None:
        st.warning("无法计算股票与指数接口的时间差。")
    else:
        st.metric("股票与指数接口时间差", f"{gap:.1f} 秒")

        if gap <= TIME_GAP_WARNING_SECONDS:
            st.info(
                f"时间差未超过 {TIME_GAP_WARNING_SECONDS} 秒的提示阈值。"
                "这不代表两组数据完全同步。"
            )
        else:
            st.warning(
                f"时间差超过 {TIME_GAP_WARNING_SECONDS} 秒。"
                "请谨慎比较两组数据。"
            )


# ============================================================
# 统一数据质量评估
# ============================================================

if stock_result is not None:
    st.divider()
    st.subheader("统一数据质量评估")

    st.caption(
        "项目阈值：涨跌幅缺失比例不超过 1%；分页时间戳跨度不超过 "
        "60 秒；需要比较股票与指数数据时，接口时间差不超过 60 秒。"
    )

    if quality_error:
        st.error(quality_error)

    elif quality_result is not None:
        if quality_result["research_ready"]:
            st.success(
                "基础数据质量门槛通过：可以展示本次快照的描述性统计。"
            )
        else:
            st.error(
                "基础数据质量门槛未通过：暂不展示正式市场统计和状态结论。"
            )

        check_labels = {
            "record_count_matches": "实际记录数与接口报告总数一致",
            "security_codes_valid": "证券代码有效",
            "no_duplicate_codes": "证券代码无重复",
            "page_timestamps_valid": "分页时间戳完整有效",
            "page_timestamp_spread_within_threshold": "分页时间戳跨度在阈值内",
            "change_values_valid": "非空涨跌幅数值有效",
            "missing_ratio_within_threshold": "涨跌幅缺失比例在阈值内",
            "api_timestamps_comparable": "股票与指数接口时间可比较",
            "api_gap_within_threshold": "股票与指数接口时间差在阈值内",
        }

        check_rows = [
            {
                "检查项目": label,
                "结果": (
                    "通过"
                    if quality_result["checks"][key]
                    else "未通过"
                ),
            }
            for key, label in check_labels.items()
        ]

        st.dataframe(
            pd.DataFrame(check_rows),
            use_container_width=True,
            hide_index=True,
        )

        if quality_result["warnings"]:
            with st.expander(
                "查看数据质量警告",
                expanded=not quality_result["research_ready"],
            ):
                for warning in quality_result["warnings"]:
                    st.warning(warning)
        else:
            st.caption("当前检查未产生额外警告。")

        st.info(
            "质量门槛通过不代表已确认当前处于交易时段，"
            "也不证明分页数据来自同一个原子快照。"
        )


# ============================================================
# 市场广度
# ============================================================

breadth_for_state = None

if stock_result is not None:
    st.divider()
    st.subheader("市场广度")

    if quality_error or quality_result is None:
        st.error("数据质量评估不可用，不能展示正式市场广度统计。")

    elif not quality_result["research_ready"]:
        st.error(
            "统一数据质量门槛未通过，暂不展示正式市场广度统计。"
            "请先查看上方检查结果和警告。"
        )

    else:
        if not stock_result["page_timestamps_consistent"]:
            st.warning(
                "分页时间戳存在差异，但跨度处于项目设定阈值内。"
                "以下统计只描述本次已获取记录，不证明所有记录来自同一行情时点。"
            )
        else:
            st.info(
                "分页时间戳一致，但这不能单独证明所有记录来自同一个原子快照。"
            )

        try:
            breadth = calculate_market_breadth(stock_result["items"])
            breadth_for_state = breadth

            st.caption(
                "计算口径：上涨为涨跌幅大于 0；下跌为小于 0；"
                "平盘为等于 0。缺失涨跌幅记录不计入有效分母。"
            )

            metric1, metric2, metric3 = st.columns(3)

            metric1.metric("上涨标的", f"{breadth['advancers']:,}")
            metric2.metric("下跌标的", f"{breadth['decliners']:,}")
            metric3.metric("平盘标的", f"{breadth['unchanged']:,}")

            ratio1, ratio2, ratio3, ratio4 = st.columns(4)

            ratio1.metric(
                "上涨占比",
                f"{breadth['advance_ratio_pct']:.2f}%",
            )
            ratio2.metric(
                "下跌占比",
                f"{breadth['decline_ratio_pct']:.2f}%",
            )
            ratio3.metric(
                "平盘占比",
                f"{breadth['unchanged_ratio_pct']:.2f}%",
            )
            ratio4.metric(
                "有效涨跌幅记录",
                f"{breadth['valid_change_count']:,}",
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
                f"有效涨跌幅记录：{breadth['valid_change_count']:,}；"
                f"缺失涨跌幅记录：{breadth['missing_change_count']:,}。"
            )

            st.info(
                "以上是本次快照的描述性统计，不代表未来走势，"
                "也不构成买卖或仓位建议。"
            )

        except (ValueError, KeyError, TypeError) as exc:
            breadth_for_state = None
            st.error(f"市场广度计算未完成。原因：{exc}")


# ============================================================
# 市场状态研判
# ============================================================
state_result = None
st.divider()
st.subheader("市场状态研判")

st.caption(
    "规则引擎 v1：结合全市场上涨占比和三个主要指数的涨跌方向。"
    "本分类用于描述当前快照，阈值尚未经过历史回测验证。"
)

if stock_result is None:
    st.info("请先获取最新行情，再进行市场状态研判。")

elif quality_error or quality_result is None:
    st.error("数据质量评估不可用，不能生成市场状态结论。")

elif not quality_result["research_ready"]:
    st.error(
        "数据质量门槛未通过，暂不生成市场状态结论。"
        "请先查看统一数据质量评估中的未通过项目。"
    )

elif index_result is None:
    st.error("缺少主要指数快照，不能生成完整的市场状态结论。")

elif breadth_for_state is None:
    st.error("市场广度计算不可用，不能生成市场状态结论。")

else:
    try:
        state_result = assess_market_state(
            breadth_for_state,
            index_result["items"],
        )

        st.markdown("#### 本次快照规则分类")

        st.subheader(state_result["state"])
        st.write(state_result["rationale"])
        st.caption(
            "这是对本次已获取快照的规则分类，不代表当前实时市场状态已确认，"
            "也不代表该规则已通过历史回测。"
        )

        # 快照阶段预检：用于提示当前数据的适用性限制。
        # 最终报告阶段以 research_report["research_applicability"] 为准。
        applicability = None

        if (
            isinstance(stock_result, dict)
            and isinstance(index_result, dict)
            and quality_result is not None
            and not quality_error
            and breadth_for_state is not None
        ):
            try:
                applicability = assess_research_applicability(
                    basic_quality_gate=(
                        "passed"
                        if quality_result.get("research_ready") is True
                        else "failed"
                    ),
                    stock_session=assess_market_session(
                        stock_result.get("api_timestamp_ms")
                    ),
                    index_session=assess_market_session(
                        index_result.get("api_timestamp_ms")
                    ),
                    market_calendar_verified=quality_result.get(
                        "market_calendar_verified", False
                    ) is True,
                    market_session_verified=quality_result.get(
                        "market_session_verified", False
                    ) is True,
                    market_freshness_verified=quality_result.get(
                        "market_freshness_verified", False
                    ) is True,
                )
            except (ValueError, TypeError, KeyError) as exc:
                st.warning(
                    f"研究适用性判断暂时无法完成：{exc}"
                )

        if applicability is not None:
            if applicability[
                "current_snapshot_applicability_confirmed"
            ]:
                st.success(
                    "当前快照时点条件已验证。"
                    "这不代表规则已经通过历史回测。"
                )
            else:
                st.warning(
                    "当前市场状态尚未确认。以下仅展示本次快照的"
                    "规则分类，不应视为已验证的实时市场状态。"
                )

        st.markdown("#### 主要证据")

        for evidence_item in state_result["evidence"]:
            st.markdown(f"- {evidence_item}")

        st.markdown("#### 主要指数方向")

        index_rows = []

        for item in state_result["index_results"]:
            index_rows.append(
                {
                    "指数": item["name"],
                    "代码": item["code"],
                    "涨跌幅": format_percent(item["change_pct"]),
                    "方向": item["direction"],
                }
            )

        st.dataframe(
            pd.DataFrame(index_rows),
            use_container_width=True,
            hide_index=True,
        )

        metrics = state_result["metrics"]

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "上涨占比",
            f"{metrics['advance_ratio_pct']:.2f}%",
        )
        col2.metric(
            "上涨指数数量",
            f"{metrics['positive_indices']} / 3",
        )
        col3.metric(
            "下跌指数数量",
            f"{metrics['negative_indices']} / 3",
        )

        st.markdown("#### 状态切换条件")

        st.caption(
            "以下是规则重新评估的条件，不代表达到条件后市场必然上涨或下跌。"
        )

        for condition in state_result["state_switch_conditions"]:
            st.markdown(f"- {condition}")

        with st.expander("查看分类方法与研究限制", expanded=True):
            st.markdown("**本版本采用的上涨占比阈值**")

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

            st.warning(
                "这些阈值是项目初始规则，尚未通过历史回测验证，"
                "不能解释为已验证的市场规律。"
            )

            st.markdown("**研究限制**")

            for limitation in state_result["limitations"]:
                st.markdown(f"- {limitation}")

    except (ValueError, KeyError, TypeError) as exc:
        st.error(
            "市场状态研判未完成。"
            f"原因：{exc}"
        )


# ============================================================
# 可审计的结构化研究报告
# ============================================================

st.divider()
st.subheader("结构化研究报告")

st.caption(
    "本报告整合本次行情快照、数据质量检查、市场广度与规则分类。"
    "报告组合器本身不调用大模型，也不预测未来涨跌。"
)

# 仅当前面的数据质量、市场广度和状态分类均成功时生成报告。
report_inputs_ready = (
    stock_result is not None
    and index_result is not None
    and quality_error is None
    and quality_result is not None
    and quality_result.get("research_ready") is True
    and breadth_for_state is not None
    and isinstance(state_result, dict)
)

if not report_inputs_ready:
    st.info(
        "当前无法生成正式结构化报告。"
        "请先确认股票快照、指数快照、数据质量门槛、"
        "市场广度计算和市场状态研判均成功。"
    )
else:
    try:
        research_report = build_research_report(
            stock_result=stock_result,
            index_result=index_result,
            quality_result=quality_result,
            breadth=breadth_for_state,
            state_result=state_result,
            freshness_result=freshness_result,
        )

        st.markdown("#### 1. 本次研究概览")

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "快照规则分类",
            research_report["market_state"]["label"],
        )
        col2.metric(
            "质量检查通过项",
            (
                f"{research_report['evidence_quality']['passed_check_count']} / "
                f"{research_report['evidence_quality']['total_check_count']}"
            ),
        )
        col3.metric(
            "历史回测验证",
            (
                "已验证"
                if research_report["evidence_quality"]["historically_validated"]
                else "尚未验证"
            ),
        )

        st.markdown("#### 2. 可核查事实")

        for item in research_report["facts"]:
            st.markdown(f"- {item['claim']}")
            st.caption(
                f"证据类型：{item['evidence_type']}｜来源：{item['source']}"
            )

        st.markdown("#### 3. 规则解释")

        for item in research_report["interpretations"]:
            st.write(item["claim"])

            if item["basis"]:
                st.caption("依据")
                for evidence in item["basis"]:
                    st.markdown(f"- {evidence}")

        st.markdown("#### 4. 尚未验证的假设与问题")

        for item in research_report["hypotheses"]:
            st.markdown(f"- **{item['claim']}**")
            st.caption(f"原因：{item['reason']}")

        st.markdown("#### 5. 证据质量与时间信息")

        evidence_quality = research_report["evidence_quality"]
        evidence_time = research_report["evidence_time"]

        stock_session = evidence_quality.get("stock_market_session", {})
        index_session = evidence_quality.get("index_market_session", {})

        st.write(
            {
                "股票接口时间（UTC）": evidence_time["stock_api_time_utc"],
                "指数接口时间（UTC）": evidence_time["index_api_time_utc"],
                "两个接口时间戳完全相同": evidence_time["timestamps_match"],
                "基础质量门槛": evidence_quality["basic_quality_gate"],
                "分页时间跨度（秒）": evidence_quality[
                    "page_timestamp_spread_seconds"
                ],
                "股票与指数接口时间差（秒）": evidence_quality[
                    "stock_index_api_gap_seconds"
                ],
                "股票接口基础时段判断": stock_session.get(
                    "status", "无法判断"
                ),
                "指数接口基础时段判断": index_session.get(
                    "status", "无法判断"
                ),
                "官方交易日历已验证": evidence_quality.get(
                    "market_calendar_verified", False
                ),
                "交易时段已验证": evidence_quality[
                    "market_session_verified"
                ],
                "行情新鲜度已验证": evidence_quality.get(
                    "market_freshness_verified",
                    False,
                ),
                "独立数据源已交叉验证": evidence_quality[
                    "independent_source_verified"
                ],
            }
        )

        # ============================================================
        # 研究适用性判断
        # ============================================================

        st.markdown("#### 研究适用性判断")

        applicability = research_report.get(
            "research_applicability",
            {},
        )

        if not applicability:
            st.warning(
                "当前报告没有研究适用性判断结果。"
                "请检查 research_report.py 是否已接入该模块。"
            )
        else:
            applicability_status = applicability.get(
                "status",
                "未知",
            )

            if applicability_status == "当前快照时点条件已验证":
                st.success(applicability_status)

            elif applicability_status == "时段适用性未确认":
                st.warning(applicability_status)

            else:
                st.error(applicability_status)

            st.caption(
                "该判断用于说明本次快照是否具备相应的研究适用条件，"
                "不代表规则经过历史回测，也不预测未来市场走势。"
            )

            st.write(
                {
                    "允许展示快照描述性统计": applicability.get(
                        "snapshot_statistics_allowed",
                        False,
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



        if evidence_quality["warnings"]:
            st.markdown("**数据质量警告**")
            for warning in evidence_quality["warnings"]:
                st.warning(warning)

        st.markdown("#### 6. 证据充分度说明")

        confidence_basis = research_report["confidence_basis"]

        st.write(confidence_basis["label"])
        st.write(confidence_basis["interpretation"])

        for reason in confidence_basis["reasons"]:
            st.markdown(f"- {reason}")

        st.markdown("#### 7. 状态重新评估条件")

        for condition in research_report["market_state"]["switch_conditions"]:
            st.markdown(f"- {condition}")

        with st.expander("查看完整报告数据（JSON）"):
            st.json(research_report)

        st.caption(research_report["disclaimer"])


        # ============================================================
        # DeepSeek AI 解读：只解释结构化报告，不修改规则分类
        # ============================================================

        st.divider()
        st.markdown("#### 8. DeepSeek AI 解读")

        st.caption(
            "AI 仅依据本次结构化研究报告进行解释，"
            "不重新判断市场状态，不预测未来涨跌，也不提供交易建议。"
        )

        # 用关键报告内容生成缓存标识，避免重复请求，
        # 同时避免把旧行情的解读误用于新报告。
        llm_input = {
            "market_state": research_report["market_state"],
            "facts": research_report["facts"],
            "interpretations": research_report["interpretations"],
            "hypotheses": research_report["hypotheses"],
            "evidence_time": research_report["evidence_time"],
            "evidence_quality": research_report["evidence_quality"],
            "research_applicability": research_report.get(
                "research_applicability",
                {},
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
            # 新报告对应新缓存；不沿用旧报告的解读。
            st.session_state.pop(cache_result_name, None)
            st.session_state.pop(cache_key_name, None)

            try:
                with st.spinner("DeepSeek 正在分析结构化研究报告……"):
                    llm_result = generate_llm_interpretation(
                        research_report
                    )

                st.session_state[cache_result_name] = llm_result
                st.session_state[cache_key_name] = llm_cache_key

            except LLMAnalysisError as exc:
                st.error(f"AI 解读生成失败：{exc}")

        # 只有缓存与当前报告匹配时才显示结果。
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


    except (ValueError, KeyError, TypeError) as exc:
        st.error(
            "结构化研究报告生成失败，未展示正式报告。"
            f"原因：{exc}"
        )





# ============================================================
# 方法、限制与免责声明
# ============================================================

st.divider()
st.subheader("数据来源与研究限制")

st.markdown(
    """
    **数据来源**

    - 股票快照：Fuyao A 股行情 API。
    - 指数快照：Fuyao A 股指数行情 API。
    - 涨跌幅字段：`price_change_ratio_pct`，单位为百分数；
      例如 `1.74` 表示上涨 `1.74%`。

    **质量控制**

    - 检查股票实际记录数与接口报告总数是否相符。
    - 检查证券代码重复、涨跌幅缺失和无效数值。
    - 检查分页时间戳和股票、指数接口时间差。
    - 未通过必要的数据质量检查时，不展示正式市场广度统计或状态结论。

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
