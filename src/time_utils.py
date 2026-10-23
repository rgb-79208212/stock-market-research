
import math


def calculate_time_gap_seconds(stock_time_ms, index_time_ms):
    """计算两组 API 时间戳的绝对差值，单位为秒。

    缺失、格式错误、NaN 或无穷大均返回 None。
    """
    if stock_time_ms is None or index_time_ms is None:
        return None

    try:
        stock_time_ms = float(stock_time_ms)
        index_time_ms = float(index_time_ms)
    except (TypeError, ValueError, OverflowError):
        return None

    if not math.isfinite(stock_time_ms) or not math.isfinite(index_time_ms):
        return None

    return abs(stock_time_ms - index_time_ms) / 1000
