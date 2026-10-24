"""行情快照数据质量评估。只检查数据质量，不判断交易时段或预测市场走势。"""

import math


def _to_finite_number(value):
    """转换为有限数值；布尔值和无效输入返回 None。"""
    if value is None or isinstance(value, bool):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None

    return number if math.isfinite(number) else None


def _to_non_negative_int(value):
    number = _to_finite_number(value)
    if number is None or number < 0 or not number.is_integer():
        return None
    return int(number)


def _validate_threshold(name, value, *, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} 必须是数值。")

    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} 必须是非负有限数值。")

    if maximum is not None and value > maximum:
        raise ValueError(f"{name} 不能超过 {maximum}。")


def assess_snapshot_quality(
    stock_result,
    index_result=None,
    max_missing_ratio_pct=1.0,
    max_page_timestamp_spread_seconds=60.0,
    max_api_gap_seconds=60.0,
):
    """
    评估行情快照质量。

    descriptive_statistics_ready:
        仅决定股票快照是否适合展示基础描述性统计。
        分页时间戳不完全一致，但跨度仍在阈值内时，
        可以展示统计，同时必须保留时间一致性警告。

    research_ready:
        严格门槛，要求所有质量检查通过。
        不代表官方交易日历已验证，也不证明分页来自原子快照。
    """
    if not isinstance(stock_result, dict):
        raise ValueError("stock_result 必须是字典。")

    _validate_threshold(
        "max_missing_ratio_pct",
        max_missing_ratio_pct,
        maximum=100,
    )
    _validate_threshold(
        "max_page_timestamp_spread_seconds",
        max_page_timestamp_spread_seconds,
    )
    _validate_threshold("max_api_gap_seconds", max_api_gap_seconds)

    items = stock_result.get("items")
    if not isinstance(items, list):
        raise ValueError("股票快照缺少有效的 items 列表。")

    actual_count = len(items)
    reported_count = _to_non_negative_int(
        stock_result.get("api_reported_total")
    )
    count_matches = (
        reported_count is not None
        and actual_count == reported_count
    )

    # 检查证券代码和重复记录。
    codes = []
    security_codes_valid = True

    for item in items:
        if not isinstance(item, dict):
            security_codes_valid = False
            continue

        code = item.get("thscode")
        if not isinstance(code, str) or not code.strip():
            security_codes_valid = False
            continue

        codes.append(code.strip())

    no_duplicate_codes = (
        security_codes_valid
        and len(codes) == len(set(codes))
    )

    # 检查每页时间戳。
    page_timestamps = stock_result.get("page_timestamps")
    if not isinstance(page_timestamps, list):
        page_timestamps = []

    valid_timestamps = []

    for timestamp in page_timestamps:
        number = _to_finite_number(timestamp)
        if number is not None and number > 0:
            valid_timestamps.append(number)

    page_timestamps_valid = (
        bool(page_timestamps)
        and len(valid_timestamps) == len(page_timestamps)
    )

    if page_timestamps_valid:
        spread_seconds = (
            max(valid_timestamps) - min(valid_timestamps)
        ) / 1000
        timestamps_consistent = (
            len(set(valid_timestamps)) == 1
        )
    else:
        spread_seconds = None
        timestamps_consistent = False

    spread_within_threshold = (
        spread_seconds is not None
        and spread_seconds <= max_page_timestamp_spread_seconds
    )

    # 检查涨跌幅字段。
    valid_change_count = 0
    missing_change_count = 0
    invalid_change_count = 0

    for item in items:
        if not isinstance(item, dict):
            invalid_change_count += 1
            continue

        value = item.get("price_change_ratio_pct")

        if value is None:
            missing_change_count += 1
        elif _to_finite_number(value) is None:
            invalid_change_count += 1
        else:
            valid_change_count += 1

    missing_ratio_pct = (
        missing_change_count / actual_count * 100
        if actual_count
        else None
    )

    missing_ratio_within_threshold = (
        missing_ratio_pct is not None
        and missing_ratio_pct <= max_missing_ratio_pct
    )

    # 检查股票与指数接口的时间差。
    stock_timestamp = _to_finite_number(
        stock_result.get("api_timestamp_ms")
    )

    index_result_provided = index_result is not None
    index_result_invalid = (
        index_result_provided
        and not isinstance(index_result, dict)
    )

    api_gap_seconds = None

    if isinstance(index_result, dict):
        index_timestamp = _to_finite_number(
            index_result.get("api_timestamp_ms")
        )

        if (
            stock_timestamp is not None
            and index_timestamp is not None
        ):
            api_gap_seconds = (
                abs(stock_timestamp - index_timestamp) / 1000
            )

    if not index_result_provided:
        api_timestamps_comparable = True
        api_gap_within_threshold = True
    elif index_result_invalid:
        api_timestamps_comparable = False
        api_gap_within_threshold = False
    else:
        api_timestamps_comparable = api_gap_seconds is not None
        api_gap_within_threshold = (
            api_gap_seconds is not None
            and api_gap_seconds <= max_api_gap_seconds
        )

    checks = {
        "record_count_matches": count_matches,
        "security_codes_valid": security_codes_valid,
        "no_duplicate_codes": no_duplicate_codes,
        "page_timestamps_valid": page_timestamps_valid,
        "page_timestamps_consistent": timestamps_consistent,
        "page_timestamp_spread_within_threshold": (
            spread_within_threshold
        ),
        "change_values_valid": invalid_change_count == 0,
        "missing_ratio_within_threshold": (
            missing_ratio_within_threshold
        ),
        "api_timestamps_comparable": api_timestamps_comparable,
        "api_gap_within_threshold": api_gap_within_threshold,
    }

    warnings = []

    if not count_matches:
        warnings.append(
            "实际股票记录数与接口报告总数不一致，或接口总数无效。"
        )

    if not security_codes_valid:
        warnings.append(
            "部分记录缺少有效证券代码或记录结构无效。"
        )

    if not no_duplicate_codes:
        warnings.append(
            "股票记录存在重复证券代码或无效证券代码。"
        )

    if not page_timestamps_valid:
        warnings.append(
            "部分分页时间戳缺失或无效，无法确认完整时间范围。"
        )
    elif not timestamps_consistent:
        warnings.append(
            "分页时间戳存在差异，不能确认所有分页属于同一时点。"
        )

    if (
        spread_seconds is not None
        and not spread_within_threshold
    ):
        warnings.append(
            f"分页时间戳跨度为 {spread_seconds:.1f} 秒，"
            f"超过设定阈值 "
            f"{max_page_timestamp_spread_seconds:.1f} 秒。"
        )

    if invalid_change_count:
        warnings.append("存在非空但无效的涨跌幅数值。")

    if missing_ratio_pct is None:
        warnings.append(
            "股票记录为空，无法计算涨跌幅缺失比例。"
        )
    elif not missing_ratio_within_threshold:
        warnings.append(
            f"涨跌幅缺失比例为 {missing_ratio_pct:.2f}%，"
            f"超过设定阈值 {max_missing_ratio_pct:.2f}%。"
        )

    if index_result_invalid:
        warnings.append(
            "指数结果结构无效，无法比较股票与指数接口时间戳。"
        )
    elif (
        isinstance(index_result, dict)
        and api_gap_seconds is None
    ):
        warnings.append(
            "股票或指数接口时间戳缺失或无效，无法比较。"
        )
    elif (
        api_gap_seconds is not None
        and not api_gap_within_threshold
    ):
        warnings.append(
            f"股票与指数接口时间差为 {api_gap_seconds:.1f} 秒，"
            f"超过设定阈值 {max_api_gap_seconds:.1f} 秒。"
        )

    # 基础统计门槛只评估股票快照本身。
    # 不要求分页时间戳完全相同，也不依赖指数接口是否成功。
    descriptive_statistics_ready = all(
        (
            count_matches,
            security_codes_valid,
            no_duplicate_codes,
            page_timestamps_valid,
            spread_within_threshold,
            invalid_change_count == 0,
            missing_ratio_within_threshold,
        )
    )

    # 基础质量门槛：
    # 分页时间戳不完全一致时，只要时间戳有效且跨度在阈值内，
    # 保留警告，但不单独判定基础质量失败。
    # 其他质量检查仍须全部通过。
    basic_quality_passed = all(
        value is True
        for name, value in checks.items()
        if name != "page_timestamps_consistent"
    )

    # 本模块不验证交易日历、真实交易时段等研究适用性条件。
    # 因此不能在这里宣布正式研究准入通过。
    research_ready = False

    return {
        "checks": checks,
        "metrics": {
            "actual_record_count": actual_count,
            "api_reported_total": reported_count,
            "valid_change_count": valid_change_count,
            "missing_change_count": missing_change_count,
            "invalid_change_count": invalid_change_count,
            "missing_ratio_pct": missing_ratio_pct,
            "page_timestamp_spread_seconds": spread_seconds,
            "page_timestamps_consistent": timestamps_consistent,
            "stock_index_api_gap_seconds": api_gap_seconds,
        },
        "warnings": warnings,
        "descriptive_statistics_ready": descriptive_statistics_ready,
        "basic_quality_passed": basic_quality_passed,
        "research_ready": research_ready,
        "market_session_verified": False,
        "market_calendar_verified": False,
        "market_freshness_verified": False,
    }