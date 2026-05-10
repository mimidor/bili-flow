import subprocess
import tempfile
import threading
import time
from pathlib import Path

from app.utils.external_tools import resolve_ffmpeg_bin, run_text_subprocess
from app.utils.logger import get_logger
from config import Config

logger = get_logger("whisper")

try:
    from opencc import OpenCC

    _opencc = OpenCC("t2s")
except Exception:
    _opencc = None

model = None
model_signature: tuple[str, str, str] | None = None
backend_signature: tuple[str, ...] | None = None


def _ensure_faster_whisper_tqdm_compat() -> None:
    """Patch tqdm compatibility for faster-whisper on newer tqdm builds."""
    try:
        import threading as _threading
        from tqdm.auto import tqdm as _tqdm

        if not hasattr(_tqdm, "_lock"):
            _tqdm._lock = _threading.RLock()
        try:
            from faster_whisper import utils as _fw_utils

            if hasattr(_fw_utils, "disabled_tqdm") and not hasattr(_fw_utils.disabled_tqdm, "_lock"):
                _fw_utils.disabled_tqdm._lock = _threading.RLock()
        except Exception:
            pass
    except Exception:
        pass


def _current_asr_provider() -> str:
    return (getattr(Config, "ASR_PROVIDER", "local_whisper") or "local_whisper").strip().lower()


def _is_bailian_provider(provider: str) -> bool:
    return provider in {"aliyun_bailian", "bailian", "aliyun"}


def _current_local_asr_engine() -> str:
    return (getattr(Config, "LOCAL_ASR_ENGINE", "whisper") or "whisper").strip().lower()


def _is_qwen_local_engine(engine: str) -> bool:
    return engine in {"qwen3_asr_0.6b", "qwen3-asr-0.6b", "qwen3_asr", "qwen3-asr"}


def _resolve_whisper_cpp_paths() -> tuple[Path | None, Path | None]:
    cli = Path(Config.WHISPER_CPP_CLI) if Config.WHISPER_CPP_CLI else None
    model_path = Path(Config.WHISPER_CPP_MODEL) if Config.WHISPER_CPP_MODEL else None
    return cli, model_path


def _use_whisper_cpp() -> bool:
    if not Config.USE_WHISPER_CPP:
        return False

    cli, model_path = _resolve_whisper_cpp_paths()
    if not cli or not cli.exists():
        logger.warning("WHISPER_CPP_CLI 配置无效或文件不存在，禁用 whisper.cpp")
        return False
    if not model_path or not model_path.exists():
        logger.warning("WHISPER_CPP_MODEL 配置无效或文件不存在，禁用 whisper.cpp")
        return False
    return True


def _get_whisper_cpp_paths() -> tuple[Path, Path]:
    cli, model_path = _resolve_whisper_cpp_paths()
    if cli is None or not cli.exists():
        raise RuntimeError(f"whisper-cli 不存在: {cli}")
    if model_path is None or not model_path.exists():
        raise RuntimeError(f"whisper 模型不存在: {model_path}")
    return cli, model_path


def _ensure_faster_whisper_model():
    global model, model_signature
    signature = (Config.WHISPER_MODEL, Config.WHISPER_DEVICE, Config.WHISPER_COMPUTE_TYPE)
    if model is not None and model_signature == signature:
        return model

    logger.info("使用 faster-whisper 进行语音识别")
    try:
        _ensure_faster_whisper_tqdm_compat()
        from faster_whisper import WhisperModel

        model = WhisperModel(
            Config.WHISPER_MODEL,
            device=Config.WHISPER_DEVICE,
            compute_type=Config.WHISPER_COMPUTE_TYPE,
            download_root="models",
        )
        model_signature = signature
    except ImportError as exc:
        logger.warning("faster-whisper 未安装")
        model = None
        model_signature = None
        raise RuntimeError("faster-whisper 模型未初始化") from exc
    return model


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
    return f"[{'█' * filled}{'░' * (width - filled)}]"


def _format_transcript_preview(text: str, limit: int = 500) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...（已截断，完整长度 {len(text)} 字）"


def _to_simplified_chinese(text: str) -> str:
    """
    Convert Whisper output to simplified Chinese when OpenCC is available.
    """
    text = (text or "").strip()
    if not text or _opencc is None:
        return text

    try:
        return _opencc.convert(text)
    except Exception:
        return text


def _get_media_duration_seconds(media_path: str) -> float | None:
    """使用 ffprobe 估算媒体时长，失败时返回 None。"""
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


