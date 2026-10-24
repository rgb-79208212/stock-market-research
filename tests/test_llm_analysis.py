import pytest

from src.llm_analysis import (
    LLMAnalysisError,
    generate_llm_interpretation,
)


def _fresh_report(**overrides):
    """构造通过基础质量门禁和行情新鲜度门禁的测试报告。"""
    report = {
        "research_ready": True,
        "facts": [],
        "evidence_quality": {
            "basic_quality_gate": "passed",
            "market_freshness_verified": True,
        },
    }
    report.update(overrides)
    return report


def test_rejects_non_dict_report():
    with pytest.raises(LLMAnalysisError, match="格式错误"):
        generate_llm_interpretation([])


def test_rejects_report_blocked_by_quality_gate(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "test-model")

    with pytest.raises(LLMAnalysisError, match="质量门禁"):
        generate_llm_interpretation(
            {"research_ready": False},
            load_env_file=False,
        )

def test_rejects_report_without_quality_gate(monkeypatch):
    import src.llm_analysis as llm

    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "test-model")

    def unexpected_client_call(**kwargs):
        raise AssertionError("质量门禁失败时不应初始化模型客户端")

    monkeypatch.setattr(llm, "OpenAI", unexpected_client_call)

    with pytest.raises(LLMAnalysisError, match="质量门禁"):
        generate_llm_interpretation(
            {"facts": []},
            load_env_file=False,
        )


@pytest.mark.parametrize("value", ["true", 1, 0, None])
def test_rejects_non_boolean_quality_gate(monkeypatch, value):
    import src.llm_analysis as llm

    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "test-model")

    def unexpected_client_call(**kwargs):
        raise AssertionError("质量门禁失败时不应初始化模型客户端")

    monkeypatch.setattr(llm, "OpenAI", unexpected_client_call)

    with pytest.raises(LLMAnalysisError, match="质量门禁"):
        generate_llm_interpretation(
            {"research_ready": value, "facts": []},
            load_env_file=False,
        )

def test_rejects_report_without_verified_freshness(monkeypatch):
    import src.llm_analysis as llm

    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "test-model")

    def unexpected_client_call(**kwargs):
        raise AssertionError("行情新鲜度未通过时不应初始化模型客户端")

    monkeypatch.setattr(llm, "OpenAI", unexpected_client_call)

    with pytest.raises(LLMAnalysisError, match="新鲜度"):
        generate_llm_interpretation(
            {
                "research_ready": True,
                "facts": [],
                "evidence_quality": {
                    "basic_quality_gate": "passed",
                    "market_freshness_verified": False,
                },
            },
            load_env_file=False,
        )


def test_requires_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_MODEL", "test-model")

    with pytest.raises(LLMAnalysisError, match="DEEPSEEK_API_KEY"):
        generate_llm_interpretation(
            _fresh_report(),
            load_env_file=False,
        )


def test_requires_model_name(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

    with pytest.raises(LLMAnalysisError, match="DEEPSEEK_MODEL"):
        generate_llm_interpretation(
            _fresh_report(),
            load_env_file=False,
        )


def test_successful_call_uses_report_and_system_prompt(monkeypatch):
    import json
    from types import SimpleNamespace

    import src.llm_analysis as llm

    report = {
        "research_ready": True,
        "facts": ["上涨占比为 55%"],
        "status": "时段适用性未确认",
        "current_snapshot_applicability_confirmed": False,
        "reasons": ["官方交易日历尚未验证"],
        "limitations": ["仅允许进行受限的快照描述"],
        "evidence_quality": {
            "basic_quality_gate": "passed",
            "market_session_verified": False,
            "independent_source_verified": False,
            "historically_validated": False,
            "market_freshness_verified": True,
        },
    }

    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="基于现有证据的研究解读。")
                    )
                ],
                created=1790000000,
                usage=None,
            )

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.chat = SimpleNamespace(
                completions=FakeCompletions()
            )

    monkeypatch.setattr(llm, "OpenAI", FakeClient)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "test-model")
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)

    result = llm.generate_llm_interpretation(
        report,
        load_env_file=False,
    )

    assert result["success"] is True
    assert result["provider"] == "DeepSeek"
    assert result["model"] == "test-model"
    assert result["content"] == "基于现有证据的研究解读。"
    assert result["generated_at"] == 1790000000
    assert result["usage"] is None

    messages = captured["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == llm.SYSTEM_PROMPT

    assert messages[1]["role"] == "user"
    assert json.dumps(report, ensure_ascii=False) in messages[1]["content"]

    assert captured["stream"] is False
    assert captured["temperature"] == 0.2

    assert "暂定、非正式解读" in llm.SYSTEM_PROMPT
    assert "不得表述为已确认的当前市场状态" in llm.SYSTEM_PROMPT
    assert (
            json.dumps(report, ensure_ascii=False)
            in messages[1]["content"]
    )


def test_api_failure_is_wrapped_without_exposing_error_details(monkeypatch):
    import src.llm_analysis as llm

    class FakeCompletions:
        def create(self, **kwargs):
            raise RuntimeError("sensitive-request-detail")

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = type(
                "FakeChat",
                (),
                {"completions": FakeCompletions()},
            )()

    monkeypatch.setattr(llm, "OpenAI", FakeClient)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "test-model")

    with pytest.raises(LLMAnalysisError, match="DeepSeek 调用失败") as exc_info:
        llm.generate_llm_interpretation(
            _fresh_report(),
            load_env_file=False,
        )

    assert "sensitive-request-detail" not in str(exc_info.value)



def test_rejects_empty_model_response(monkeypatch):
    import src.llm_analysis as llm

    class FakeCompletions:
        def create(self, **kwargs):
            return type(
                "FakeResponse",
                (),
                {
                    "choices": [
                        type(
                            "FakeChoice",
                            (),
                            {
                                "message": type(
                                    "FakeMessage",
                                    (),
                                    {"content": "   "},
                                )()
                            },
                        )()
                    ],
                    "created": 1790000000,
                    "usage": None,
                },
            )()

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = type(
                "FakeChat",
                (),
                {
                    "completions": FakeCompletions(),
                },
            )()

    monkeypatch.setattr(llm, "OpenAI", FakeClient)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "test-model")

    with pytest.raises(LLMAnalysisError, match="模型返回了空内容"):
        llm.generate_llm_interpretation(
            _fresh_report(),
            load_env_file=False,
        )
