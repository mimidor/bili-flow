from __future__ import annotations

from datetime import datetime
import threading
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from config import Config
from app.utils.runtime_home import get_data_dir

Base = declarative_base()


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    mid = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    homepage_url = Column(String, nullable=True)
    last_video_bvid = Column(String, nullable=True)
    last_dynamic_id = Column(String, nullable=True)
    last_check_time = Column(DateTime, nullable=True)
    push_target_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True)
    bvid = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    mid = Column(String, nullable=False)
    pub_time = Column(Integer, nullable=True)
    has_subtitle = Column(Boolean, default=False)
    has_video = Column(Boolean, default=False)
    has_audio = Column(Boolean, default=False)
    subtitle_path = Column(String, nullable=True)
    transcript_text = Column(Text, nullable=True)
    video_path = Column(String, nullable=True)
    audio_path = Column(String, nullable=True)
    status = Column(String, default="pending")
    attempt_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    summary_json = Column(Text, nullable=True)
    doc_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Dynamic(Base):
    __tablename__ = "dynamics"

    id = Column(Integer, primary_key=True)
    dynamic_id = Column(String, unique=True, nullable=False)
    mid = Column(String, nullable=False)
    type = Column(String, nullable=True)
    text = Column(Text, nullable=True)
    image_count = Column(Integer, default=0)
    images_path = Column(Text, nullable=True)
    image_urls = Column(Text, nullable=True)
    status = Column(String, default="pending")
    push_status = Column(String, default="pending")
    pub_time = Column(DateTime, nullable=True)
    pushed_at = Column(DateTime, nullable=True)
    attempt_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    summary_json = Column(Text, nullable=True)
    doc_url = Column(String, nullable=True)


class PodcastSubscription(Base):
    __tablename__ = "podcast_subscriptions"

    id = Column(Integer, primary_key=True)
    pid = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    homepage_url = Column(String, nullable=True)
    last_episode_eid = Column(String, nullable=True)
    last_episode_pub_time = Column(DateTime, nullable=True)
    last_response_cursor_json = Column(Text, nullable=True)
    bootstrap_recent_episodes = Column(Integer, default=3)
    last_check_time = Column(DateTime, nullable=True)
    last_success_time = Column(DateTime, nullable=True)
    consecutive_failures = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PodcastEpisode(Base):
    __tablename__ = "podcast_episodes"

    id = Column(Integer, primary_key=True)
    eid = Column(String, unique=True, nullable=False)
    pid = Column(String, nullable=False)
    title = Column(String, nullable=False)
    pub_time = Column(DateTime, nullable=True)
    audio_url = Column(String, nullable=False)
    audio_mime = Column(String, nullable=True)
    audio_size = Column(Integer, nullable=True)
    raw_episode_json = Column(Text, nullable=False)
    local_audio_path = Column(Text, nullable=True)
    local_transcript_path = Column(Text, nullable=True)
    local_summary_path = Column(Text, nullable=True)
    transcript_text = Column(Text, nullable=True)
    summary_json = Column(Text, nullable=True)
    doc_url = Column(String, nullable=True)
    status = Column(String, default="pending")
    push_status = Column(String, default="pending")
    download_attempts = Column(Integer, default=0)
    asr_attempts = Column(Integer, default=0)
    summary_attempts = Column(Integer, default=0)
    attempt_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    discovered_at = Column(DateTime, default=datetime.utcnow)
    downloaded_at = Column(DateTime, nullable=True)
    transcribed_at = Column(DateTime, nullable=True)
    summarized_at = Column(DateTime, nullable=True)
    pushed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WeWeRssSubscription(Base):
    __tablename__ = "wewe_rss_subscriptions"

    id = Column(Integer, primary_key=True)
    feed_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    homepage_url = Column(String, nullable=True)
    feed_format = Column(String, default="atom")
    push_target_id = Column(Integer, nullable=True)
    last_entry_id = Column(String, nullable=True)
    last_entry_pub_time = Column(DateTime, nullable=True)
    last_response_cursor_json = Column(Text, nullable=True)
    bootstrap_recent_items = Column(Integer, default=3)
    last_check_time = Column(DateTime, nullable=True)
    last_success_time = Column(DateTime, nullable=True)
    consecutive_failures = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WeWeRssArticle(Base):
    __tablename__ = "wewe_rss_articles"

    id = Column(Integer, primary_key=True)
    entry_id = Column(String, unique=True, nullable=False)
    feed_id = Column(String, nullable=False)
    title = Column(String, nullable=False)
    author = Column(String, nullable=True)
    link = Column(Text, nullable=False)
    pub_time = Column(DateTime, nullable=True)
    content_text = Column(Text, nullable=True)
    content_html = Column(Text, nullable=True)
    raw_entry_json = Column(Text, nullable=False)
    status = Column(String, default="pending")
    push_status = Column(String, default="pending")
    attempt_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    discovered_at = Column(DateTime, default=datetime.utcnow)
    pushed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True)
    bvid = Column(String, unique=True, nullable=False)
    summary_json = Column(Text, nullable=False)
    push_status = Column(String, default="pending")
    pushed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True)
    level = Column(String)
    message = Column(Text)
    context = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class ClassificationRule(Base):
    __tablename__ = "classification_rules"

    id = Column(Integer, primary_key=True)
    uploader_name = Column(String, nullable=False)
    pattern = Column(String, nullable=False)
    target_folder = Column(String, nullable=False)
    priority = Column(Integer, default=100)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FolderMapping(Base):
    __tablename__ = "folder_mappings"

    id = Column(Integer, primary_key=True)
    uploader_name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    folder_token = Column(String, nullable=False)
    folder_path = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PushHistory(Base):
    __tablename__ = "push_history"

    id = Column(Integer, primary_key=True)
    content_type = Column(String, nullable=False)
    content_id = Column(String, nullable=False)
    content_title = Column(String, nullable=True)
    uploader_name = Column(String, nullable=True)
    channel = Column(String, nullable=False)
    target_id = Column(Integer, nullable=True)
    target_name = Column(String, nullable=True)
    target_receive_id = Column(String, nullable=True)
    status = Column(String, default="success")
    error_message = Column(Text, nullable=True)
    response_summary = Column(Text, nullable=True)
    request_payload = Column(Text, nullable=True)
    response_payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LLMUsage(Base):
    __tablename__ = "llm_usage"

    id = Column(Integer, primary_key=True)
    content_type = Column(String, nullable=True)
    content_id = Column(String, nullable=True)
    content_title = Column(String, nullable=True)
    uploader_name = Column(String, nullable=True)
    provider = Column(String, nullable=False)
    model = Column(String, nullable=True)
    web_search_enabled = Column(Boolean, default=False)
    web_search_mode = Column(String, nullable=True)
    web_search_used = Column(Boolean, default=False)
    web_search_fallback_reason = Column(Text, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    raw_response = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RuntimeConfig(Base):
    __tablename__ = "runtime_configs"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BilibiliAuthState(Base):
    __tablename__ = "bilibili_auth_state"

    id = Column(Integer, primary_key=True)
    refresh_token = Column(Text, nullable=True)
    last_check_time = Column(Float, nullable=True)
    last_refresh_time = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PushTarget(Base):
    __tablename__ = "push_targets"

    id = Column(Integer, primary_key=True)
    channel = Column(String, nullable=False, default="feishu")
    name = Column(String, nullable=False)
    receive_id = Column(String, nullable=False)
    receive_id_type = Column(String, nullable=False, default="chat_id")
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AdminUserRole(Base):
    __tablename__ = "admin_user_roles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(Integer, ForeignKey("admin_roles.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_admin_user_role"),
    )