def _run_whisper_cpp_with_progress(cmd: list[str], duration_seconds: float | None = None) -> subprocess.CompletedProcess:
    """
    运行 whisper.cpp，并在执行期间周期性输出进度日志。
    duration_seconds 只是估算值，用于显示进度条和剩余时间。
    """
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    output_lines: list[str] = []

    def _consume_output() -> None:
        assert proc.stdout is not None
        for line in iter(proc.stdout.readline, ""):
            if not line:
                break
            output_lines.append(line)
            stripped = line.strip()
            if stripped:
                logger.info("%s", stripped)

    reader = threading.Thread(target=_consume_output, daemon=True)
    reader.start()

    start = time.monotonic()
    last_progress_log = 0.0

    while proc.poll() is None:
        elapsed = time.monotonic() - start
        if elapsed - last_progress_log >= 5:
            last_progress_log = elapsed
            if duration_seconds and duration_seconds > 0:
                percent = min(99, int(elapsed / duration_seconds * 100))
                bar = _render_progress_bar(percent)
                eta = max(0, duration_seconds - elapsed)
                logger.info(
                    "[识别进度] %s %d%% | 已用时 %s | 预计剩余 %s",
                    bar,
                    percent,
                    _format_duration(elapsed),
                    _format_duration(eta),
                )
            else:
                logger.info("[识别进度] 正在识别... 已用时 %s", _format_duration(elapsed))
        time.sleep(1)

    returncode = proc.wait()
    reader.join(timeout=5)

    return subprocess.CompletedProcess(
        args=cmd,
        returncode=returncode,
        stdout="".join(output_lines),
        stderr="",
    )


def transcribe_audio(audio_path: str) -> str:
    """
    使用 Whisper 进行语音识别。

    支持视频文件输入（自动提取音频）。
    """
    logger.info("Whisper 识别: %s", audio_path)
    logger.info("识别中，请稍候。长音频会周期性输出进度。")

    video_extensions = [".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm"]
    input_path = Path(audio_path)
    provider = _current_asr_provider()
    local_engine = _current_local_asr_engine()
    use_whisper_cpp = False

    if _is_bailian_provider(provider):
        logger.info("使用阿里百炼 ASR 进行语音识别")
        from app.modules.bailian_asr import transcribe_audio as transcribe_audio_bailian

        if input_path.suffix.lower() in video_extensions:
            logger.debug("检测到视频文件，先提取音频再上传百炼...")
            from app.modules.downloader import extract_audio_from_video

            temp_audio = extract_audio_from_video(str(input_path))
            logger.debug("临时音频文件: %s", temp_audio)
            try:
                return transcribe_audio_bailian(temp_audio)
            finally:
                try:
                    Path(temp_audio).unlink()
                    logger.debug("已清理临时音频文件")
                except Exception:
                    pass
        return transcribe_audio_bailian(audio_path)

    if _is_qwen_local_engine(local_engine):
        logger.info("使用 Qwen3-ASR-0.6B 进行本地语音识别")
        from app.modules.qwen3_asr_local import transcribe_audio as transcribe_audio_qwen3

        if input_path.suffix.lower() in video_extensions:
            logger.debug("检测到视频文件，先提取音频...")
            from app.modules.downloader import extract_audio_from_video

            temp_audio = extract_audio_from_video(str(input_path))
            logger.debug("临时音频文件: %s", temp_audio)
            try:
                return transcribe_audio_qwen3(temp_audio)
            finally:
                try:
                    Path(temp_audio).unlink()
                    logger.debug("已清理临时音频文件")
                except Exception:
                    pass
        return transcribe_audio_qwen3(audio_path)

    use_whisper_cpp = _use_whisper_cpp()

    if use_whisper_cpp:
        cli_path, model_path = _get_whisper_cpp_paths()
        logger.info("使用 whisper.cpp 进行语音识别")
        logger.info("  CLI: %s", cli_path)
        logger.info("  Model: %s", model_path)
    else:
        logger.info("使用 faster-whisper 进行语音识别")

    if input_path.suffix.lower() in video_extensions:
        logger.debug("检测到视频文件，先提取音频...")
        from app.modules.downloader import extract_audio_from_video

        temp_audio = extract_audio_from_video(str(input_path))
        logger.debug("临时音频文件: %s", temp_audio)

        try:
            if use_whisper_cpp:
                result = _transcribe_with_cpp(temp_audio)
            else:
                result = _transcribe_with_faster_whisper(temp_audio)
        finally:
            try:
                Path(temp_audio).unlink()
                logger.debug("已清理临时音频文件")
            except Exception:
                pass
        return result

    if use_whisper_cpp:
        return _transcribe_with_cpp(audio_path)
    return _transcribe_with_faster_whisper(audio_path)


