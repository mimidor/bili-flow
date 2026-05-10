from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)


class StatusUpdate(BaseModel):
    status: str


class BatchStatusUpdate(BaseModel):
    ids: list[int]
    status: str


class BatchActiveUpdate(BaseModel):
    ids: list[int]
    is_active: bool


class BatchIdsRequest(BaseModel):
    ids: list[int]


class RetryResponse(BaseModel):
    success: bool
    message: str


class AuthLoginRequest(BaseModel):
    username: str
    password: str


class AuthRoleResponse(BaseModel):
    id: int
    code: str
    name: str


class AuthUserResponse(BaseModel):
    authenticated: bool = True
    id: int
    username: str
    display_name: str | None = None
    is_super_admin: bool = False
    roles: list[AuthRoleResponse] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    menu_keys: list[str] = Field(default_factory=list)
    token: str | None = None


class AdminPermissionResponse(BaseModel):
    id: int
    key: str
    label: str
    kind: str
    group_key: str
    group_name: str
    description: str | None = None


class AdminRoleCreateRequest(BaseModel):
    code: str
    name: str
    description: str | None = None
    is_active: bool = True
    permission_keys: list[str] = Field(default_factory=list)


class AdminRoleUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    permission_keys: list[str] | None = None


class AdminRoleResponse(BaseModel):
    id: int
    code: str
    name: str
    description: str | None = None
    is_system: bool = False
    is_active: bool = True
    permissions: list[AdminPermissionResponse] = Field(default_factory=list)
    permission_keys: list[str] = Field(default_factory=list)
    user_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class AdminUserCreateRequest(BaseModel):
    username: str
    password: str
    display_name: str | None = None
    is_active: bool = True
    is_super_admin: bool = False
    role_ids: list[int] = Field(default_factory=list)


class AdminUserUpdateRequest(BaseModel):
    display_name: str | None = None
    is_active: bool | None = None
    is_super_admin: bool | None = None
    role_ids: list[int] | None = None


class AdminUserResetPasswordRequest(BaseModel):
    password: str