class AdminRolePermission(Base):
    __tablename__ = "admin_role_permissions"

    id = Column(Integer, primary_key=True)
    role_id = Column(Integer, ForeignKey("admin_roles.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_id = Column(Integer, ForeignKey("admin_permissions.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_admin_role_permission"),
    )


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)
    display_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_super_admin = Column(Boolean, default=False, nullable=False)
    session_nonce = Column(String, nullable=False, default="")
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    roles = relationship("AdminRole", secondary="admin_user_roles", back_populates="users")


class AdminRole(Base):
    __tablename__ = "admin_roles"

    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = relationship("AdminUser", secondary="admin_user_roles", back_populates="roles")
    permissions = relationship("AdminPermission", secondary="admin_role_permissions", back_populates="roles")


class AdminPermission(Base):
    __tablename__ = "admin_permissions"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False, index=True)
    label = Column(String, nullable=False)
    kind = Column(String, nullable=False)
    group_key = Column(String, nullable=False)
    group_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    roles = relationship("AdminRole", secondary="admin_role_permissions", back_populates="permissions")


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    prompt_text = Column(Text, nullable=False)
    model_profile_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LLMModelProfile(Base):
    __tablename__ = "llm_model_profiles"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    base_url = Column(String, nullable=True)
    api_key = Column(Text, nullable=True)
    model_name = Column(String, nullable=False)
    enable_web_search = Column(Boolean, default=False)
    enable_reasoning = Column(Boolean, default=False)
    enable_image = Column(Boolean, default=False)
    enable_tools = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LLMChatSession(Base):
    __tablename__ = "llm_chat_sessions"

    id = Column(Integer, primary_key=True)
    session_key = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False, default="新会话")
    source = Column(String, nullable=False, default="workbench")
    model_ids_json = Column(Text, nullable=False, default="[]")
    system_prompt = Column(Text, nullable=False, default="")
    temperature = Column(Float, nullable=False, default=0.3)
    max_tokens = Column(Integer, nullable=False, default=2048)
    turns_count = Column(Integer, nullable=False, default=0)
    last_turn_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_llm_chat_sessions_updated_at", "updated_at"),
    )