def _transcribe_with_cpp(audio_path: str) -> str:
    """使用 whisper.cpp 进行识别。"""
    whisper_cpp_cli, whisper_cpp_model = _get_whisper_cpp_paths()

    input_path = Path(audio_path)
    temp_wav = None

    if input_path.suffix.lower() != ".wav":
        logger.debug("音频不是 wav 格式，使用 ffmpeg 转换: %s", input_path.suffix)
        with tempfile.NamedTemporaryFile(prefix="whisper_input_", suffix=".wav", delete=False) as f:
            temp_wav = Path(f.name)

        ffmpeg_bin = resolve_ffmpeg_bin()
        ffmpeg_exe = str((ffmpeg_bin / "ffmpeg.exe") if ffmpeg_bin else "ffmpeg")
        ffmpeg_cmd = [
            ffmpeg_exe,
            "-y",
            "-i",
            str(input_path),
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(temp_wav),
        ]
        logger.debug("执行 ffmpeg 转换: %s", " ".join(ffmpeg_cmd))
        ffmpeg_proc = run_text_subprocess(ffmpeg_cmd)
        if ffmpeg_proc.returncode != 0:
            logger.error("ffmpeg 转换失败: %s", ffmpeg_proc.stderr)
            raise RuntimeError(f"ffmpeg 转换失败: {ffmpeg_proc.stderr}")

        input_for_whisper = str(temp_wav)
    else:
        input_for_whisper = str(input_path)

    duration_seconds = _get_media_duration_seconds(input_for_whisper)
    if duration_seconds and duration_seconds > 0:
        logger.info("whisper.cpp 识别开始，音频时长约 %s", _format_duration(duration_seconds))
    else:
        logger.info("whisper.cpp 识别开始，无法估算时长，将按运行时输出进度")

    with tempfile.NamedTemporaryFile(prefix="whisper_out_", suffix="", delete=False) as f:
        output_prefix = f.name

    try:
        cmd = [
            str(whisper_cpp_cli),
            "-m",
            str(whisper_cpp_model),
            "-f",
            input_for_whisper,
            "-l",
            "zh",
            "--print-progress",
            "--output-txt",
            "--output-file",
            output_prefix,
        ]

        logger.debug("执行命令: %s", " ".join(cmd))
        proc = _run_whisper_cpp_with_progress(cmd, duration_seconds)

        if proc.returncode != 0:
            logger.error("whisper.cpp 失败: %s", proc.stderr)
            raise RuntimeError(f"whisper.cpp 识别失败: {proc.stderr}")

        output_file = Path(f"{output_prefix}.txt")
        if output_file.exists():
            text = output_file.read_text("utf-8").strip()
            try:
                output_file.unlink()
            except Exception:
                pass
        else:
            text = proc.stdout.strip()

        text = _to_simplified_chinese(text)

        if duration_seconds and duration_seconds > 0:
            logger.info("whisper.cpp 完成，音频时长约 %s，文本长度 %d", _format_duration(duration_seconds), len(text))
        else:
            logger.info("whisper.cpp 完成，文本长度 %d", len(text))
        if text:
            logger.info("whisper.cpp 识别结果: %s", _format_transcript_preview(text))
            logger.debug("whisper.cpp 完整识别结果: %s", text)
        return text
    finally:
        try:
            Path(output_prefix).unlink(missing_ok=True)
            Path(f"{output_prefix}.txt").unlink(missing_ok=True)
            if temp_wav:
                temp_wav.unlink(missing_ok=True)
        except Exception:
            pass


def _transcribe_with_faster_whisper(audio_path: str) -> str:
    """使用 faster-whisper 进行识别。"""
    _ensure_faster_whisper_tqdm_compat()
    current_model = _ensure_faster_whisper_model()

    logger.info("faster-whisper 识别开始，处理中请稍候")
    start = time.monotonic()
    segments, _ = current_model.transcribe(
        audio_path,
        language="zh",
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=True,
        log_progress=Config.WHISPER_LOG_PROGRESS,
    )
    text = "\n".join([segment.text for segment in segments])
    text = _to_simplified_chinese(text)
    logger.info("faster-whisper 完成，耗时 %s，文本长度 %d", _format_duration(time.monotonic() - start), len(text))
    if text:
        logger.info("faster-whisper 识别结果: %s", _format_transcript_preview(text))
        logger.debug("faster-whisper 完整识别结果: %s", text)
    return text
