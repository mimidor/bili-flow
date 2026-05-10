from __future__ import annotations

from threading import Event, Lock, Thread
from types import SimpleNamespace

import app.modules.processor as processor


def test_process_text_merges_multiple_effective_models(monkeypatch):
    profile_a = SimpleNamespace(id=1, name="Model A", provider="openai-compatible", model_name="model-a")
    profile_b = SimpleNamespace(id=2, name="Model B", provider="openai-compatible", model_name="model-b")

    monkeypatch.setattr(processor, "get_llm_profiles", lambda use_case_key: (None, [profile_a, profile_b]))
    monkeypatch.setattr(
        processor,
        "_resolve_process_prompt_text",
        lambda **kwargs: "system prompt",
    )

    outputs = {
        "model-a": {
            "profile": profile_a,
            "provider_name": "openai-compatible",
            "model_name": "model-a",
            "error_message": None,
            "result": {
                "corrected_text": "raw transcript",
                "summary": "summary a",
                "details": "details a",
                "key_points": ["point a"],
                "stocks": ["AAPL"],
                "tags": ["tech"],
                "insights": "insight a",
                "success": True,
            },
        },
        "model-b": {
            "profile": profile_b,
            "provider_name": "openai-compatible",
            "model_name": "model-b",
            "error_message": None,
            "result": {
                "corrected_text": "raw transcript",
                "summary": "summary b",
                "details": "details b",
                "key_points": ["point b"],
                "stocks": ["MSFT"],
                "tags": ["cloud"],
                "insights": "insight b",
                "success": True,
            },
        },
    }

    def fake_process_text_with_profile(**kwargs):
        return outputs[kwargs["profile"].model_name]

    monkeypatch.setattr(processor, "_process_text_with_profile", fake_process_text_with_profile)

    result = processor.process_text(
        raw_text="raw transcript",
        video_title="Demo",
        duration=0,
        content_type="video",
        content_id="BV1",
        uploader_name="Uploader",
    )

    assert result["success"] is True
    assert "Model A (model-a): summary a" in result["summary"]
    assert "Model B (model-b): summary b" in result["summary"]
    assert "## Model A (model-a)" in result["details"]
    assert "details a" in result["details"]
    assert "## Model B (model-b)" in result["details"]
    assert "details b" in result["details"]
    assert result["key_points"] == ["point a", "point b"]
    assert result["stocks"] == ["AAPL", "MSFT"]
    assert len(result["model_outputs"]) == 2
    assert result["active_models"] == ["model-a", "model-b"]


def test_process_text_keeps_single_model_shape(monkeypatch):
    profile = SimpleNamespace(id=1, name="Single", provider="openai-compatible", model_name="single-model")
    expected = {
        "profile": profile,
        "provider_name": "openai-compatible",
        "model_name": "single-model",
        "error_message": None,
        "result": {
            "corrected_text": "raw transcript",
            "summary": "single summary",
            "details": "single details",
            "key_points": ["point"],
            "stocks": ["AAPL"],
            "tags": ["tech"],
            "insights": "single insight",
            "success": True,
        },
    }

    monkeypatch.setattr(processor, "get_llm_profiles", lambda use_case_key: (None, [profile]))
    monkeypatch.setattr(processor, "_resolve_process_prompt_text", lambda **kwargs: "system prompt")
    monkeypatch.setattr(processor, "_process_text_with_profile", lambda **kwargs: expected)

    result = processor.process_text("raw transcript", "Demo", 0)

    assert result == expected["result"]


def test_process_text_runs_multiple_models_in_parallel(monkeypatch):
    profile_a = SimpleNamespace(id=1, name="Model A", provider="openai-compatible", model_name="model-a")
    profile_b = SimpleNamespace(id=2, name="Model B", provider="openai-compatible", model_name="model-b")

    monkeypatch.setattr(processor, "get_llm_profiles", lambda use_case_key: (None, [profile_a, profile_b]))
    monkeypatch.setattr(processor, "_resolve_process_prompt_text", lambda **kwargs: "system prompt")

    started = []
    started_lock = Lock()
    both_started = Event()
    release = Event()

    outputs = {
        "model-a": {
            "profile": profile_a,
            "provider_name": "openai-compatible",
            "model_name": "model-a",
            "error_message": None,
            "result": {
                "corrected_text": "raw transcript",
                "summary": "summary a",
                "details": "details a",
                "key_points": ["point a"],
                "stocks": ["AAPL"],
                "tags": ["tech"],
                "insights": "insight a",
                "success": True,
            },
        },
        "model-b": {
            "profile": profile_b,
            "provider_name": "openai-compatible",
            "model_name": "model-b",
            "error_message": None,
            "result": {
                "corrected_text": "raw transcript",
                "summary": "summary b",
                "details": "details b",
                "key_points": ["point b"],
                "stocks": ["MSFT"],
                "tags": ["cloud"],
                "insights": "insight b",
                "success": True,
            },
        },
    }

    def fake_process_text_with_profile(**kwargs):
        model_name = kwargs["profile"].model_name
        with started_lock:
            started.append(model_name)
            if len(started) == 2:
                both_started.set()
        assert release.wait(timeout=1), "parallel workers did not start in time"
        return outputs[model_name]

    monkeypatch.setattr(processor, "_process_text_with_profile", fake_process_text_with_profile)

    result_holder = {}
    error_holder = {}

    def run_process():
        try:
            result_holder["result"] = processor.process_text(
                raw_text="raw transcript",
                video_title="Demo",
                duration=0,
                content_type="video",
                content_id="BV1",
                uploader_name="Uploader",
            )
        except Exception as exc:  # pragma: no cover - test helper
            error_holder["error"] = exc

    worker = Thread(target=run_process)
    worker.start()

    assert both_started.wait(timeout=1), "expected both model calls to start in parallel"
    release.set()
    worker.join(timeout=1)

    assert not error_holder
    assert "result" in result_holder
    assert result_holder["result"]["success"] is True
    assert started == ["model-a", "model-b"]
