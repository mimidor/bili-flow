from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.models.database import LLMUsage, PushHistory, get_db


def _json_safe(value: Any, max_len: int = 8000) -> str | None:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            text = value
        else:
            text = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        text = str(value)
    if len(text) > max_len:
        text = text[:max_len] + "..."
    return text


def record_push_history(
    *,
    content_type: str,
    content_id: str,
    channel: str,
    status: str,
    content_title: str | None = None,
    uploader_name: str | None = None,
    target_id: int | None = None,
    target_name: str | None = None,
    target_receive_id: str | None = None,
    error_message: str | None = None,
    response_summary: str | None = None,
    request_payload: Any = None,
    response_payload: Any = None,
) -> None:
    db = get_db()
    try:
        row = PushHistory(
            content_type=content_type,
            content_id=content_id,
            content_title=content_title,
            uploader_name=uploader_name,
            channel=channel,
            target_id=target_id,
            target_name=target_name,
            target_receive_id=target_receive_id,
            status=status,
            error_message=error_message,
            response_summary=response_summary,
            request_payload=_json_safe(request_payload),
            response_payload=_json_safe(response_payload),
        )
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def record_llm_usage(
    *,
    content_type: str | None,
    content_id: str | None,
    content_title: str | None,
    uploader_name: str | None,
    provider: str,
    model: str | None,
    web_search_enabled: bool | None = None,
    web_search_mode: str | None = None,
    web_search_used: bool | None = None,
    web_search_fallback_reason: str | None = None,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    total_tokens: int | None,
    duration_ms: int | None,
    success: bool,
    error_message: str | None = None,
    raw_response: Any = None,
) -> None:
    db = get_db()
    try:
        row = LLMUsage(
            content_type=content_type,
            content_id=content_id,
            content_title=content_title,
            uploader_name=uploader_name,
            provider=provider,
            model=model,
            web_search_enabled=web_search_enabled,
            web_search_mode=web_search_mode,
            web_search_used=web_search_used,
            web_search_fallback_reason=web_search_fallback_reason,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
            success=success,
            error_message=error_message,
            raw_response=_json_safe(raw_response),
            created_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
