from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from app.utils.runtime_home import get_data_dir, get_env_path, get_models_dir

ENV_PATH = get_env_path()
_ENV_LOCK = threading.RLock()
_ENV_MTIME: float | None = None


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.expanduser().resolve().as_posix()}"


@dataclass(frozen=True)
class ConfigSpec:
    default: Any
    kind: str = "str"


CONFIG_SPECS: dict[str, ConfigSpec] = {
    "BILIBILI_COOKIE": ConfigSpec(""),
    "refresh_token": ConfigSpec(""),
    "ADMIN_AUTH_USERNAME": ConfigSpec(""),
    "ADMIN_AUTH_PASSWORD": ConfigSpec(""),
    "ADMIN_AUTH_SECRET": ConfigSpec(""),
    "OPENAI_API_KEY": ConfigSpec(""),
    "OPENAI_BASE_URL": ConfigSpec(""),
    "OPENAI_MODEL": ConfigSpec(""),
    "LLM_INPUT_TOKEN_PRICE_PER_MILLION": ConfigSpec(2, "int"),
    "LLM_OUTPUT_TOKEN_PRICE_PER_MILLION": ConfigSpec(12, "int"),
    "FEISHU_WEBHOOK": ConfigSpec(""),
    "FEISHU_APP_ID": ConfigSpec(""),
    "FEISHU_APP_SECRET": ConfigSpec(""),
    "FEISHU_RECEIVE_ID": ConfigSpec(""),
    "FEISHU_RECEIVE_ID_TYPE": ConfigSpec("chat_id"),
    "FEISHU_DOCS_ENABLED": ConfigSpec(False, "bool"),
    "FEISHU_DOCS_FOLDER_TOKEN": ConfigSpec(""),
    "FEISHU_DOCS_SPACE_ID": ConfigSpec(""),
    "DATABASE_SOURCE": ConfigSpec("sqlite"),
    "DATABASE_URL": ConfigSpec(_sqlite_url(get_data_dir() / "bili.db")),
    "SQLITE_DATABASE_URL": ConfigSpec(_sqlite_url(get_data_dir() / "bili.db")),
    "POSTGRESQL_DATABASE_URL": ConfigSpec(""),
    "LOG_LEVEL": ConfigSpec("INFO"),
    "FFMPEG_LOCATION": ConfigSpec(""),
    "ASR_PROVIDER": ConfigSpec("local_whisper"),
    "DASHSCOPE_API_KEY": ConfigSpec(""),
    "DASHSCOPE_ASR_BASE_URL": ConfigSpec("https://dashscope.aliyuncs.com/api/v1"),
    "ALIYUN_BAILIAN_ASR_MODEL": ConfigSpec("qwen3-asr-flash-filetrans"),
    "ALIYUN_BAILIAN_ASR_CHANNEL_ID": ConfigSpec(0, "int"),
    "ALIYUN_BAILIAN_ASR_ENABLE_ITN": ConfigSpec(False, "bool"),
    "ALIYUN_BAILIAN_ASR_ENABLE_WORDS": ConfigSpec(True, "bool"),
    "ALIYUN_BAILIAN_ASR_POLL_INTERVAL": ConfigSpec(2, "int"),
    "ALIYUN_OSS_ENDPOINT": ConfigSpec(""),
    "ALIYUN_OSS_BUCKET": ConfigSpec(""),
    "ALIYUN_OSS_ACCESS_KEY_ID": ConfigSpec(""),
    "ALIYUN_OSS_ACCESS_KEY_SECRET": ConfigSpec(""),
    "ALIYUN_OSS_PREFIX": ConfigSpec("bili-flow/asr"),
    "ALIYUN_OSS_URL_EXPIRE_SECONDS": ConfigSpec(3600, "int"),
    "ALIYUN_OSS_CLEANUP": ConfigSpec(True, "bool"),
    "XYZ_BASE_URL": ConfigSpec(""),
    "XYZ_DEVICE_ID": ConfigSpec(""),
    "XYZ_ACCESS_TOKEN": ConfigSpec(""),
    "XYZ_REFRESH_TOKEN": ConfigSpec(""),
    "XYZ_CHECK_INTERVAL": ConfigSpec(10, "int"),
    "XYZ_BOOTSTRAP_RECENT_EPISODES": ConfigSpec(3, "int"),
    "XYZ_MAX_PAGES_PER_POLL": ConfigSpec(5, "int"),
    "WEWE_RSS_BASE_URL": ConfigSpec(""),
    "WEWE_RSS_AUTH_CODE": ConfigSpec(""),
    "WEWE_RSS_CHECK_INTERVAL": ConfigSpec(10, "int"),
    "VIDEO_CHECK_INTERVAL": ConfigSpec(10, "int"),
    "DYNAMIC_CHECK_INTERVAL": ConfigSpec(5, "int"),
    "LOCAL_VIDEO_SCAN_DIRS": ConfigSpec(""),
    "LOCAL_VIDEO_SCAN_INTERVAL": ConfigSpec(0, "int"),
    "LOCAL_VIDEO_SCAN_PUSH_TARGET_ID": ConfigSpec(0, "int"),
    "SILENT_MODE_START": ConfigSpec(""),  # 静音开始时间，格式 HH:MM，空字符串表示不启用
    "SILENT_MODE_END": ConfigSpec(""),  # 静音结束时间，格式 HH:MM
    "WHISPER_MODEL": ConfigSpec("medium"),
    "WHISPER_DEVICE": ConfigSpec("cpu"),
    "WHISPER_COMPUTE_TYPE": ConfigSpec("float16"),
    "WHISPER_LOG_PROGRESS": ConfigSpec(True, "bool"),
    "USE_WHISPER_CPP": ConfigSpec(False, "bool"),
    "WHISPER_CPP_CLI": ConfigSpec(""),
    "WHISPER_CPP_MODEL": ConfigSpec(""),
    "LOCAL_ASR_ENGINE": ConfigSpec("whisper"),
    "QWEN3_ASR_MODEL_SOURCE": ConfigSpec("modelscope"),
    "QWEN3_ASR_MODEL_ID": ConfigSpec("Qwen/Qwen3-ASR-0.6B"),
    "QWEN3_ASR_MODEL_DIR": ConfigSpec(str(get_models_dir() / "Qwen3-ASR-0.6B")),
    "QWEN3_ASR_HF_ENDPOINT": ConfigSpec("https://hf-mirror.com"),
    "QTEASY_API_URL": ConfigSpec(""),
}


