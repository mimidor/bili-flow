from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from app.utils.external_tools import resolve_ffmpeg_bin, run_text_subprocess
from app.utils.logger import get_logger
from config import Config

logger = get_logger("qwen3_asr")

try:
    from opencc import OpenCC

    _opencc = OpenCC("t2s")
except Exception:
    _opencc = None

_model: Any | None = None
_model_signature: tuple[str, ...] | None = None
_model_lock = threading.RLock()


def _normalize_model_source() -> str:
    source = (Config.QWEN3_ASR_MODEL_SOURCE or "modelscope").strip().lower()
    if source not in {"modelscope", "huggingface"}:
        logger.warning("未知的 Qwen3-ASR 下载源 %s，回退到 modelscope", source)
        return "modelscope"
    return source


def _model_id() -> str:
    return (Config.QWEN3_ASR_MODEL_ID or "Qwen/Qwen3-ASR-0.6B").strip() or "Qwen/Qwen3-ASR-0.6B"


def _model_dir() -> Path:
    configured = (Config.QWEN3_ASR_MODEL_DIR or "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path("models") / "Qwen3-ASR-0.6B"


def _hf_endpoint() -> str:
    return (Config.QWEN3_ASR_HF_ENDPOINT or "").strip()


def _is_model_ready(model_dir: Path) -> bool:
    return (model_dir / "config.json").exists()


def _download_from_modelscope(model_id: str, model_dir: Path) -> Path:
    try:
        from modelscope import snapshot_download
    except ImportError as exc:
        raise RuntimeError("缺少 modelscope 依赖，无法下载 Qwen3-ASR-0.6B") from exc

    downloaded_path = snapshot_download(model_id, local_dir=str(model_dir))
    return Path(downloaded_path)


def _download_from_huggingface(model_id: str, model_dir: Path) -> Path:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError("缺少 huggingface_hub 依赖，无法下载 Qwen3-ASR-0.6B") from exc

    kwargs: dict[str, Any] = {
        "repo_id": model_id,
        "local_dir": str(model_dir),
    }
    endpoint = _hf_endpoint()
    if endpoint:
        kwargs["endpoint"] = endpoint
    downloaded_path = snapshot_download(**kwargs)
    return Path(downloaded_path)


def _ensure_model_downloaded() -> Path:
    model_dir = _model_dir()
    if _is_model_ready(model_dir):
        return model_dir

    source = _normalize_model_source()
    model_id = _model_id()
    model_dir.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Qwen3-ASR-0.6B 本地模型不存在，开始下载: source=%s model=%s dir=%s",
        source,
        model_id,
        model_dir,
    )

    if source == "huggingface":
        downloaded_path = _download_from_huggingface(model_id, model_dir)
    else:
        downloaded_path = _download_from_modelscope(model_id, model_dir)

    candidate_dirs = [model_dir, downloaded_path]
    for candidate in candidate_dirs:
        if _is_model_ready(candidate):
            logger.info("Qwen3-ASR-0.6B 下载完成: %s", candidate)
            return candidate

    raise RuntimeError(f"Qwen3-ASR-0.6B 下载完成但模型目录无效: {downloaded_path}")


def _resolve_runtime() -> tuple[Any, str, Any]:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("缺少 torch 依赖，无法加载 Qwen3-ASR-0.6B") from exc

    desired_device = (Config.WHISPER_DEVICE or "cpu").strip().lower()
    if desired_device == "cuda":
        if torch.cuda.is_available():
            return torch, "cuda:0", torch.float16
        logger.warning("WHISPER_DEVICE=cuda 但 CUDA 不可用，Qwen3-ASR-0.6B 回退到 CPU")

    return torch, "cpu", torch.float32


def _build_model_signature(model_path: Path, device: str, dtype: Any) -> tuple[str, ...]:
    return (
        str(model_path.resolve()),
        _normalize_model_source(),
        _model_id(),
        _hf_endpoint(),
        device,
        str(dtype),
    )


