from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional

from config import Config
from app.utils.runtime_home import get_install_root


def _iter_existing_paths(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        resolved = path.expanduser()
        key = str(resolved).lower()
        if key in seen or not resolved.exists():
            continue
        seen.add(key)
        result.append(resolved)
    return result


def resolve_cuda_dll_dirs() -> list[Path]:
    """
    Resolve directories that contain CUDA runtime DLLs packaged with the venv.

    On Windows, packages such as nvidia-cublas-cu12 and nvidia-cudnn-cu12 ship the
    DLLs inside site-packages/nvidia/*/bin. These directories must be added to
    the DLL search path for faster-whisper / ctranslate2 to load successfully.
    """
    candidate_dirs: list[Path] = []

    try:
        import importlib.util

        for module_name in ("nvidia.cublas", "nvidia.cudnn", "nvidia.cuda_runtime", "nvidia.cuda_nvrtc"):
            spec = importlib.util.find_spec(module_name)
            if not spec or not spec.submodule_search_locations:
                continue
            for location in spec.submodule_search_locations:
                base = Path(location)
                candidate_dirs.append(base / "bin")
    except Exception:
        pass

    # Fallback to the active environment's site-packages layout.
    env_root = Path(sys.prefix)
    candidate_dirs.extend(
        [
            env_root / "Lib" / "site-packages" / "nvidia" / "cublas" / "bin",
            env_root / "Lib" / "site-packages" / "nvidia" / "cudnn" / "bin",
            env_root / "Lib" / "site-packages" / "nvidia" / "cuda_runtime" / "bin",
            env_root / "Lib" / "site-packages" / "nvidia" / "cuda_nvrtc" / "bin",
        ]
    )

    return _iter_existing_paths(candidate_dirs)


def ensure_runtime_dll_dirs_loaded() -> list[Path]:
    """
    Add CUDA runtime DLL directories to the process search path on Windows.
    """
    if os.name != "nt":
        return []

    dll_dirs = resolve_cuda_dll_dirs()
    if not dll_dirs:
        return []

    existing_path = os.environ.get("PATH", "")
    path_parts = [part for part in existing_path.split(os.pathsep) if part]

    for dll_dir in dll_dirs:
        dll_dir_str = str(dll_dir)
        if dll_dir_str not in path_parts:
            path_parts.insert(0, dll_dir_str)
        try:
            os.add_dll_directory(dll_dir_str)
        except (AttributeError, FileNotFoundError, OSError):
            pass

    os.environ["PATH"] = os.pathsep.join(path_parts)
    return dll_dirs


def resolve_ffmpeg_bin() -> Optional[Path]:
    """
    Resolve the directory that contains ffmpeg.exe and ffprobe.exe.

    Priority:
    1. FFMPEG_LOCATION env/config override
    2. current PATH via shutil.which
    3. common WinGet package locations
    """
    configured = getattr(Config, "FFMPEG_LOCATION", "") or os.getenv("FFMPEG_LOCATION", "")
    if configured:
        configured_path = Path(configured).expanduser()
        if configured_path.is_file():
            return configured_path.parent
        if configured_path.is_dir():
            return configured_path

    install_root = get_install_root()
    packaged_tools_roots = [
        install_root / "tools",
        install_root.parent / "tools",
    ]
    for packaged_tools_root in packaged_tools_roots:
        for candidate in (
            packaged_tools_root / "ffmpeg",
            packaged_tools_root / "ffmpeg" / "bin",
            packaged_tools_root,
        ):
            if (candidate / "ffmpeg.exe").exists() or (candidate / "ffprobe.exe").exists():
                return candidate

    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return Path(ffmpeg_path).resolve().parent

    candidate_root = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
    if candidate_root.exists():
        for ffmpeg_exe in candidate_root.glob("Gyan.FFmpeg*/*/bin/ffmpeg.exe"):
            return ffmpeg_exe.resolve().parent
        for ffmpeg_exe in candidate_root.rglob("ffmpeg.exe"):
            if "Gyan.FFmpeg" in str(ffmpeg_exe):
                return ffmpeg_exe.resolve().parent

    return None


def resolve_ytdlp_executable() -> Optional[Path]:
    """
    Resolve the yt-dlp executable path.

    Priority:
    1. active virtual environment Scripts directory
    2. install root / packaged tools
    3. current PATH via shutil.which
    """
    env_root = Path(sys.prefix)
    candidate_paths = _iter_existing_paths(
        [
            env_root / "Scripts" / "yt-dlp.exe",
            env_root / "bin" / "yt-dlp",
            get_install_root() / "tools" / "yt-dlp.exe",
            get_install_root().parent / "tools" / "yt-dlp.exe",
        ]
    )
    for candidate in candidate_paths:
        if candidate.is_file():
            return candidate

    ytdlp_path = shutil.which("yt-dlp.exe") or shutil.which("yt-dlp")
    if ytdlp_path:
        return Path(ytdlp_path).resolve()

    return None


def run_text_subprocess(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """
    Run a subprocess with UTF-8 decoding and replacement for invalid bytes.
    """
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    kwargs.setdefault("encoding", "utf-8")
    kwargs.setdefault("errors", "replace")
    return subprocess.run(cmd, **kwargs)


# Load packaged CUDA runtime DLLs early so importing GPU-backed libraries works
# without requiring the user to manually edit PATH.
ensure_runtime_dll_dirs_loaded()
