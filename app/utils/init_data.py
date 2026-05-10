from __future__ import annotations

from admin_backend.rbac import (
    DEFAULT_ROLE_SEEDS,
    DEFAULT_SUPER_ADMIN_PASSWORD,
    DEFAULT_SUPER_ADMIN_USERNAME,
    generate_session_nonce,
    hash_password,
    list_permission_payloads,
)
from app.models.database import (
    AdminPermission,
    AdminRole,
    AdminUser,
    BilibiliAuthState,
    LLMModelProfile,
    PromptTemplate,
    PushTarget,
    SessionLocal,
)
from app.utils.runtime_config import load_runtime_config_overrides, seed_runtime_config_rows
from app.utils.runtime_home import get_install_root, get_runtime_home
from config import Config


def _push_relevance_fallback_prompt() -> str:
    try:
        from app.modules.processor import PUSH_RELEVANCE_PROMPT

        return PUSH_RELEVANCE_PROMPT
    except Exception:
        return (
            "You are a relevance classifier for push notifications. "
            "Decide whether the content should be pushed. "
            "Return only a JSON object with should_push and reason."
        )


def _seed_bilibili_auth_state(db) -> None:
    auth_state = db.query(BilibiliAuthState).first()
    if auth_state:
        return

    legacy_path = get_runtime_home() / "data" / "bilibili_auth.json"
    if not legacy_path.exists():
        return

    try:
        import json

        data = json.loads(legacy_path.read_text(encoding="utf-8"))
    except Exception:
        return

    if not isinstance(data, dict):
        return

    db.add(
        BilibiliAuthState(
            refresh_token=data.get("refresh_token"),
            last_check_time=data.get("last_check_time"),
            last_refresh_time=data.get("last_refresh_time"),
        )
    )
    db.commit()


def _seed_rbac(db) -> None:
    permission_by_key: dict[str, AdminPermission] = {}
    for payload in list_permission_payloads():
        permission = db.query(AdminPermission).filter_by(key=payload["key"]).first()
        if not permission:
            permission = AdminPermission(**payload)
            db.add(permission)
        else:
            permission.label = payload["label"]
            permission.kind = payload["kind"]
            permission.group_key = payload["group_key"]
            permission.group_name = payload["group_name"]
            permission.description = payload["description"]
        permission_by_key[payload["key"]] = permission

    db.flush()

    role_by_code: dict[str, AdminRole] = {}
    for role_seed in DEFAULT_ROLE_SEEDS:
        role = db.query(AdminRole).filter_by(code=role_seed.code).first()
        is_new_role = role is None
        if not role:
            role = AdminRole(
                code=role_seed.code,
                name=role_seed.name,
                description=role_seed.description,
                is_system=True,
                is_active=True,
            )
            db.add(role)
            db.flush()
        else:
            role.name = role_seed.name
            role.description = role_seed.description
            role.is_system = True
            role.is_active = True
        if is_new_role:
            role.permissions = [permission_by_key[key] for key in role_seed.permission_keys if key in permission_by_key]
        role_by_code[role.code] = role

    db.flush()

    admin_user = db.query(AdminUser).filter_by(username=DEFAULT_SUPER_ADMIN_USERNAME).first()
    if not admin_user:
        admin_user = AdminUser(
            username=DEFAULT_SUPER_ADMIN_USERNAME,
            password_hash=hash_password(DEFAULT_SUPER_ADMIN_PASSWORD),
            display_name="Super Admin",
            is_active=True,
            is_super_admin=True,
            session_nonce=generate_session_nonce(),
        )
        db.add(admin_user)
        db.flush()
    else:
        admin_user.display_name = admin_user.display_name or "Super Admin"
        admin_user.is_active = True
        admin_user.is_super_admin = True
        if not admin_user.session_nonce:
            admin_user.session_nonce = generate_session_nonce()

    super_admin_role = role_by_code.get("super_admin")
    if super_admin_role and super_admin_role not in admin_user.roles:
        admin_user.roles.append(super_admin_role)


