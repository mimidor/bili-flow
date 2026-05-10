from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.database import PushTarget, Subscription, WeWeRssSubscription, get_db
from config import Config


def serialize_push_target_row(row: PushTarget) -> dict[str, Any]:
    return {
        "id": row.id,
        "channel": row.channel,
        "name": row.name,
        "receive_id": row.receive_id,
        "receive_id_type": row.receive_id_type,
        "is_default": bool(row.is_default),
        "is_active": bool(row.is_active),
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def get_default_push_target(db: Session, channel: str = "feishu") -> PushTarget | None:
    return (
        db.query(PushTarget)
        .filter(PushTarget.channel == channel, PushTarget.is_default.is_(True))
        .order_by(PushTarget.id.asc())
        .first()
    )


def get_push_target_by_id(db: Session, target_id: int, channel: str = "feishu") -> PushTarget | None:
    return (
        db.query(PushTarget)
        .filter(PushTarget.id == int(target_id), PushTarget.channel == channel)
        .first()
    )


def get_subscription_push_target(db: Session, mid: str, channel: str = "feishu") -> PushTarget | None:
    subscription = db.query(Subscription).filter(Subscription.mid == str(mid)).first()
    if not subscription or not subscription.push_target_id:
        return None
    return (
        db.query(PushTarget)
        .filter(PushTarget.id == subscription.push_target_id, PushTarget.channel == channel)
        .first()
    )


def get_wewe_subscription_push_target(db: Session, feed_id: str, channel: str = "feishu") -> PushTarget | None:
    subscription = db.query(WeWeRssSubscription).filter(WeWeRssSubscription.feed_id == str(feed_id)).first()
    if not subscription or not subscription.push_target_id:
        return None
    return (
        db.query(PushTarget)
        .filter(PushTarget.id == subscription.push_target_id, PushTarget.channel == channel)
        .first()
    )


def resolve_push_target(
    content_data: dict[str, Any],
    *,
    channel: str,
    db: Session | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    managed_db = db is None
    session = db or get_db()
    try:
        target_row: PushTarget | None = None
        if channel == "feishu" and content_data.get("type") in {"video", "dynamic"}:
            mid = content_data.get("mid")
            if mid:
                target_row = get_subscription_push_target(session, str(mid), channel=channel)
                if target_row and not target_row.is_active:
                    return None, f"push target '{target_row.name}' is disabled"
        elif channel == "feishu" and content_data.get("type") == "wewe_rss":
            feed_id = content_data.get("feed_id")
            if feed_id:
                target_row = get_wewe_subscription_push_target(session, str(feed_id), channel=channel)
                if target_row and not target_row.is_active:
                    return None, f"push target '{target_row.name}' is disabled"

        if target_row is None:
            target_row = get_default_push_target(session, channel=channel)
            if not target_row:
                if channel == "feishu" and Config.FEISHU_RECEIVE_ID and Config.FEISHU_RECEIVE_ID_TYPE:
                    return {
                        "id": None,
                        "channel": "feishu",
                        "name": "Legacy Default",
                        "receive_id": Config.FEISHU_RECEIVE_ID,
                        "receive_id_type": Config.FEISHU_RECEIVE_ID_TYPE,
                        "is_default": True,
                        "is_active": True,
                        "notes": "Fallback to legacy env config",
                        "created_at": None,
                        "updated_at": None,
                    }, None
                return None, f"default {channel} push target is not configured"
            if not target_row.is_active:
                return None, f"default {channel} push target '{target_row.name}' is disabled"

        return serialize_push_target_row(target_row), None
    finally:
        if managed_db:
            session.close()
