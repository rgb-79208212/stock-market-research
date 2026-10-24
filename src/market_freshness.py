"""Assess snapshot timestamp freshness without claiming live market validity."""

import math


def _finite_timestamp_ms(value):
    """Return a valid positive millisecond timestamp, or None."""
    if value is None or isinstance(value, bool):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None

    if not math.isfinite(number) or number <= 0:
        return None

    return number


def assess_market_freshness(
    timestamp_ms,
    *,
    now_ms,
    max_age_seconds=120.0,
    max_future_skew_seconds=0.0,
):
    """Assess timestamp age relative to an explicitly supplied clock.

    This checks timestamp freshness only. It does not verify the timestamp
    semantics, official trading calendar, or actual quote freshness.
    """
    for name, value in (
        ("max_age_seconds", max_age_seconds),
        ("max_future_skew_seconds", max_future_skew_seconds),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError(f"{name} must be a finite non-negative number")

    timestamp = _finite_timestamp_ms(timestamp_ms)
    now = _finite_timestamp_ms(now_ms)

    if timestamp is None:
        return {
            "verified": False,
            "status": "invalid_or_missing_timestamp",
            "age_seconds": None,
            "max_age_seconds": float(max_age_seconds),
        }

    if now is None:
        return {
            "verified": False,
            "status": "invalid_reference_time",
            "age_seconds": None,
            "max_age_seconds": float(max_age_seconds),
        }

    age_seconds = (now - timestamp) / 1000.0

    if age_seconds < -max_future_skew_seconds:
        status = "future_timestamp"
        verified = False
    elif age_seconds > max_age_seconds:
        status = "stale_timestamp"
        verified = False
    else:
        status = "within_configured_age"
        verified = True

    return {
        "verified": verified,
        "status": status,
        "age_seconds": age_seconds,
        "max_age_seconds": float(max_age_seconds),
    }


def assess_snapshot_freshness(
    stock_result,
    index_result,
    *,
    now_ms,
    max_age_seconds=120.0,
    max_future_skew_seconds=0.0,
):
    """Assess stock and index timestamps independently and together."""
    stock_timestamp = (
        stock_result.get("api_timestamp_ms")
        if isinstance(stock_result, dict)
        else None
    )
    index_timestamp = (
        index_result.get("api_timestamp_ms")
        if isinstance(index_result, dict)
        else None
    )

    stock = assess_market_freshness(
        stock_timestamp,
        now_ms=now_ms,
        max_age_seconds=max_age_seconds,
        max_future_skew_seconds=max_future_skew_seconds,
    )
    index = assess_market_freshness(
        index_timestamp,
        now_ms=now_ms,
        max_age_seconds=max_age_seconds,
        max_future_skew_seconds=max_future_skew_seconds,
    )

    return {
        "verified": stock["verified"] is True and index["verified"] is True,
        "stock": stock,
        "index": index,
        "max_age_seconds": float(max_age_seconds),
        "limitations": [
            "Timestamp age does not prove the provider timestamp represents "
            "the actual quote-generation time.",
            "Timestamp freshness does not verify the official trading calendar "
            "or prove that quotes are live.",
        ],
    }
