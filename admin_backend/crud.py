from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from admin_backend.rbac import ALL_PERMISSION_KEYS
from app.models.database import (
    AdminPermission,
    AdminRole,
    AdminUser,
    ClassificationRule,
    Dynamic,
    FolderMapping,
    LLMChatSession,
    LLMChatSessionTurn,
    LLMUsage,
    LLMModelProfile,
    ManualPushTask,
    PodcastEpisode,
    PodcastSubscription,
    PushHistory,
    PushTarget,
    WeWeRssArticle,
    WeWeRssSubscription,
    Subscription,
    Video,
)


def serialize_admin_permission(row: AdminPermission) -> dict[str, Any]:
    return {
        "id": row.id,
        "key": row.key,
        "label": row.label,
        "kind": row.kind,
        "group_key": row.group_key,
        "group_name": row.group_name,
        "description": row.description,
    }


def serialize_admin_role(row: AdminRole) -> dict[str, Any]:
    permissions = sorted(row.permissions, key=lambda item: item.key)
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "description": row.description,
        "is_system": row.is_system,
        "is_active": row.is_active,
        "permissions": [serialize_admin_permission(permission) for permission in permissions],
        "permission_keys": [permission.key for permission in permissions],
        "user_count": len(row.users),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_admin_user(row: AdminUser, permission_keys: list[str] | None = None) -> dict[str, Any]:
    sorted_roles = sorted(row.roles, key=lambda item: item.code)
    resolved_permissions = permission_keys
    if resolved_permissions is None:
        permission_set = {permission.key for role in sorted_roles for permission in role.permissions}
        resolved_permissions = sorted(permission_set)
    if row.is_super_admin:
        resolved_permissions = sorted(set(resolved_permissions) | set(ALL_PERMISSION_KEYS))
    menu_keys = sorted(key for key in resolved_permissions if key.startswith("menu."))
    return {
        "id": row.id,
        "username": row.username,
        "display_name": row.display_name,
        "is_active": row.is_active,
        "is_super_admin": row.is_super_admin,
        "roles": [{"id": role.id, "code": role.code, "name": role.name} for role in sorted_roles],
        "permissions": resolved_permissions,
        "menu_keys": menu_keys,
        "last_login_at": row.last_login_at.isoformat() if row.last_login_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _loads_json(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


def _loads_json_list(value: str | None) -> list[Any]:
    loaded = _loads_json(value)
    return loaded if isinstance(loaded, list) else []


def _with_detail_fields(payload: dict[str, Any], row: Any, fields: dict[str, Any]) -> dict[str, Any]:
    for field_name, loader in fields.items():
      payload[field_name] = loader(getattr(row, field_name))
    return payload


def paginate_query(query, page: int, page_size: int):
    total = query.order_by(None).count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return total, items


def serialize_video(video: Video, uploader_name: str | None = None) -> dict[str, Any]:
    summary = _loads_json(video.summary_json) or {}
    display_uploader_name = uploader_name or f"UP主_{video.mid}"
    return {
        "id": video.id,
        "bvid": video.bvid,
        "title": video.title,
        "mid": video.mid,
        "uploader_name": display_uploader_name,
        "pub_time": video.pub_time,
        "has_subtitle": video.has_subtitle,
        "has_video": video.has_video,
        "has_audio": video.has_audio,
        "subtitle_path": video.subtitle_path,
        "video_path": video.video_path,
        "audio_path": video.audio_path,
        "status": video.status,
        "attempt_count": video.attempt_count,
        "last_error": video.last_error,
        "summary_json": summary,
        "doc_url": video.doc_url,
        "created_at": video.created_at.isoformat() if video.created_at else None,
        "updated_at": video.updated_at.isoformat() if video.updated_at else None,
    }


def serialize_video_detail(video: Video, uploader_name: str | None = None) -> dict[str, Any]:
    payload = serialize_video(video, uploader_name=uploader_name)
    payload["transcript_text"] = video.transcript_text
    return payload


def serialize_dynamic(dynamic: Dynamic, uploader_name: str | None = None) -> dict[str, Any]:
    summary = _loads_json(dynamic.summary_json) or {}
    image_urls = _loads_json(dynamic.image_urls) or []
    images_path = _loads_json(dynamic.images_path) or []
    display_uploader_name = uploader_name or f"UP主_{dynamic.mid}"
    return {
        "id": dynamic.id,
        "dynamic_id": dynamic.dynamic_id,
        "mid": dynamic.mid,
        "uploader_name": display_uploader_name,
        "type": dynamic.type,
        "text": dynamic.text,
        "image_count": dynamic.image_count,
        "images_path": images_path,
        "image_urls": image_urls,
        "summary_json": summary,
        "doc_url": dynamic.doc_url,
        "status": dynamic.status,
        "push_status": dynamic.push_status,
        "pub_time": dynamic.pub_time.isoformat() if dynamic.pub_time else None,
        "pushed_at": dynamic.pushed_at.isoformat() if dynamic.pushed_at else None,
        "attempt_count": dynamic.attempt_count,
        "last_error": dynamic.last_error,
        "created_at": dynamic.created_at.isoformat() if dynamic.created_at else None,
        "updated_at": dynamic.updated_at.isoformat() if dynamic.updated_at else None,
    }


def serialize_push_history(row: PushHistory) -> dict[str, Any]:
    return {
        "id": row.id,
        "content_type": row.content_type,
        "content_id": row.content_id,
        "content_title": row.content_title,
        "uploader_name": row.uploader_name,
        "channel": row.channel,
        "target_id": row.target_id,
        "target_name": row.target_name,
        "target_receive_id": row.target_receive_id,
        "status": row.status,
        "error_message": row.error_message,
        "response_summary": row.response_summary,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_push_history_detail(row: PushHistory) -> dict[str, Any]:
    return _with_detail_fields(
        serialize_push_history(row),
        row,
        {
            "request_payload": _loads_json,
            "response_payload": _loads_json,
        },
    )


def serialize_llm_usage(row: LLMUsage) -> dict[str, Any]:
    return {
        "id": row.id,
        "content_type": row.content_type,
        "content_id": row.content_id,
        "content_title": row.content_title,
        "uploader_name": row.uploader_name,
        "provider": row.provider,
        "model": row.model,
        "web_search_enabled": bool(getattr(row, "web_search_enabled", False)),
        "web_search_mode": getattr(row, "web_search_mode", None),
        "web_search_used": bool(getattr(row, "web_search_used", False)),
        "web_search_fallback_reason": getattr(row, "web_search_fallback_reason", None),
        "prompt_tokens": row.prompt_tokens,
        "completion_tokens": row.completion_tokens,
        "total_tokens": row.total_tokens,
        "duration_ms": row.duration_ms,
        "success": row.success,
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_llm_usage_detail(row: LLMUsage) -> dict[str, Any]:
    return _with_detail_fields(serialize_llm_usage(row), row, {"raw_response": _loads_json})


def serialize_llm_profile(row: LLMModelProfile) -> dict[str, Any]:
    from app.utils.llm_client import resolve_web_search_mode

    mode = resolve_web_search_mode(row)
    return {
        "id": row.id,
        "name": row.name,
        "provider": row.provider,
        "base_url": row.base_url,
        "model_name": row.model_name,
        "enable_web_search": bool(getattr(row, "enable_web_search", False)),
        "enable_reasoning": bool(getattr(row, "enable_reasoning", False)),
        "enable_image": bool(getattr(row, "enable_image", False)),
        "enable_tools": bool(getattr(row, "enable_tools", False)),
        "web_search_mode": mode,
        "web_search_supported": mode in {"chat_completions", "responses"},
        "is_default": row.is_default,
        "is_active": row.is_active,
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_llm_profile_detail(row: LLMModelProfile) -> dict[str, Any]:
    return _with_detail_fields(serialize_llm_profile(row), row, {"api_key": lambda value: value})


def serialize_llm_chat_session(row: LLMChatSession) -> dict[str, Any]:
    return {
        "id": row.id,
        "session_key": row.session_key,
        "title": row.title,
        "source": row.source,
        "model_ids": _loads_json_list(row.model_ids_json),
        "system_prompt": row.system_prompt or "",
        "temperature": float(row.temperature if row.temperature is not None else 0.3),
        "max_tokens": int(row.max_tokens if row.max_tokens is not None else 2048),
        "turns_count": int(row.turns_count or 0),
        "last_turn_at": row.last_turn_at.isoformat() if row.last_turn_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_llm_chat_session_turn(row: LLMChatSessionTurn) -> dict[str, Any]:
    return {
        "id": row.id,
        "session_id": row.session_id,
        "turn_index": row.turn_index,
        "source": row.source,
        "user_prompt": row.user_prompt,
        "model_results": _loads_json_list(row.model_results_json),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_manual_push_task(row: ManualPushTask) -> dict[str, Any]:
    source_type = getattr(row, "source_type", None) or "bilibili"
    return {
        "id": row.id,
        "bvid": row.bvid,
        "source_type": source_type,
        "source_path": getattr(row, "source_path", None),
        "title": row.title,
        "uploader_name": row.uploader_name,
        "source_video_id": row.source_video_id,
        "status": row.status,
        "stage": row.stage,
        "progress": int(row.progress or 0),
        "message": row.message,
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "source_url": None if source_type == "local_video" else f"https://www.bilibili.com/video/{row.bvid}",
    }


def serialize_manual_push_task_detail(row: ManualPushTask) -> dict[str, Any]:
    return _with_detail_fields(serialize_manual_push_task(row), row, {"result_json": _loads_json})


def serialize_subscription(row: Subscription) -> dict[str, Any]:
    return {
        "id": row.id,
        "mid": row.mid,
        "name": row.name,
        "homepage_url": row.homepage_url,
        "last_video_bvid": row.last_video_bvid,
        "last_dynamic_id": row.last_dynamic_id,
        "last_check_time": row.last_check_time.isoformat() if row.last_check_time else None,
        "push_target_id": row.push_target_id,
        "is_active": row.is_active,
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_push_target(row: PushTarget) -> dict[str, Any]:
    return {
        "id": row.id,
        "channel": row.channel,
        "name": row.name,
        "receive_id": row.receive_id,
        "receive_id_type": row.receive_id_type,
        "is_default": row.is_default,
        "is_active": row.is_active,
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_podcast_subscription(row: PodcastSubscription) -> dict[str, Any]:
    return {
        "id": row.id,
        "pid": row.pid,
        "name": row.name,
        "homepage_url": row.homepage_url,
        "last_episode_eid": row.last_episode_eid,
        "last_episode_pub_time": row.last_episode_pub_time.isoformat() if row.last_episode_pub_time else None,
        "last_response_cursor_json": _loads_json(row.last_response_cursor_json),
        "bootstrap_recent_episodes": row.bootstrap_recent_episodes,
        "last_check_time": row.last_check_time.isoformat() if row.last_check_time else None,
        "last_success_time": row.last_success_time.isoformat() if row.last_success_time else None,
        "consecutive_failures": row.consecutive_failures,
        "is_active": row.is_active,
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_podcast_episode(row: PodcastEpisode) -> dict[str, Any]:
    return {
        "id": row.id,
        "eid": row.eid,
        "pid": row.pid,
        "title": row.title,
        "pub_time": row.pub_time.isoformat() if row.pub_time else None,
        "audio_url": row.audio_url,
        "audio_mime": row.audio_mime,
        "audio_size": row.audio_size,
        "raw_episode_json": _loads_json(row.raw_episode_json),
        "local_audio_path": row.local_audio_path,
        "local_transcript_path": row.local_transcript_path,
        "local_summary_path": row.local_summary_path,
        "transcript_text": row.transcript_text,
        "summary_json": _loads_json(row.summary_json),
        "doc_url": row.doc_url,
        "status": row.status,
        "push_status": row.push_status,
        "download_attempts": row.download_attempts,
        "asr_attempts": row.asr_attempts,
        "summary_attempts": row.summary_attempts,
        "attempt_count": row.attempt_count,
        "last_error": row.last_error,
        "discovered_at": row.discovered_at.isoformat() if row.discovered_at else None,
        "downloaded_at": row.downloaded_at.isoformat() if row.downloaded_at else None,
        "transcribed_at": row.transcribed_at.isoformat() if row.transcribed_at else None,
        "summarized_at": row.summarized_at.isoformat() if row.summarized_at else None,
        "pushed_at": row.pushed_at.isoformat() if row.pushed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_wewe_subscription(row: WeWeRssSubscription) -> dict[str, Any]:
    return {
        "id": row.id,
        "feed_id": row.feed_id,
        "name": row.name,
        "homepage_url": row.homepage_url,
        "feed_format": row.feed_format,
        "push_target_id": row.push_target_id,
        "last_entry_id": row.last_entry_id,
        "last_entry_pub_time": row.last_entry_pub_time.isoformat() if row.last_entry_pub_time else None,
        "last_response_cursor_json": _loads_json(row.last_response_cursor_json),
        "bootstrap_recent_items": row.bootstrap_recent_items,
        "last_check_time": row.last_check_time.isoformat() if row.last_check_time else None,
        "last_success_time": row.last_success_time.isoformat() if row.last_success_time else None,
        "consecutive_failures": row.consecutive_failures,
        "is_active": row.is_active,
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_wewe_article(row: WeWeRssArticle) -> dict[str, Any]:
    return {
        "id": row.id,
        "entry_id": row.entry_id,
        "feed_id": row.feed_id,
        "title": row.title,
        "author": row.author,
        "link": row.link,
        "pub_time": row.pub_time.isoformat() if row.pub_time else None,
        "content_text": row.content_text,
        "content_html": row.content_html,
        "raw_entry_json": _loads_json(row.raw_entry_json),
        "status": row.status,
        "push_status": row.push_status,
        "attempt_count": int(row.attempt_count or 0),
        "last_error": row.last_error,
        "discovered_at": row.discovered_at.isoformat() if row.discovered_at else None,
        "pushed_at": row.pushed_at.isoformat() if row.pushed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "source_url": row.link,
    }


def serialize_rule(row: ClassificationRule) -> dict[str, Any]:
    return {
        "id": row.id,
        "uploader_name": row.uploader_name,
        "pattern": row.pattern,
        "target_folder": row.target_folder,
        "priority": row.priority,
        "is_active": row.is_active,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_folder_mapping(row: FolderMapping) -> dict[str, Any]:
    return {
        "id": row.id,
        "uploader_name": row.uploader_name,
        "category": row.category,
        "folder_token": row.folder_token,
        "folder_path": row.folder_path,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def get_uploader_name_map(db: Session, mids: list[str]) -> dict[str, str]:
    if not mids:
        return {}
    rows = db.query(Subscription.mid, Subscription.name).filter(Subscription.mid.in_(mids)).all()
    return {mid: name for mid, name in rows}


def get_podcast_name_map(db: Session, pids: list[str]) -> dict[str, str]:
    if not pids:
        return {}
    rows = db.query(PodcastSubscription.pid, PodcastSubscription.name).filter(PodcastSubscription.pid.in_(pids)).all()
    return {pid: name for pid, name in rows}


def token_overview(db: Session) -> dict[str, int]:
    totals = db.query(
        func.coalesce(func.sum(LLMUsage.total_tokens), 0),
        func.coalesce(func.sum(LLMUsage.prompt_tokens), 0),
        func.coalesce(func.sum(LLMUsage.completion_tokens), 0),
    ).one()
    return {
        "total_tokens": int(totals[0] or 0),
        "prompt_tokens": int(totals[1] or 0),
        "completion_tokens": int(totals[2] or 0),
    }
