from __future__ import annotations

import importlib
import os
import time
from pathlib import Path

import pytest
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _find_first_transcript() -> Path | None:
    data_root = PROJECT_ROOT / "data" / "uploaders"
    if not data_root.exists():
        return None

    transcripts = sorted(
        path for path in data_root.rglob("transcript.txt") if path.is_file()
    )
    return transcripts[0] if transcripts else None


def _reload_processor_module():
    load_dotenv(PROJECT_ROOT / ".env", override=True)

    import config as config_module
    import app.modules.processor as processor_module

    importlib.reload(config_module)
    return importlib.reload(processor_module)


@pytest.mark.integration
def test_real_llm_process_text():
    load_dotenv(PROJECT_ROOT / ".env", override=True)

    transcript_path = _find_first_transcript()
    if not transcript_path:
        pytest.skip("No transcript.txt found under data/uploaders")

    if not os.getenv("OPENAI_API_KEY", "").strip():
        pytest.skip("Missing OPENAI_API_KEY in .env")

    raw_text = transcript_path.read_text(encoding="utf-8").strip()
    if not raw_text:
        pytest.skip(f"Empty transcript file: {transcript_path}")

    processor = _reload_processor_module()
    video_title = transcript_path.parent.name

    start = time.perf_counter()
    result = processor.process_text(
        raw_text=raw_text,
        video_title=video_title,
        duration=0,
    )
    elapsed = time.perf_counter() - start

    print("\n=== LLM integration ===")
    print(f"Transcript: {transcript_path}")
    print(f"Title: {video_title}")
    print(f"Time: {elapsed:.2f}s")
    print(f"Success: {result.get('success')}")
    print(f"Summary: {result.get('summary', '')[:300]}")
    print(f"Details length: {len(result.get('details', ''))}")

    assert isinstance(result, dict)
    assert result.get("success") is True
    assert result.get("summary", "").strip() or result.get("details", "").strip()
