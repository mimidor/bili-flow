from __future__ import annotations

from dataclasses import dataclass
import hashlib
import secrets
from typing import Any

PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 390000
READ_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass(frozen=True)
class PermissionSeed:
    key: str
    label: str
    kind: str
    group_key: str
    group_name: str
    description: str = ""


@dataclass(frozen=True)
class RoleSeed:
    code: str
    name: str
    description: str
    permission_keys: tuple[str, ...]


MENU_PERMISSION_SEEDS: tuple[PermissionSeed, ...] = (
    PermissionSeed("menu.dashboard", "Dashboard", "menu", "menu.core", "Core"),
    PermissionSeed("menu.monitor", "System Monitor", "menu", "menu.core", "Core"),
    PermissionSeed("menu.content_audit", "Content Audit", "menu", "menu.core", "Core"),
    PermissionSeed("menu.videos", "Videos", "menu", "menu.content", "Content"),
    PermissionSeed("menu.dynamics", "Dynamics", "menu", "menu.content", "Content"),
    PermissionSeed("menu.manual_push", "Manual Push", "menu", "menu.content", "Content"),
    PermissionSeed("menu.push_history", "Push History", "menu", "menu.content", "Content"),
    PermissionSeed("menu.push_targets", "Push Targets", "menu", "menu.config", "Config"),
    PermissionSeed("menu.tokens", "Token Stats", "menu", "menu.analytics", "Analytics"),
    PermissionSeed("menu.qteasy", "Qteasy", "menu", "menu.analytics", "Analytics"),
    PermissionSeed("menu.tasks", "Task Center", "menu", "menu.core", "Core"),
    PermissionSeed("menu.logs", "Log Center", "menu", "menu.core", "Core"),
    PermissionSeed("menu.podcasts", "Podcasts", "menu", "menu.content", "Content"),
    PermissionSeed("menu.wewe_rss", "WeWe RSS", "menu", "menu.content", "Content"),
    PermissionSeed("menu.llm_models", "LLM Models", "menu", "menu.llm", "LLM"),
    PermissionSeed("menu.llm_chat", "LLM Chat Workbench", "menu", "menu.llm", "LLM"),
    PermissionSeed("menu.llm_prompts", "LLM Prompts", "menu", "menu.llm", "LLM"),
    PermissionSeed("menu.subscriptions", "Subscriptions", "menu", "menu.config", "Config"),
    PermissionSeed("menu.rules", "Rules", "menu", "menu.config", "Config"),
    PermissionSeed("menu.folder_mappings", "Folder Mappings", "menu", "menu.config", "Config"),
    PermissionSeed("menu.config", "Business Config", "menu", "menu.config", "Config"),
    PermissionSeed("menu.env_config", "Environment Config", "menu", "menu.config", "Config"),
    PermissionSeed("menu.access_control", "Accounts & Roles", "menu", "menu.config", "Config"),
)

API_PERMISSION_SEEDS: tuple[PermissionSeed, ...] = (
    PermissionSeed("api.analytics.read", "Analytics Read", "api", "api.analytics", "Analytics"),
    PermissionSeed("api.logs.read", "Logs Read", "api", "api.logs", "Logs"),
    PermissionSeed("api.tasks.read", "Tasks Read", "api", "api.tasks", "Tasks"),
    PermissionSeed("api.tasks.write", "Tasks Write", "api", "api.tasks", "Tasks"),
    PermissionSeed("api.videos.read", "Videos Read", "api", "api.videos", "Videos"),
    PermissionSeed("api.videos.write", "Videos Write", "api", "api.videos", "Videos"),
    PermissionSeed("api.dynamics.read", "Dynamics Read", "api", "api.dynamics", "Dynamics"),
    PermissionSeed("api.dynamics.write", "Dynamics Write", "api", "api.dynamics", "Dynamics"),
    PermissionSeed("api.push_history.read", "Push History Read", "api", "api.push_history", "Push History"),
    PermissionSeed("api.push_targets.read", "Push Targets Read", "api", "api.push_targets", "Push Targets"),
    PermissionSeed("api.push_targets.write", "Push Targets Write", "api", "api.push_targets", "Push Targets"),
    PermissionSeed("api.subscriptions.read", "Subscriptions Read", "api", "api.subscriptions", "Subscriptions"),
    PermissionSeed("api.subscriptions.write", "Subscriptions Write", "api", "api.subscriptions", "Subscriptions"),
    PermissionSeed("api.podcasts.read", "Podcasts Read", "api", "api.podcasts", "Podcasts"),
    PermissionSeed("api.podcasts.write", "Podcasts Write", "api", "api.podcasts", "Podcasts"),
    PermissionSeed("api.wewe_rss.read", "WeWe RSS Read", "api", "api.wewe_rss", "WeWe RSS"),
    PermissionSeed("api.wewe_rss.write", "WeWe RSS Write", "api", "api.wewe_rss", "WeWe RSS"),
    PermissionSeed("api.rules.read", "Rules Read", "api", "api.rules", "Rules"),
    PermissionSeed("api.rules.write", "Rules Write", "api", "api.rules", "Rules"),
    PermissionSeed("api.folder_mappings.read", "Folder Mappings Read", "api", "api.folder_mappings", "Folder Mappings"),
    PermissionSeed("api.folder_mappings.write", "Folder Mappings Write", "api", "api.folder_mappings", "Folder Mappings"),
    PermissionSeed("api.config.read", "Config Read", "api", "api.config", "Config"),
    PermissionSeed("api.config.write", "Config Write", "api", "api.config", "Config"),
    PermissionSeed("api.llm.read", "LLM Read", "api", "api.llm", "LLM"),
    PermissionSeed("api.llm.write", "LLM Write", "api", "api.llm", "LLM"),
    PermissionSeed("api.qteasy.read", "Qteasy Read", "api", "api.qteasy", "Qteasy"),
    PermissionSeed("api.qteasy.write", "Qteasy Write", "api", "api.qteasy", "Qteasy"),
    PermissionSeed("api.auth_admin.read", "Access Control Read", "api", "api.auth_admin", "Access Control"),
    PermissionSeed("api.auth_admin.write", "Access Control Write", "api", "api.auth_admin", "Access Control"),
)