def ensure_seed_data() -> None:
    db = SessionLocal()
    try:
        _seed_rbac(db)
        # Seed runtime config rows from current .env-derived values.
        from admin_backend.configs import ENV_CONFIG_FIELDS

        defaults = {field.key: getattr(Config, field.key) for field in ENV_CONFIG_FIELDS}
        seed_runtime_config_rows(defaults)
        _seed_bilibili_auth_state(db)

        default_push_target = db.query(PushTarget).filter_by(channel="feishu", is_default=True).first()
        if not default_push_target and Config.FEISHU_RECEIVE_ID and Config.FEISHU_RECEIVE_ID_TYPE:
            db.add(
                PushTarget(
                    channel="feishu",
                    name="默认飞书群",
                    receive_id=Config.FEISHU_RECEIVE_ID,
                    receive_id_type=Config.FEISHU_RECEIVE_ID_TYPE,
                    is_default=True,
                    is_active=True,
                    notes="Seeded from legacy .env Feishu target",
                )
            )
            db.commit()

        # Seed a default model profile from the legacy OpenAI-style env config.
        default_profile = db.query(LLMModelProfile).filter_by(is_default=True).first()
        if not default_profile and Config.OPENAI_API_KEY:
            default_profile = LLMModelProfile(
                name="Default Env Profile",
                provider="openai-compatible",
                base_url=Config.OPENAI_BASE_URL,
                api_key=Config.OPENAI_API_KEY,
                model_name=Config.OPENAI_MODEL or "gpt-3.5-turbo",
                is_default=True,
                is_active=True,
                notes="Seeded from .env configuration",
            )
            db.add(default_profile)
            db.commit()

        if not db.query(LLMModelProfile).first():
            db.add(
                LLMModelProfile(
                    name="Default Model",
                    provider="openai-compatible",
                    base_url="",
                    api_key="",
                    model_name="gpt-3.5-turbo",
                    is_default=True,
                    is_active=True,
                    notes="Created default empty profile",
                )
            )
            db.commit()

        docs_dir = get_install_root() / "docs"
        prompts_to_seed = [
            {
                "key": "video_summary",
                "name": "视频总结",
                "description": "用于视频内容总结",
                "path": "prompt.md",
                "fallback": "You are a content processing assistant. Return a single JSON object with keys: summary, details, key_points, stocks, insights.",
            },
            {
                "key": "dynamic_summary",
                "name": "动态总结",
                "description": "用于图文动态内容总结",
                "path": "prompt_dynamic.md",
                "fallback": "You are a content processing assistant. Return a single JSON object with keys: summary, details, key_points, stocks, insights.",
            },
            {
                "key": "podcast_summary",
                "name": "小宇宙总结",
                "description": "用于播客内容总结",
                "path": "prompt_podcast.md",
                "fallback": "You are a content processing assistant. Return a single JSON object with keys: summary, details, key_points, stocks, insights.",
            },
            {
                "key": "push_relevance",
                "name": "推送相关性判断",
                "description": "用于判断内容是否需要推送",
                "path": None,
                "fallback": _push_relevance_fallback_prompt,
            },
        ]

        for prompt_seed in prompts_to_seed:
            existing = db.query(PromptTemplate).filter_by(key=prompt_seed["key"]).first()
            if existing:
                continue

            if prompt_seed["path"]:
                try:
                    prompt_text = (docs_dir / prompt_seed["path"]).read_text(encoding="utf-8")
                except Exception:
                    fallback = prompt_seed["fallback"]
                    prompt_text = fallback() if callable(fallback) else str(fallback)
            else:
                fallback = prompt_seed["fallback"]
                prompt_text = fallback() if callable(fallback) else str(fallback)

            db.add(
                PromptTemplate(
                    key=prompt_seed["key"],
                    name=prompt_seed["name"],
                    description=prompt_seed["description"],
                    prompt_text=prompt_text,
                    is_active=True,
                )
            )

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # Make sure the current process sees the DB overrides immediately.
    load_runtime_config_overrides()
