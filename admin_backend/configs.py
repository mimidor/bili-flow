from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from config import Config, ENV_PATH, refresh_runtime_env
from app.models.database import PushTarget, create_session
from app.utils.runtime_config import upsert_runtime_config_values

ValueType = Literal["string", "password", "bool", "int", "select", "push_target_select"]


@dataclass(frozen=True)
class EnvConfigField:
    key: str
    label: str
    group: str
    value_type: ValueType = "string"
    description: str = ""
    editable: bool = True
    secret: bool = False
    restart_required: bool = False
    options: tuple[str, ...] = ()


ENV_CONFIG_FIELDS: tuple[EnvConfigField, ...] = (
    EnvConfigField("BILIBILI_COOKIE", "B站 Cookie", "账号与鉴权", "password", "浏览视频、抓取动态、下载音频时使用", secret=True),
    EnvConfigField("refresh_token", "刷新令牌", "账号与鉴权", "password", "用于自动刷新 B 站 Cookie", secret=True),
    EnvConfigField("ADMIN_AUTH_SECRET", "后台会话密钥", "账号与鉴权", "password", "用于签名登录 cookie", secret=True),
    EnvConfigField("LLM_INPUT_TOKEN_PRICE_PER_MILLION", "LLM 输入 Token 单价", "LLM 成本", "int", "单位：元 / 百万 token"),
    EnvConfigField("LLM_OUTPUT_TOKEN_PRICE_PER_MILLION", "LLM 输出 Token 单价", "LLM 成本", "int", "单位：元 / 百万 token"),
    EnvConfigField("FEISHU_WEBHOOK", "飞书 Webhook", "飞书推送", "password", "保留兼容配置", secret=True),
    EnvConfigField("FEISHU_APP_ID", "飞书应用 ID", "飞书推送", "password", "飞书开放平台应用凭证", secret=True),
    EnvConfigField("FEISHU_APP_SECRET", "飞书应用密钥", "飞书推送", "password", "飞书开放平台应用凭证", secret=True),
    EnvConfigField("FEISHU_RECEIVE_ID", "飞书接收目标", "飞书推送", "string", "迁移兼容字段，仅用于初始化默认推送组或旧链路兜底"),
    EnvConfigField(
        "FEISHU_RECEIVE_ID_TYPE",
        "飞书接收类型",
        "飞书推送",
        "select",
        "迁移兼容字段，仅用于初始化默认推送组或旧链路兜底",
        options=("chat_id", "open_id", "user_id"),
    ),
    EnvConfigField("FEISHU_DOCS_ENABLED", "飞书文档上传", "飞书文档", "bool", "是否上传总结 Markdown 到飞书云盘"),
    EnvConfigField("FEISHU_DOCS_FOLDER_TOKEN", "飞书文档文件夹令牌", "飞书文档", "string", "总结文档上传到哪个文件夹"),
    EnvConfigField("FEISHU_DOCS_SPACE_ID", "飞书知识空间 ID", "飞书文档", "string", "预留字段，当前版本暂未使用"),
    EnvConfigField("DATABASE_SOURCE", "数据库数据源", "系统", "select", "当前生效的数据源", options=("sqlite", "postgresql")),
    EnvConfigField("SQLITE_DATABASE_URL", "SQLite 数据库地址", "系统", "string", "SQLite 连接串"),
    EnvConfigField("POSTGRESQL_DATABASE_URL", "PostgreSQL 数据库地址", "系统", "string", "PostgreSQL 连接串"),
    EnvConfigField("DATABASE_URL", "当前数据库地址", "系统", "string", "当前生效的数据库连接串", editable=False, restart_required=True),
    EnvConfigField("LOG_LEVEL", "日志级别", "系统", "select", "控制日志输出级别", options=("DEBUG", "INFO", "WARNING", "ERROR")),
    EnvConfigField("FFMPEG_LOCATION", "FFmpeg 路径", "工具", "string", "手动指定 ffmpeg 目录"),
    EnvConfigField("ASR_PROVIDER", "语音识别来源", "语音识别", "select", "本地 Whisper 或阿里百炼", options=("local_whisper", "aliyun_bailian")),
    EnvConfigField("DASHSCOPE_API_KEY", "百炼 API Key", "语音识别", "password", "阿里百炼 ASR 使用", secret=True),
    EnvConfigField("ALIYUN_OSS_ENDPOINT", "OSS Endpoint", "语音识别", "string", "百炼 ASR 上传临时音频时使用"),
    EnvConfigField("ALIYUN_OSS_BUCKET", "OSS Bucket", "语音识别", "string", "百炼 ASR 上传临时音频时使用"),
    EnvConfigField("ALIYUN_OSS_ACCESS_KEY_ID", "OSS AccessKey ID", "语音识别", "password", "OSS 上传凭证", secret=True),
    EnvConfigField("ALIYUN_OSS_ACCESS_KEY_SECRET", "OSS AccessKey Secret", "语音识别", "password", "OSS 上传凭证", secret=True),
    EnvConfigField("ALIYUN_OSS_PREFIX", "OSS 前缀", "语音识别", "string", "临时音频对象前缀"),
    EnvConfigField("XYZ_BASE_URL", "小宇宙接口地址", "小宇宙", "string", "xyz 服务的基础接口地址", restart_required=True),
    EnvConfigField("XYZ_DEVICE_ID", "小宇宙设备ID", "小宇宙", "string", "调用 xyz / xiaoyuzhou 接口所需的设备标识", restart_required=True),
    EnvConfigField("XYZ_ACCESS_TOKEN", "小宇宙访问令牌", "小宇宙", "password", "调用 xyz 服务时使用", secret=True, restart_required=True),
    EnvConfigField("XYZ_REFRESH_TOKEN", "小宇宙刷新令牌", "小宇宙", "password", "调用 xyz 服务时使用的刷新令牌", secret=True, restart_required=True),
    EnvConfigField("XYZ_CHECK_INTERVAL", "小宇宙检测间隔(分钟)", "调度", "int", "0 表示关闭小宇宙检测"),
    EnvConfigField("XYZ_BOOTSTRAP_RECENT_EPISODES", "小宇宙首次同步集数", "调度", "int", "首次订阅时最多同步最近几集"),
    EnvConfigField("XYZ_MAX_PAGES_PER_POLL", "小宇宙单次翻页上限", "调度", "int", "发现新单集时最多翻多少页"),
    EnvConfigField("WEWE_RSS_BASE_URL", "WeWe RSS 基地址", "公众号订阅", "string", "例如 http://wewe-rss-host:4000"),
    EnvConfigField("WEWE_RSS_AUTH_CODE", "WeWe RSS 授权码", "公众号订阅", "password", "仅管理接口可能需要；公开订阅消费不需要", secret=True, restart_required=True),
    EnvConfigField("WEWE_RSS_CHECK_INTERVAL", "公众号检测间隔(分钟)", "调度", "int", "0 表示关闭公众号检测"),
    EnvConfigField("VIDEO_CHECK_INTERVAL", "视频检测间隔(分钟)", "调度", "int", "0 表示关闭视频检测"),
    EnvConfigField("DYNAMIC_CHECK_INTERVAL", "动态检测间隔(分钟)", "调度", "int", "0 表示关闭动态检测"),
    EnvConfigField("LOCAL_VIDEO_SCAN_DIRS", "本地视频扫描目录", "调度", "string", "用分号分隔多个绝对路径；会递归扫描子目录中的 .flv 文件"),
    EnvConfigField("LOCAL_VIDEO_SCAN_INTERVAL", "本地视频扫描间隔(分钟)", "调度", "int", "0 表示关闭本地 .flv 扫描"),
    EnvConfigField(
        "LOCAL_VIDEO_SCAN_PUSH_TARGET_ID",
        "本地视频固定推送群",
        "调度",
        "push_target_select",
        "扫描到新的本地 .flv 后统一推送到这个飞书群",
    ),
    EnvConfigField("WHISPER_MODEL", "Whisper 模型", "本地识别", "string", "本地 faster-whisper 使用的模型"),
    EnvConfigField("WHISPER_DEVICE", "Whisper 设备", "本地识别", "select", "cpu 或 cuda", options=("cpu", "cuda")),
    EnvConfigField("WHISPER_LOG_PROGRESS", "Whisper 显示进度", "本地识别", "bool", "是否打印识别进度"),
    EnvConfigField("USE_WHISPER_CPP", "启用 whisper.cpp", "本地识别", "bool", "是否优先使用 whisper.cpp"),
    EnvConfigField("WHISPER_CPP_CLI", "whisper.cpp CLI 路径", "本地识别", "string", "whisper.cpp 可执行文件路径"),
    EnvConfigField("WHISPER_CPP_MODEL", "whisper.cpp 模型路径", "本地识别", "string", "whisper.cpp 模型文件路径"),
    EnvConfigField(
        "LOCAL_ASR_ENGINE",
        "本地 ASR 引擎",
        "本地识别",
        "select",
        "默认使用 Whisper，可切换到 Qwen3-ASR-0.6B",
        options=("whisper", "qwen3_asr_0.6b"),
    ),
    EnvConfigField(
        "QWEN3_ASR_MODEL_SOURCE",
        "Qwen3-ASR 下载源",
        "本地识别",
        "select",
        "ModelScope 或 Hugging Face 镜像站",
        options=("modelscope", "huggingface"),
    ),
    EnvConfigField(
        "QWEN3_ASR_MODEL_ID",
        "Qwen3-ASR 模型 ID",
        "本地识别",
        "string",
        "默认官方仓库 Qwen/Qwen3-ASR-0.6B",
    ),
    EnvConfigField(
        "QWEN3_ASR_MODEL_DIR",
        "Qwen3-ASR 本地目录",
        "本地识别",
        "string",
        "首次使用时会自动下载到该目录",
    ),
    EnvConfigField(
        "QWEN3_ASR_HF_ENDPOINT",
        "Hugging Face 镜像地址",
        "本地识别",
        "string",
        "仅在下载源选择 huggingface 时使用，例如 https://hf-mirror.com",
    ),
    EnvConfigField("QTEASY_API_URL", "量化回测 API 地址", "量化回测", "string", "Qteasy FastAPI 基础地址，需包含协议头，例如 http://127.0.0.1:8001"),
)

