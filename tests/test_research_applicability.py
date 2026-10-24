
from src.research_applicability import assess_research_applicability



def make_session(
    status="工作日常规连续交易时段（未核验节假日）",
    within_regular_session=True,
):
    return {
        "status": status,
        "within_regular_session": within_regular_session,
    }


def test_failed_quality_gate_blocks_research():
    result = assess_research_applicability(
        basic_quality_gate="failed",
        stock_session=make_session(),
        index_session=make_session(),
    )

    assert result["status"] == "不可用于正式状态研判"
    assert result["snapshot_statistics_allowed"] is False
    assert result["current_snapshot_applicability_confirmed"] is False


def test_unverified_calendar_keeps_applicability_unconfirmed():
    result = assess_research_applicability(
        basic_quality_gate="passed",
        stock_session=make_session(),
        index_session=make_session(),
    )

    assert result["status"] == "时段适用性未确认"
    assert result["snapshot_statistics_allowed"] is True
    assert result["current_snapshot_applicability_confirmed"] is False
    assert any("官方交易日历" in reason for reason in result["reasons"])


def test_weekend_session_keeps_applicability_unconfirmed():
    result = assess_research_applicability(
        basic_quality_gate="passed",
        stock_session=make_session(
            status="周末（非交易日）",
            within_regular_session=False,
        ),
        index_session=make_session(
            status="周末（非交易日）",
            within_regular_session=False,
        ),
    )

    assert result["status"] == "时段适用性未确认"
    assert result["snapshot_statistics_allowed"] is True
    assert result["current_snapshot_applicability_confirmed"] is False


def test_missing_session_information_keeps_applicability_unconfirmed():
    result = assess_research_applicability(
        basic_quality_gate="passed",
        stock_session=None,
        index_session=make_session(),
    )

    assert result["status"] == "时段适用性未确认"
    assert result["current_snapshot_applicability_confirmed"] is False
    assert any("股票接口" in reason for reason in result["reasons"])


def test_verified_conditions_allow_confirmation():
    result = assess_research_applicability(
        basic_quality_gate="passed",
        stock_session=make_session(),
        index_session=make_session(),
        market_calendar_verified=True,
        market_session_verified=True,
        market_freshness_verified=True,
    )

    assert result["status"] == "当前快照时点条件已验证"
    assert result["snapshot_statistics_allowed"] is True
    assert result["current_snapshot_applicability_confirmed"] is True


def test_verification_flags_require_explicit_true():
    session = {
        "status": "工作日常规连续交易时段（未核验节假日）",
        "within_regular_session": True,
    }

    result = assess_research_applicability(
        basic_quality_gate="passed",
        stock_session=session,
        index_session=session,
        market_calendar_verified="false",
        market_session_verified="false",
        market_freshness_verified="false",
    )

    assert result["current_snapshot_applicability_confirmed"] is False
    assert result["status"] == "时段适用性未确认"
    assert len(result["reasons"]) == 3