class LLMChatSessionTurn(Base):
    __tablename__ = "llm_chat_session_turns"

    id = Column(Integer, primary_key=True)
    session_id = Column(
        Integer,
        ForeignKey("llm_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    turn_index = Column(Integer, nullable=False)
    source = Column(String, nullable=False, default="workbench")
    user_prompt = Column(Text, nullable=False)
    model_results_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("session_id", "turn_index", name="uq_llm_chat_session_turns_session_id_turn_index"),
        Index("idx_llm_chat_turns_session_id_created_at", "session_id", "created_at"),
    )


class TaskRuntimeState(Base):
    __tablename__ = "task_runtime_states"

    id = Column(Integer, primary_key=True)
    component = Column(String, unique=True, nullable=False)
    is_paused = Column(Boolean, default=False)
    status = Column(String, default="running")
    last_heartbeat_at = Column(DateTime, nullable=True)
    last_run_at = Column(DateTime, nullable=True)
    last_message = Column(Text, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ManualPushTask(Base):
    __tablename__ = "manual_push_tasks"

    id = Column(Integer, primary_key=True)
    bvid = Column(String, nullable=False, index=True)
    source_type = Column(String, nullable=False, default="bilibili", index=True)
    source_path = Column(Text, nullable=True)
    push_target_id = Column(Integer, nullable=True)
    title = Column(String, nullable=True)
    uploader_name = Column(String, nullable=True)
    source_video_id = Column(Integer, nullable=True)
    status = Column(String, default="pending")
    stage = Column(String, default="created")
    progress = Column(Integer, default=0)
    message = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_manual_push_tasks_source_type_path", "source_type", "source_path"),
    )


class QteasyJobSnapshot(Base):
    __tablename__ = "qteasy_job_snapshots"

    id = Column(Integer, primary_key=True)
    job_id = Column(String, unique=True, nullable=False, index=True)
    task_type = Column(String, nullable=False)
    job_name = Column(String, nullable=True)
    status = Column(String, nullable=False, default="queued")
    priority = Column(Integer, nullable=True)
    progress = Column(Integer, nullable=True)
    current_step = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    payload_json = Column(Text, nullable=True)
    raw_result_json = Column(Text, nullable=True)
    worker_id = Column(String, nullable=True)
    attempts = Column(Integer, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class QteasyBacktestResult(Base):
    __tablename__ = "qteasy_backtest_results"

    id = Column(Integer, primary_key=True)
    job_id = Column(String, unique=True, nullable=False, index=True)
    task_type = Column(String, nullable=False)
    job_name = Column(String, nullable=True)
    strategy_id = Column(String, nullable=True)
    strategy_path = Column(String, nullable=True)
    symbol_pool_json = Column(Text, nullable=True)
    benchmark = Column(String, nullable=True)
    invest_start = Column(String, nullable=True)
    invest_end = Column(String, nullable=True)
    status = Column(String, nullable=False, default="succeeded")
    payload_json = Column(Text, nullable=True)
    raw_result_json = Column(Text, nullable=True)
    metrics_json = Column(Text, nullable=True)
    equity_curve_json = Column(Text, nullable=True)
    drawdown_curve_json = Column(Text, nullable=True)
    return_histogram_json = Column(Text, nullable=True)
    parse_message = Column(Text, nullable=True)
    parsed_ok = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_synced_at = Column(DateTime, nullable=True)


class OpenClawScenario(Base):
    __tablename__ = "openclaw_scenarios"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="draft")
    agent_selection_mode = Column(String, default="existing")
    selected_agents = Column(Text, default="[]")
    generated_agents = Column(Text, default="[]")
    bindings = Column(Text, default="[]")
    tasks = Column(Text, default="[]")
    execution_log = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OpenClawTask(Base):
    __tablename__ = "openclaw_tasks"

    id = Column(String, primary_key=True)
    scenario_id = Column(String, nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="pending")
    assigned_agents = Column(Text, default="[]")
    priority = Column(String, default="medium")
    mode = Column(String, default="default")
    conversation_history = Column(Text, default="[]")
    execution_history = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OpenClawBackupRecord(Base):
    __tablename__ = "openclaw_backup_records"

    id = Column(String, primary_key=True)
    type = Column(String, nullable=False)
    filename = Column(String, nullable=True)
    status = Column(String, default="pending")
    progress = Column(Integer, default=0)
    message = Column(Text, nullable=True)
    stage = Column(String, nullable=True)
    error = Column(Text, nullable=True)
    result = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    size = Column(Integer, nullable=True)


_ENGINE_LOCK = threading.RLock()
_ENGINE_CACHE: dict[tuple[Any, ...], Any] = {}
_SESSION_FACTORY_CACHE: dict[tuple[Any, ...], Any] = {}


def _is_sqlite_url(database_url: str) -> bool:
    return "sqlite" in (database_url or "").lower()


def _engine_cache_key(
    database_url: str,
    *,
    sqlite_timeout_seconds: float | None = None,
    pool_timeout_seconds: float | None = None,
    sqlite_busy_timeout_ms: int | None = None,
) -> tuple[Any, ...]:
    return (
        database_url,
        sqlite_timeout_seconds,
        pool_timeout_seconds,
        sqlite_busy_timeout_ms,
    )


def _build_engine(
    database_url: str,
    *,
    sqlite_timeout_seconds: float | None = None,
    pool_timeout_seconds: float | None = None,
    sqlite_busy_timeout_ms: int | None = None,
):
    resolved_pool_timeout = 30 if pool_timeout_seconds is None else float(pool_timeout_seconds)
    resolved_sqlite_timeout = 30 if sqlite_timeout_seconds is None else float(sqlite_timeout_seconds)
    resolved_busy_timeout = 30000 if sqlite_busy_timeout_ms is None else int(sqlite_busy_timeout_ms)
    connect_args = (
        {
            "check_same_thread": False,
            "timeout": resolved_sqlite_timeout,
        }
        if _is_sqlite_url(database_url)
        else {}
    )
    engine = create_engine(
        database_url,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_timeout=resolved_pool_timeout,
        connect_args=connect_args,
    )

    if _is_sqlite_url(database_url):
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):  # type: ignore[unused-argument]
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute(f"PRAGMA busy_timeout={resolved_busy_timeout}")
            cursor.close()

    return engine