ENV_CONFIG_KEYS = {field.key for field in ENV_CONFIG_FIELDS}

DATABASE_SOURCE_KEYS = {"DATABASE_SOURCE", "SQLITE_DATABASE_URL", "POSTGRESQL_DATABASE_URL"}


def _normalize_database_updates(updates: dict[str, Any]) -> dict[str, Any]:
    if not updates:
        return updates

    normalized = dict(updates)
    if not (DATABASE_SOURCE_KEYS & normalized.keys()):
        return normalized

    source = str(normalized.get("DATABASE_SOURCE", getattr(Config, "DATABASE_SOURCE", "sqlite")) or "sqlite").strip().lower()
    if source not in {"sqlite", "postgresql"}:
        raise ValueError("DATABASE_SOURCE must be either sqlite or postgresql")

    sqlite_url = normalized.get("SQLITE_DATABASE_URL", getattr(Config, "SQLITE_DATABASE_URL", "sqlite:///data/bili.db"))
    postgres_url = normalized.get("POSTGRESQL_DATABASE_URL", getattr(Config, "POSTGRESQL_DATABASE_URL", ""))

    if source == "postgresql":
        active_url = postgres_url
    else:
        active_url = sqlite_url

    if not active_url:
        raise ValueError("Selected database source does not have a usable DATABASE_URL")

    normalized["DATABASE_SOURCE"] = source
    normalized["DATABASE_URL"] = active_url
    return normalized


