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
from src.time_utils import calculate_time_gap_seconds


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


def format_percent(value):
    """格式化百分数。API 涨跌幅单位本身就是百分数。"""
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


def get_item_value(item, key):
    """安全读取接口记录中的字段。"""
    value = item.get(key)

    if value is None:
        return None

    try:
        number = float(value)
        if pd.notna(number):
            return number
    except (TypeError, ValueError, OverflowError):
        pass

    return None


# ============================================================
# 数据获取
# ============================================================

st.subheader("实时行情")

st.write(
    "点击按钮获取股票全市场快照和三个主要指数的快照。"
    "股票全市场接口需要分页请求，获取过程可能需要一些时间。"
)

if st.button("获取最新行情", type="primary"):
    # 每次重新获取前，清除上一轮结果，避免失败后继续显示旧数据。
    st.session_state.pop("market_result", None)
    st.session_state.pop("index_result", None)
    st.session_state.pop("market_error", None)
    st.session_state.pop("index_error", None)

    with st.spinner("正在获取全市场股票和指数数据，请稍候……"):
        try:
            stock_result = fetch_stock_snapshot()
            st.session_state["market_result"] = stock_result
        except MarketDataError as exc:
            st.session_state["market_error"] = str(exc)
        except Exception as exc:
            st.session_state["market_error"] = (
                f"股票数据获取失败，错误类型：{type(exc).__name__}。"
                "请检查网络、API 服务和应用日志。"
            )

        try:
            index_result = fetch_index_snapshot()
            st.session_state["index_result"] = index_result
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


if stock_result is None and index_result is None:
    st.info(
        "尚未获取本次会话的实时行情。点击上方按钮开始获取。"
        "API Key 不需要填写在页面中。"
    )


# ============================================================
# 指数快照
# ============================================================

if index_result is not None:
    st.divider()
    st.subheader("主要指数表现")

    index_items = index_result["items"]

    columns = st.columns(3)

    for column, item in zip(columns, index_items):
        code = item.get("thscode", "未知代码")
        name = INDEX_NAMES.get(code, code)
        last_price = item.get("last_price")
        change_pct = item.get("price_change_ratio_pct")

        with column:
            st.metric(
                label=name,
                value=format_price(last_price),
                delta=format_percent(change_pct),
            )
            st.caption(f"证券代码：{code}")

    index_time = index_result.get("api_timestamp_ms")

    st.caption(
        f"指数接口数据时间：{format_api_time(index_time)}"
    )
    st.caption(
        f"来源：{index_result.get('source_api', '未提供')}"
    )


# ============================================================
# 股票数据质量
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
        st.error(
            "记录数量检查未通过：实际记录数与接口报告总数不一致。"
        )

    if timestamps_consistent:
        st.success(
            "分页时间戳检查通过：各页返回了相同的非空时间戳。"
        )
        st.caption(
            "注意：时间戳一致不等于已经证明所有分页来自同一个原子快照。"
        )
    else:
        st.warning(
            "分页时间戳不一致或存在缺失。"
            "本次不生成正式市场广度结论。"
        )

    st.caption(
        f"股票接口数据时间："
        f"{format_api_time(stock_result.get('api_timestamp_ms'))}"
    )
    st.caption(
        f"来源：{stock_result.get('source_api', '未提供')}"
    )

    with st.expander("查看逐页时间戳"):
        timestamp_rows = []

        for page_number, timestamp in enumerate(page_timestamps, start=1):
            timestamp_rows.append(
                {
                    "页码": page_number,
                    "原始时间戳（毫秒）": (
                        str(timestamp) if timestamp is not None else "缺失"
                    ),
                    "转换后的北京时间": format_api_time(timestamp),
                }
            )

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
                "这不代表两组数据完全同步，也不能证明它们属于同一交易时点。"
            )
        else:
            st.warning(
                f"时间差超过 {TIME_GAP_WARNING_SECONDS} 秒。"
                "请谨慎比较两组数据。"
            )


# ============================================================
# 市场广度
# ============================================================

if stock_result is not None:
    st.divider()
    st.subheader("市场广度")

    timestamps_consistent = stock_result["page_timestamps_consistent"]
    count_matches = (
        stock_result["actual_record_count"]
        == stock_result["api_reported_total"]
    )

    if not timestamps_consistent:
        st.warning(
            "当前股票分页时间戳检查未通过。"
            "为避免把不同时间的数据拼成一个市场截面，"
            "本页面不展示正式市场广度统计。"
        )

    elif not count_matches:
        st.error(
            "股票记录数量检查未通过，不能计算正式市场广度。"
        )

    else:
        try:
            breadth = calculate_market_breadth(stock_result["items"])

            st.caption(
                "计算口径：上涨为涨跌幅大于 0；"
                "下跌为涨跌幅小于 0；平盘为涨跌幅等于 0。"
                "缺失涨跌幅记录不计入有效分母。"
            )

            metric1, metric2, metric3 = st.columns(3)

            metric1.metric("上涨标的", f"{breadth['advancers']:,}")
            metric2.metric("下跌标的", f"{breadth['decliners']:,}")
            metric3.metric("平盘标的", f"{breadth['unchanged']:,}")

            ratio1, ratio2, ratio3 = st.columns(3)

            ratio1.metric(
                "上涨占比",
                (
                    f"{breadth['advance_ratio_pct']:.2f}%"
                    if breadth["advance_ratio_pct"] is not None
                    else "暂无数据"
                ),
            )

            ratio2.metric(
                "下跌占比",
                (
                    f"{breadth['decline_ratio_pct']:.2f}%"
                    if breadth["decline_ratio_pct"] is not None
                    else "暂无数据"
                ),
            )

            ratio3.metric(
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
                f"纳入统计的有效涨跌幅记录："
                f"{breadth['valid_change_count']:,}；"
                f"缺失涨跌幅记录："
                f"{breadth['missing_change_count']:,}。"
            )

            st.info(
                "以上是基于接口返回记录的描述性统计，"
                "不代表未来走势，也不构成买卖或仓位建议。"
            )

        except (ValueError, KeyError, TypeError) as exc:
            st.error(
                "市场广度计算未完成。"
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
    - 检查各页返回的时间戳是否一致。
    - 比较股票与指数接口的时间戳差异。
    - 未通过必要的数据质量检查时，不展示正式市场广度结论。

    **研究限制**

    - API 数据就绪时间不一定等于交易所交易时间。
    - 分页时间戳一致不能单独证明分页属于同一个原子快照。
    - 当前版本不推断未来价格，不生成买卖信号，不提供仓位建议。
    - 市场广度描述的是已获取数据中的上涨、下跌和平盘分布；
      不能单独代表市场风险或未来收益。
    """
)

st.caption(
    "项目定位：AI 驱动的股票市场趋势研究原型。"
    "结论应结合数据质量、来源时间与计算口径进行解读。"
)