ALL_PERMISSION_SEEDS: tuple[PermissionSeed, ...] = MENU_PERMISSION_SEEDS + API_PERMISSION_SEEDS
ALL_PERMISSION_KEYS: tuple[str, ...] = tuple(seed.key for seed in ALL_PERMISSION_SEEDS)

OPERATOR_PERMISSION_KEYS: tuple[str, ...] = (
    "menu.dashboard",
    "menu.monitor",
    "menu.content_audit",
    "menu.videos",
    "menu.dynamics",
    "menu.manual_push",
    "menu.push_history",
    "menu.push_targets",
    "menu.tokens",
    "menu.qteasy",
    "menu.tasks",
    "menu.logs",
    "menu.podcasts",
    "menu.wewe_rss",
    "menu.llm_models",
    "menu.llm_chat",
    "menu.llm_prompts",
    "menu.subscriptions",
    "menu.rules",
    "menu.folder_mappings",
    "menu.config",
    "menu.env_config",
    "api.analytics.read",
    "api.logs.read",
    "api.tasks.read",
    "api.tasks.write",
    "api.videos.read",
    "api.videos.write",
    "api.dynamics.read",
    "api.dynamics.write",
    "api.push_history.read",
    "api.push_targets.read",
    "api.push_targets.write",
    "api.subscriptions.read",
    "api.subscriptions.write",
    "api.podcasts.read",
    "api.podcasts.write",
    "api.wewe_rss.read",
    "api.wewe_rss.write",
    "api.rules.read",
    "api.rules.write",
    "api.folder_mappings.read",
    "api.folder_mappings.write",
    "api.config.read",
    "api.config.write",
    "api.llm.read",
    "api.llm.write",
    "api.qteasy.read",
    "api.qteasy.write",
)

VIEWER_PERMISSION_KEYS: tuple[str, ...] = (
    "menu.dashboard",
    "menu.monitor",
    "menu.push_history",
    "menu.tokens",
    "menu.qteasy",
    "menu.logs",
    "api.analytics.read",
    "api.logs.read",
    "api.push_history.read",
    "api.qteasy.read",
)

DEFAULT_ROLE_SEEDS: tuple[RoleSeed, ...] = (
    RoleSeed("super_admin", "Super Admin", "Full access to all menus and API groups.", ALL_PERMISSION_KEYS),
    RoleSeed("operator", "Operator", "Operate content, tasks, config, llm and qteasy modules.", OPERATOR_PERMISSION_KEYS),
    RoleSeed("viewer", "Viewer", "Read-only access to overview, logs, push history and qteasy.", VIEWER_PERMISSION_KEYS),
)

DEFAULT_SUPER_ADMIN_USERNAME = "admin"
DEFAULT_SUPER_ADMIN_PASSWORD = "change-me"


def is_read_method(method: str) -> bool:
    return method.upper() in READ_METHODS


def build_menu_keys(permission_keys: set[str] | list[str] | tuple[str, ...]) -> list[str]:
    return sorted(key for key in permission_keys if key.startswith("menu."))


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"{PASSWORD_HASH_ALGORITHM}${PASSWORD_HASH_ITERATIONS}${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt, expected = password_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != PASSWORD_HASH_ALGORITHM:
        return False
    try:
        iterations = int(iterations_text)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return secrets.compare_digest(digest, expected)


def generate_session_nonce() -> str:
    return secrets.token_urlsafe(24)


def list_permission_payloads() -> list[dict[str, Any]]:
    return [
        {
            "key": seed.key,
            "label": seed.label,
            "kind": seed.kind,
            "group_key": seed.group_key,
            "group_name": seed.group_name,
            "description": seed.description,
        }
        for seed in ALL_PERMISSION_SEEDS
    ]
