from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.utils.llm_client import (
    LLMCallResult,
    build_openai_client,
    _extract_text_from_response,
    resolve_temperature,
    test_llm_connection_config as run_llm_connection_config_test,
    test_llm_connection as run_llm_connection_test,
)


class _FakeQuery:
    def __init__(self, row):
        self._row = row

    def filter_by(self, **kwargs):
        return self

    def first(self):
        return self._row


class _FakeSession:
    def __init__(self, row):
        self._row = row
        self.closed = False

    def query(self, _model):
        return _FakeQuery(self._row)

    def close(self):
        self.closed = True


def test_llm_connection_uses_short_probe_and_disables_web_search():
    profile = SimpleNamespace(
        id=1,
        provider="openai-compatible",
        base_url="https://example.com/v1",
        api_key="test-key",
        model_name="demo-model",
        enable_web_search=True,
        enable_reasoning=True,
        enable_image=True,
        enable_tools=True,
    )
    session = _FakeSession(profile)
    captured: dict[str, object] = {}

    def fake_call_llm(probe_profile, messages, **kwargs):
        captured["profile"] = probe_profile
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return LLMCallResult(response=SimpleNamespace(output_text="OK"))

    with patch("app.utils.llm_client.SessionLocal", return_value=session):
        with patch("app.utils.llm_client.call_llm", side_effect=fake_call_llm):
            result = run_llm_connection_test(1)

    assert result["success"] is True
    assert "Connected successfully" in result["message"]
    assert result["prompt_text"] == "Reply with one short sentence.\nReply OK if the model is reachable."
    assert result["response_text"] == "OK"
    assert result["web_search_mode"] == "disabled"
    assert result["web_search_used"] is False
    assert captured["kwargs"]["max_tokens"] == 16
    assert captured["kwargs"]["timeout"] == 12
    assert captured["profile"].enable_web_search is False
    assert captured["profile"].enable_reasoning is False
    assert captured["profile"].enable_image is False
    assert captured["profile"].enable_tools is False
    assert captured["messages"] == [
        {"role": "system", "content": "Reply with one short sentence."},
        {"role": "user", "content": "Reply OK if the model is reachable."},
    ]


def test_llm_connection_config_works_without_db_row():
    profile = SimpleNamespace(
        provider="kimi",
        base_url="https://api.moonshot.cn/v1",
        api_key="test-key",
        model_name="kimi-k2.6",
        enable_web_search=False,
        enable_reasoning=False,
        enable_image=False,
        enable_tools=False,
        name="Kimi test",
    )

    captured: dict[str, object] = {}

    def fake_call_llm(probe_profile, messages, **kwargs):
        captured["profile"] = probe_profile
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return LLMCallResult(response=SimpleNamespace(output_text="OK"))

    with patch("app.utils.llm_client.call_llm", side_effect=fake_call_llm):
        result = run_llm_connection_config_test(profile)

    assert result["success"] is True
    assert result["response_text"] == "OK"
    assert captured["profile"].provider == "kimi"
    assert captured["profile"].model_name == "kimi-k2.6"


def test_build_openai_client_normalizes_misconfigured_chat_completions_base_url():
    profile = SimpleNamespace(
        api_key="test-key",
        base_url="https://api.moonshot.cn/v1/chat/completions",
    )

    captured: dict[str, object] = {}

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    with patch("app.utils.llm_client.OpenAI", _FakeOpenAI):
        client = build_openai_client(profile)

    assert client is not None
    assert captured["base_url"] == "https://api.moonshot.cn/v1"


def test_resolve_temperature_for_kimi_forces_one():
    profile = SimpleNamespace(
        provider="kimi",
        base_url="https://api.moonshot.cn/v1",
        model_name="kimi-k2.6",
    )

    assert resolve_temperature(profile, 0.3) == 1.0
    assert resolve_temperature(profile, 1.0) == 1.0


def test_extract_text_from_response_supports_content_parts():
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=[
                        {"type": "text", "text": "OK"},
                        {"type": "text", "text": "reachable"},
                    ]
                )
            )
        ]
    )

    assert _extract_text_from_response(response) == "OK\nreachable"


def test_extract_text_from_response_falls_back_to_reasoning_content():
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=None,
                    reasoning_content="Model is reachable.",
                )
            )
        ]
    )

    assert _extract_text_from_response(response) == "Model is reachable."