def _format_env_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    text = str(value)
    if text == "":
        return ""

    safe_pattern = re.compile(r"^[A-Za-z0-9_./:@,;+\-]+$")
    if safe_pattern.fullmatch(text):
        return text
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _parse_existing_lines() -> list[str]:
    if not ENV_PATH.exists():
        return []
    return ENV_PATH.read_text(encoding="utf-8").splitlines()


def _apply_env_updates(updates: dict[str, Any], *, refresh: bool = True) -> None:
    lines = _parse_existing_lines()
    line_index: dict[str, int] = {}
    line_pattern = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=.*$")

    for index, line in enumerate(lines):
        match = line_pattern.match(line)
        if match:
            line_index[match.group(1)] = index

    updated_keys: set[str] = set()
    for key, value in updates.items():
        formatted_value = _format_env_value(value)
        rendered = f"{key}={formatted_value}"
        if key in line_index:
            lines[line_index[key]] = rendered
        else:
            lines.append(rendered)
        updated_keys.add(key)

    if not ENV_PATH.parent.exists():
        ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    ENV_PATH.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    if refresh:
        refresh_runtime_env(force=True)


def _serialize_value(field: EnvConfigField) -> Any:
    value = getattr(Config, field.key)
    return value


def _load_feishu_push_target_options() -> list[dict[str, Any]]:
    db = create_session(
        sqlite_timeout_seconds=3,
        pool_timeout_seconds=3,
        sqlite_busy_timeout_ms=3000,
    )
    try:
        rows = (
            db.query(PushTarget)
            .filter(PushTarget.channel == "feishu", PushTarget.is_active.is_(True))
            .order_by(PushTarget.is_default.desc(), PushTarget.name.asc(), PushTarget.id.asc())
            .all()
        )
        return [
            {
                "value": row.id,
                "label": row.name,
                "is_default": bool(row.is_default),
            }
            for row in rows
        ]
    finally:
        db.close()


def list_env_config_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    push_target_options: list[dict[str, Any]] | None = None
    for field in ENV_CONFIG_FIELDS:
        item = asdict(field)
        item["options"] = list(field.options)
        item["value"] = _serialize_value(field)
        if field.value_type == "push_target_select":
            if push_target_options is None:
                push_target_options = _load_feishu_push_target_options()
            item["option_items"] = push_target_options
        items.append(item)
    return items


def update_env_config(updates: dict[str, Any]) -> list[dict[str, Any]]:
    updates = _normalize_database_updates(updates)
    unknown = sorted(set(updates) - ENV_CONFIG_KEYS)
    if unknown:
        raise ValueError(f"Unknown config keys: {', '.join(unknown)}")

    target_database_url = str(updates.get("DATABASE_URL", getattr(Config, "DATABASE_URL", "")) or "").strip()
    if target_database_url:
        upsert_runtime_config_values(updates, database_url=target_database_url)

    _apply_env_updates(updates, refresh=False)
    refresh_runtime_env(force=True)
    return list_env_config_items()
