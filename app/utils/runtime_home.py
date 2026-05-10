from __future__ import annotations

import os
import sys
from pathlib import Path


def get_source_root() -> Path:
    return Path(__file__).resolve().parents[2]


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_install_root() -> Path:
    if is_frozen() and getattr(sys, "executable", None):
        return Path(sys.executable).resolve().parent
    return get_source_root()


def get_runtime_home() -> Path:
    configured = (os.getenv("BILI_FLOW_HOME") or os.getenv("BILI_AUTO_HOME") or "").strip()
    if configured:
        return Path(configured).expanduser()

    if is_frozen():
        local_app_data = (os.getenv("LOCALAPPDATA") or "").strip()
        if local_app_data:
            return Path(local_app_data).expanduser() / "bili-flow"
        return Path.home() / "AppData" / "Local" / "bili-flow"

    return get_source_root()


def get_env_path() -> Path:
    return get_runtime_home() / ".env"


def get_data_dir() -> Path:
    return get_runtime_home() / "data"


def get_logs_dir() -> Path:
    return get_runtime_home() / "logs"


def get_models_dir() -> Path:
    return get_runtime_home() / "models"


def get_lock_dir() -> Path:
    return get_runtime_home() / ".runtime" / "locks"
