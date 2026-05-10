from __future__ import annotations

from types import SimpleNamespace

import app.modules.processor as processor


class _FakeResponse:
    def __init__(self, content: str, finish_reason: str):
        self.choices = [
            SimpleNamespace(
                message=SimpleNamespace(content=content),
                finish_reason=finish_reason,
            )
        ]


class _FakeCompletions:
    def __init__(self, responses: list[_FakeResponse]):
        self._responses = responses
        self.calls: list[list[dict[str, str]]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs["messages"])
        if not self._responses:
            raise AssertionError("No more fake responses configured")
        return self._responses.pop(0)


class _FakeClient:
    def __init__(self, responses: list[_FakeResponse]):
        self.chat = SimpleNamespace(completions=_FakeCompletions(responses))


def test_process_text_continues_when_response_is_truncated(monkeypatch):
    fake_client = _FakeClient(
        [
            _FakeResponse('{"summary":"第一段",', "length"),
            _FakeResponse(
                '{"summary":"完整摘要","details":"## 标题\\n内容","key_points":["要点1"],'
                '"stocks":["宁德时代","新能源车板块","创业板指"],"insights":"洞察"}',
                "stop",
            ),
        ]
    )

    monkeypatch.setattr(processor.Config, "OPENAI_API_KEY", "sk-test", raising=False)
    monkeypatch.setattr(processor, "client", fake_client)

    result = processor.process_text("原始文本", "测试标题", 0)

    assert result["success"] is True
    assert result["summary"] == "完整摘要"
    assert result["details"] == "## 标题\n内容"
    assert result["stocks"] == ["宁德时代", "新能源车板块", "创业板指"]
    assert len(fake_client.chat.completions.calls) == 2
    assert processor.LLM_CONTINUE_PROMPT in fake_client.chat.completions.calls[1][-1]["content"]


def test_process_text_falls_back_when_continuation_still_invalid(monkeypatch):
    fake_client = _FakeClient(
        [
            _FakeResponse('{"summary":"第一段",', "length"),
            _FakeResponse("继续但仍然不完整", "length"),
            _FakeResponse("还是不完整", "length"),
        ]
    )

    monkeypatch.setattr(processor.Config, "OPENAI_API_KEY", "sk-test", raising=False)
    monkeypatch.setattr(processor, "client", fake_client)
    monkeypatch.setattr(
        processor,
        "_process_local",
        lambda raw_text, video_title, duration: {
            "corrected_text": raw_text,
            "summary": "local-summary",
            "details": "",
            "key_points": [],
            "stocks": [],
            "tags": [],
            "insights": "local-insights",
            "success": False,
        },
    )

    result = processor.process_text("原始文本", "测试标题", 0)

    assert result["success"] is False
    assert result["summary"] == "local-summary"
    assert result["insights"] == "local-insights"
    assert len(fake_client.chat.completions.calls) == 3
