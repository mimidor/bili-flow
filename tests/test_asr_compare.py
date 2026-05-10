"""
Integration comparison test for local Whisper vs Alibaba Bailian ASR.

This test is intentionally skipped unless:
- a target audio file is available, and
- the required ASR credentials/config are present.
"""

from __future__ import annotations

import importlib
import os
import time
from pathlib import Path

import pytest


TARGET_AUDIO_HINT = "20260413_BV1ngDdBDEqd"


def _resolve_compare_audio_path() -> Path | None:
    env_path = os.getenv("ASR_COMPARE_AUDIO_PATH", "").strip()
    if env_path:
        candidate = Path(env_path)
        if candidate.is_file():
            return candidate

    search_roots = [
        Path("data"),
        Path("."),
    ]

    for root in search_roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if TARGET_AUDIO_HINT not in str(path):
                continue
            if path.suffix.lower() not in {".m4a", ".mp3", ".wav"}:
                continue
            return path

    return None


def _run_local_whisper(audio_path: str) -> tuple[str, float]:
    # Force the local provider so the module loads faster-whisper.
    os.environ["ASR_PROVIDER"] = "local_whisper"

    import config as config_module
    import app.modules.whisper_ai as whisper_module

    importlib.reload(config_module)
    whisper_module = importlib.reload(whisper_module)

    start = time.perf_counter()
    text = whisper_module.transcribe_audio(audio_path)
    elapsed = time.perf_counter() - start
    return text, elapsed


def _run_bailian_asr(audio_path: str) -> tuple[str, float]:
    # Force the Bailian provider so the module routes through OSS + DashScope.
    os.environ["ASR_PROVIDER"] = "aliyun_bailian"

    import config as config_module
    import app.modules.whisper_ai as whisper_module

    importlib.reload(config_module)
    whisper_module = importlib.reload(whisper_module)

    start = time.perf_counter()
    text = whisper_module.transcribe_audio(audio_path)
    elapsed = time.perf_counter() - start
    return text, elapsed


@pytest.mark.integration
def test_compare_whisper_vs_bailian_asr():
    """
    Compare runtime of local Whisper and Alibaba Bailian ASR on the same audio.

    This is a manual integration benchmark. It skips when the audio file or
    required credentials are missing.
    """
    audio_path = _resolve_compare_audio_path()
    if not audio_path:
        pytest.skip(
            "Compare audio not found. Set ASR_COMPARE_AUDIO_PATH or place the file under data/. "
            f"Looked for a file containing: {TARGET_AUDIO_HINT}"
        )

    # Bailian requires OSS + DashScope credentials.
    required_env = [
        "DASHSCOPE_API_KEY",
        "ALIYUN_OSS_ENDPOINT",
        "ALIYUN_OSS_BUCKET",
        "ALIYUN_OSS_ACCESS_KEY_ID",
        "ALIYUN_OSS_ACCESS_KEY_SECRET",
    ]
    missing = [name for name in required_env if not os.getenv(name, "").strip()]
    if missing:
        pytest.skip(f"Missing Bailian ASR config: {', '.join(missing)}")

    whisper_text, whisper_seconds = _run_local_whisper(str(audio_path))
    bailian_text, bailian_seconds = _run_bailian_asr(str(audio_path))

    print("\n=== ASR comparison ===")
    print(f"Audio: {audio_path}")
    print(f"Whisper time: {whisper_seconds:.2f}s, chars: {len(whisper_text)}")
    print(f"Bailian time: {bailian_seconds:.2f}s, chars: {len(bailian_text)}")
    print("\n--- Whisper preview ---")
    print(whisper_text[:500])
    print("\n--- Bailian preview ---")
    print(bailian_text[:500])

    assert isinstance(whisper_text, str)
    assert isinstance(bailian_text, str)
    assert whisper_text.strip() or bailian_text.strip()