def _load_env_file(force: bool = False) -> None:
    global _ENV_MTIME
    with _ENV_LOCK:
        mtime = ENV_PATH.stat().st_mtime if ENV_PATH.exists() else None
        env_changed = force or mtime != _ENV_MTIME

        if env_changed:
            if ENV_PATH.exists():
                load_dotenv(dotenv_path=ENV_PATH, override=True)
            else:
                load_dotenv(override=True)
            _ENV_MTIME = mtime

        try:
            from app.utils.runtime_config import project_database_url_from_env

            # Choose the database first from env/source-specific URLs, then read
            # runtime_config overrides from that selected database.
            project_database_url_from_env()
        except Exception:
            pass

        try:
            from app.utils.runtime_config import (
                load_runtime_config_overrides,
                runtime_config_overrides_loaded,
            )

            if env_changed or not runtime_config_overrides_loaded():
                load_runtime_config_overrides()
        except Exception:
            # Configuration table is optional during bootstrap / tests.
            pass
        try:
            from app.utils.runtime_config import project_database_url_from_env

            project_database_url_from_env()
        except Exception:
            pass


def refresh_runtime_env(force: bool = False) -> None:
    """Reload .env into the current process if the file changed."""
    _load_env_file(force=force)


def _to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _to_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _convert_value(value: Any, spec: ConfigSpec) -> Any:
    if spec.kind == "bool":
        return _to_bool(value, bool(spec.default))
    if spec.kind == "int":
        return _to_int(value, int(spec.default))
    return "" if value is None else str(value)


def _stringify_value(value: Any, spec: ConfigSpec) -> str:
    if spec.kind == "bool":
        return "true" if _to_bool(value, bool(spec.default)) else "false"
    if spec.kind == "int":
        return str(_to_int(value, int(spec.default)))
    if value is None:
        return ""
    return str(value)


def _persist_env_updates(updates: dict[str, Any]) -> None:
    with _ENV_LOCK:
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
        line_pattern = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=.*$")
        line_index: dict[str, int] = {}
        for index, line in enumerate(lines):
            match = line_pattern.match(line)
            if match:
                line_index[match.group(1)] = index

        for key, value in updates.items():
            spec = CONFIG_SPECS[key]
            rendered = f"{key}={_stringify_value(value, spec)}"
            if key in line_index:
                lines[line_index[key]] = rendered
            else:
                lines.append(rendered)

        if not ENV_PATH.parent.exists():
            ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
        ENV_PATH.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
        global _ENV_MTIME
        _ENV_MTIME = ENV_PATH.stat().st_mtime if ENV_PATH.exists() else None


class ConfigMeta(type):
    def __getattribute__(cls, name: str) -> Any:
        if name in CONFIG_SPECS:
            _load_env_file()
            spec = CONFIG_SPECS[name]
            raw = os.getenv(name)
            if raw is None or raw == "":
                return spec.default
            value = _convert_value(raw, spec)
            if name == "BILIBILI_COOKIE" and isinstance(value, str):
                return value.strip()
            return value
        return super().__getattribute__(name)

    def __setattr__(cls, name: str, value: Any) -> None:
        if name in CONFIG_SPECS:
            if name == "BILIBILI_COOKIE" and isinstance(value, str):
                value = value.strip()
            os.environ[name] = _stringify_value(value, CONFIG_SPECS[name])
            try:
                _persist_env_updates({name: value})
            except Exception:
                pass
            return
        super().__setattr__(name, value)


class Config(metaclass=ConfigMeta):
    @classmethod
    def refresh(cls, force: bool = False) -> None:
        refresh_runtime_env(force=force)
