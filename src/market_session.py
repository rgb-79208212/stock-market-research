
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo


BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def assess_market_session(timestamp_ms):
    """根据 API 毫秒时间戳判断基础交易时段。

    注意：
    1. 只判断星期和常规连续交易时段。
    2. 不核验法定节假日、临时休市或特殊交易安排。
    3. API 时间戳不一定等于交易所实际行情生成时间。
    """
    if timestamp_ms is None:
        return {
            "status": "无法判断",
            "is_weekend": None,
            "within_regular_session": None,
            "local_time": None,
            "detail": "接口未提供时间戳，无法判断基础交易时段。",
        }

    try:
        timestamp = float(timestamp_ms)

        if not timestamp_ms or timestamp != timestamp:
            raise ValueError("无效时间戳")

        dt = datetime.fromtimestamp(
            timestamp / 1000,
            tz=timezone.utc,
        ).astimezone(BEIJING_TZ)

    except (ValueError, TypeError, OverflowError, OSError):
        return {
            "status": "无法判断",
            "is_weekend": None,
            "within_regular_session": None,
            "local_time": None,
            "detail": "接口时间戳无效，无法判断基础交易时段。",
        }

    local_time = dt.strftime("%Y-%m-%d %H:%M:%S %Z")

    # Python：周一为 0，周日为 6。
    if dt.weekday() >= 5:
        return {
            "status": "周末（非交易日）",
            "is_weekend": True,
            "within_regular_session": False,
            "local_time": local_time,
            "detail": (
                "接口时间戳落在周末。该记录不能仅凭接口请求成功"
                "就被称为交易时段实时行情。"
            ),
        }

    clock_time = dt.time().replace(tzinfo=None)

    morning_session = time(9, 30) <= clock_time <= time(11, 30)
    afternoon_session = time(13, 0) <= clock_time <= time(15, 0)
    within_session = morning_session or afternoon_session

    if within_session:
        return {
            "status": "工作日常规连续交易时段（未核验节假日）",
            "is_weekend": False,
            "within_regular_session": True,
            "local_time": local_time,
            "detail": (
                "时间落在工作日常规连续交易时段范围内；"
                "尚未核验法定节假日、临时休市或实际行情新鲜度。"
            ),
        }

    return {
        "status": "工作日非连续交易时段（未核验节假日）",
        "is_weekend": False,
        "within_regular_session": False,
        "local_time": local_time,
        "detail": (
            "时间不在工作日常规连续交易时段范围内。"
            "这可能是开盘前、午间休市或收盘后；"
            "本模块尚未核验法定节假日及特殊交易安排。"
        ),
    }