def _ensure_qwen3_asr_model():
    global _model, _model_signature

    model_path = _ensure_model_downloaded()
    torch, device, dtype = _resolve_runtime()
    signature = _build_model_signature(model_path, device, dtype)
    if _model is not None and _model_signature == signature:
        return _model

    with _model_lock:
        if _model is not None and _model_signature == signature:
            return _model

        try:
            from qwen_asr import Qwen3ASRModel
        except ImportError as exc:
            raise RuntimeError("缺少 qwen-asr 依赖，无法加载 Qwen3-ASR-0.6B") from exc

        logger.info("加载 Qwen3-ASR-0.6B: dir=%s device=%s", model_path, device)
        wrapper = Qwen3ASRModel.from_pretrained(
            str(model_path),
            torch_dtype=dtype,
            max_inference_batch_size=1,
        )
        wrapper.model.to(device)
        wrapper.model.eval()

        _model = wrapper
        _model_signature = signature
        return _model


def _extract_transcript_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        for key in ("text", "transcript", "transcription", "content"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""
    if isinstance(result, (list, tuple)):
        parts = [_extract_transcript_text(item) for item in result]
        return "\n".join(part for part in parts if part)

    text = getattr(result, "text", None)
    if isinstance(text, str):
        return text.strip()

    return ""


def _to_simplified_chinese(text: str) -> str:
    text = (text or "").strip()
    if not text or _opencc is None:
        return text

    try:
        return _opencc.convert(text)
    except Exception:
        return text


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _render_progress_bar(percent: int, width: int = 24) -> str:
    percent = max(0, min(100, int(percent)))
    filled = min(width, max(0, round(width * percent / 100)))
    return f"[{'#' * filled}{'-' * (width - filled)}]"


def _get_media_duration_seconds(media_path: str) -> float | None:
    ffmpeg_bin = resolve_ffmpeg_bin()
    ffprobe = None
    if ffmpeg_bin:
        candidate = ffmpeg_bin / "ffprobe.exe"
        if candidate.exists():
            ffprobe = candidate

    if not ffprobe:
        return None

    cmd = [
        str(ffprobe),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        media_path,
    ]
    proc = run_text_subprocess(cmd)
    if proc.returncode != 0:
        return None

    try:
        return float(proc.stdout.strip())
    except (TypeError, ValueError):
        return None


def _log_progress(stop_event: threading.Event, start: float, duration_seconds: float | None) -> None:
    last_logged = 0.0
    while not stop_event.wait(timeout=1):
        elapsed = time.monotonic() - start
        if elapsed - last_logged < 5:
            continue

        last_logged = elapsed
        if duration_seconds and duration_seconds > 0:
            percent = min(99, int(elapsed / duration_seconds * 100))
            bar = _render_progress_bar(percent)
            eta = max(0.0, duration_seconds - elapsed)
            logger.info(
                "[Qwen3-ASR progress] %s %d%% | elapsed %s | est. remaining %s",
                bar,
                percent,
                _format_duration(elapsed),
                _format_duration(eta),
            )
            continue

        logger.info("[Qwen3-ASR progress] running | elapsed %s", _format_duration(elapsed))


def transcribe_audio(audio_path: str) -> str:
    current_model = _ensure_qwen3_asr_model()

    duration_seconds = _get_media_duration_seconds(audio_path)
    if duration_seconds and duration_seconds > 0:
        logger.info(
            "Qwen3-ASR-0.6B 识别开始，音频时长约 %s，处理中请稍候",
            _format_duration(duration_seconds),
        )
    else:
        logger.info("Qwen3-ASR-0.6B 识别开始，处理中请稍候")

    start = time.monotonic()
    stop_event = threading.Event()
    progress_thread = threading.Thread(
        target=_log_progress,
        args=(stop_event, start, duration_seconds),
        daemon=True,
        name="qwen3-asr-progress",
    )
    progress_thread.start()

    try:
        result = current_model.transcribe(audio=audio_path, language="Chinese")
        text = _to_simplified_chinese(_extract_transcript_text(result))
    finally:
        stop_event.set()
        progress_thread.join(timeout=1)

    logger.info(
        "Qwen3-ASR-0.6B 完成，耗时 %s，文本长度 %d",
        _format_duration(time.monotonic() - start),
        len(text),
    )
    return text