class AdminUserResponse(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    is_active: bool = True
    is_super_admin: bool = False
    roles: list[AuthRoleResponse] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    menu_keys: list[str] = Field(default_factory=list)
    last_login_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SubscriptionCreate(BaseModel):
    mid: str
    name: str
    homepage_url: str | None = None
    notes: str | None = None
    push_target_id: int | None = None
    is_active: bool = True


class SubscriptionUpdate(BaseModel):
    name: str | None = None
    homepage_url: str | None = None
    notes: str | None = None
    push_target_id: int | None = None
    is_active: bool | None = None


class PushTargetCreate(BaseModel):
    channel: str = "feishu"
    name: str
    receive_id: str
    receive_id_type: str
    notes: str | None = None
    is_active: bool = True
    is_default: bool = False


class PushTargetUpdate(BaseModel):
    name: str | None = None
    receive_id: str | None = None
    receive_id_type: str | None = None
    notes: str | None = None
    is_active: bool | None = None
    is_default: bool | None = None


class PodcastSubscriptionCreate(BaseModel):
    pid: str
    name: str
    homepage_url: str | None = None
    notes: str | None = None
    is_active: bool = True
    bootstrap_recent_episodes: int = 3


class PodcastSubscriptionUpdate(BaseModel):
    name: str | None = None
    homepage_url: str | None = None
    notes: str | None = None
    is_active: bool | None = None
    bootstrap_recent_episodes: int | None = None


class WeWeRssFeedItem(BaseModel):
    feed_id: str
    title: str
    homepage_url: str | None = None
    atom_url: str | None = None
    rss_url: str | None = None
    json_url: str | None = None
    raw: dict[str, Any] | None = None


class WeWeRssSubscriptionCreate(BaseModel):
    feed_id: str
    name: str
    homepage_url: str | None = None
    notes: str | None = None
    push_target_id: int | None = None
    feed_format: str = "atom"
    bootstrap_recent_items: int = 3
    is_active: bool = True


class WeWeRssSubscriptionUpdate(BaseModel):
    name: str | None = None
    homepage_url: str | None = None
    notes: str | None = None
    push_target_id: int | None = None
    feed_format: str | None = None
    bootstrap_recent_items: int | None = None
    is_active: bool | None = None


class WeWeRssArticleItem(BaseModel):
    id: int
    entry_id: str
    feed_id: str
    title: str
    author: str | None = None
    link: str
    pub_time: str | None = None
    content_text: str | None = None
    content_html: str | None = None
    raw_entry_json: dict[str, Any] | str | None = None
    status: str
    push_status: str
    attempt_count: int = 0
    last_error: str | None = None
    discovered_at: str | None = None
    pushed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    source_url: str | None = None


class ClassificationRuleCreate(BaseModel):
    uploader_name: str
    pattern: str
    target_folder: str
    priority: int = 100
    is_active: bool = True


class ClassificationRuleUpdate(BaseModel):
    uploader_name: str | None = None
    pattern: str | None = None
    target_folder: str | None = None
    priority: int | None = None
    is_active: bool | None = None


class FolderMappingCreate(BaseModel):
    uploader_name: str
    category: str
    folder_token: str
    folder_path: str


class FolderMappingUpdate(BaseModel):
    uploader_name: str | None = None
    category: str | None = None
    folder_token: str | None = None
    folder_path: str | None = None


class ListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[dict[str, Any]]


class OverviewResponse(BaseModel):
    videos: int
    dynamics: int
    podcasts: int
    push_records: int
    llm_calls: int
    llm_total_tokens: int
    llm_prompt_tokens: int
    llm_completion_tokens: int


class TaskRuntimeItem(BaseModel):
    component: str
    label: str
    is_paused: bool
    status: str
    last_heartbeat_at: str | None = None
    last_run_at: str | None = None
    last_message: str | None = None
    last_error: str | None = None


class TaskOverviewResponse(BaseModel):
    video_pending: int
    video_processing: int
    video_failed: int
    dynamic_pending: int
    dynamic_processing: int
    dynamic_failed: int
    podcast_pending: int
    podcast_processing: int
    podcast_failed: int
    total_pending: int
    total_processing: int
    total_failed: int
    runtime_states: list[TaskRuntimeItem]


class TaskListItem(BaseModel):
    id: int
    content_type: Literal["video", "dynamic", "podcast"]
    content_id: str
    title: str
    uploader_name: str | None = None
    status: str
    push_status: str | None = None
    attempt_count: int = 0
    last_error: str | None = None
    pub_time: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    source_url: str | None = None
    doc_url: str | None = None
    summary_excerpt: str | None = None


class TaskListResponse(PageParams):
    total: int
    items: list[TaskListItem]


class TaskRetryItem(BaseModel):
    content_type: Literal["video", "dynamic", "podcast"]
    id: int


class TaskRetryRequest(BaseModel):
    items: list[TaskRetryItem]


class TaskRetryResponse(BaseModel):
    success: bool
    requeued: int
    failed: int
    message: str


class TaskRuntimeUpdateRequest(BaseModel):
    scheduler_paused: bool | None = None
    queue_paused: bool | None = None


class TaskRuntimeUpdateResponse(BaseModel):
    runtime_states: list[TaskRuntimeItem]


class TaskRunResponse(BaseModel):
    success: bool
    task: str
    target: str | None = None
    message: str


class TaskAcceptedResponse(BaseModel):
    accepted: bool
    task: str
    target: str | None = None
    message: str


class ManualPushTaskCreateRequest(BaseModel):
    bvid: str
    push_target_id: int | None = None


class ManualPushTaskCreateResponse(BaseModel):
    accepted: bool
    task_id: int
    bvid: str
    push_target_id: int | None = None
    push_target_name: str | None = None
    message: str


class ManualPushTaskItem(BaseModel):
    id: int
    bvid: str
    source_type: str | None = None
    source_path: str | None = None
    push_target_id: int | None = None
    push_target_name: str | None = None
    title: str | None = None
    uploader_name: str | None = None
    source_video_id: int | None = None
    status: str
    stage: str
    progress: int
    message: str | None = None
    error_message: str | None = None
    result_json: dict[str, Any] | None = None
    created_at: str | None = None
    updated_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    source_url: str | None = None


class ManualPushTaskListResponse(PageParams):
    total: int
    items: list[ManualPushTaskItem]


class EnvConfigItem(BaseModel):
    key: str
    label: str
    group: str
    value_type: str
    description: str = ""
    editable: bool = True
    secret: bool = False
    restart_required: bool = False
    options: list[str] = Field(default_factory=list)
    option_items: list[dict[str, Any]] = Field(default_factory=list)
    value: Any


class EnvConfigUpdateRequest(BaseModel):
    updates: dict[str, Any]


class EnvConfigResponse(BaseModel):
    items: list[EnvConfigItem]