def get_database_url() -> str:
    url = Config.DATABASE_URL
    return str(url or f"sqlite:///{(get_data_dir() / 'bili.db').expanduser().resolve().as_posix()}")


def get_engine(
    database_url: str | None = None,
    *,
    sqlite_timeout_seconds: float | None = None,
    pool_timeout_seconds: float | None = None,
    sqlite_busy_timeout_ms: int | None = None,
):
    resolved_url = database_url or get_database_url()
    cache_key = _engine_cache_key(
        resolved_url,
        sqlite_timeout_seconds=sqlite_timeout_seconds,
        pool_timeout_seconds=pool_timeout_seconds,
        sqlite_busy_timeout_ms=sqlite_busy_timeout_ms,
    )
    with _ENGINE_LOCK:
        engine = _ENGINE_CACHE.get(cache_key)
        if engine is None:
            engine = _build_engine(
                resolved_url,
                sqlite_timeout_seconds=sqlite_timeout_seconds,
                pool_timeout_seconds=pool_timeout_seconds,
                sqlite_busy_timeout_ms=sqlite_busy_timeout_ms,
            )
            _ENGINE_CACHE[cache_key] = engine
        return engine


def get_session_factory(
    database_url: str | None = None,
    *,
    sqlite_timeout_seconds: float | None = None,
    pool_timeout_seconds: float | None = None,
    sqlite_busy_timeout_ms: int | None = None,
):
    resolved_url = database_url or get_database_url()
    cache_key = _engine_cache_key(
        resolved_url,
        sqlite_timeout_seconds=sqlite_timeout_seconds,
        pool_timeout_seconds=pool_timeout_seconds,
        sqlite_busy_timeout_ms=sqlite_busy_timeout_ms,
    )
    with _ENGINE_LOCK:
        factory = _SESSION_FACTORY_CACHE.get(cache_key)
        if factory is None:
            factory = sessionmaker(
                bind=get_engine(
                    resolved_url,
                    sqlite_timeout_seconds=sqlite_timeout_seconds,
                    pool_timeout_seconds=pool_timeout_seconds,
                    sqlite_busy_timeout_ms=sqlite_busy_timeout_ms,
                ),
                expire_on_commit=False,
            )
            _SESSION_FACTORY_CACHE[cache_key] = factory
        return factory


def create_session(
    database_url: str | None = None,
    *,
    sqlite_timeout_seconds: float | None = None,
    pool_timeout_seconds: float | None = None,
    sqlite_busy_timeout_ms: int | None = None,
):
    return get_session_factory(
        database_url,
        sqlite_timeout_seconds=sqlite_timeout_seconds,
        pool_timeout_seconds=pool_timeout_seconds,
        sqlite_busy_timeout_ms=sqlite_busy_timeout_ms,
    )()


class _SessionLocalProxy:
    def __call__(self, *args, **kwargs):
        return get_session_factory()(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(get_session_factory(), name)


SessionLocal = _SessionLocalProxy()


def init_db():
    Base.metadata.create_all(get_engine())
    print("database initialized")


def get_db():
    return SessionLocal()
