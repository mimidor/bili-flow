from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.database import WeWeRssArticle, WeWeRssSubscription, get_db
from app.modules.wewe_rss import WeWeFeedEntry, WeWeFeedInfo, WeWeRssClient, WeWeRssError, build_feed_urls
from app.modules.push_channels import push_content
from app.services.push_targets import resolve_push_target
from config import Config


def serialize_wewe_subscription(row: WeWeRssSubscription) -> dict[str, Any]:
    return {
        "id": row.id,
        "feed_id": row.feed_id,
        "name": row.name,
        "feed_format": row.feed_format,
        "homepage_url": row.homepage_url,
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


def _loads_json(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


def _get_client(base_url: str | None = None) -> WeWeRssClient:
    return WeWeRssClient(base_url or Config.WEWE_RSS_BASE_URL, auth_code=Config.WEWE_RSS_AUTH_CODE)


def fetch_feed_catalog(*, base_url: str | None = None) -> list[WeWeFeedInfo]:
    client = _get_client(base_url)
    try:
        return client.list_feeds()
    finally:
        client.close()


def sync_subscription_articles(
    db: Session,
    subscription: WeWeRssSubscription,
    *,
    manual_update: bool = False,
    max_pages: int = 5,
    page_limit: int = 20,
) -> dict[str, Any]:
    client = _get_client()
    discovered_entries: list[WeWeFeedEntry] = []
    last_entry_id = (subscription.last_entry_id or "").strip()
    bootstrap_limit = int(subscription.bootstrap_recent_items or 3)
    feed_format = (subscription.feed_format or "atom").strip().lower() or "atom"
    latest_entry: WeWeFeedEntry | None = None
    found_last_seen = False
    error: str | None = None

    try:
        for page in range(1, max_pages + 1):
            entries = client.fetch_feed_entries(
                subscription.feed_id,
                format=feed_format,
                limit=page_limit,
                page=page,
                mode="fulltext",
                update=manual_update and page == 1,
            )
            if not entries:
                break
            if latest_entry is None:
                latest_entry = entries[0]
            if not last_entry_id:
                discovered_entries.extend(entries[: max(bootstrap_limit, 0)])
                break
            for entry in entries:
                if entry.entry_id == last_entry_id:
                    found_last_seen = True
                    break
                discovered_entries.append(entry)
            if found_last_seen or len(entries) < page_limit:
                break
        discovered_entries.sort(key=lambda item: item.pub_date or datetime.min)

        new_count = 0
        pushed_count = 0
        failed_count = 0
        skipped_count = 0

        for entry in discovered_entries:
            existing = db.query(WeWeRssArticle).filter(WeWeRssArticle.entry_id == entry.entry_id).first()
            if existing:
                continue

            article = WeWeRssArticle(
                entry_id=entry.entry_id,
                feed_id=subscription.feed_id,
                title=entry.title,
                author=entry.author,
                link=entry.link,
                pub_time=entry.pub_date,
                content_text=entry.content_text,
                content_html=entry.content_html,
                raw_entry_json=json.dumps(entry.raw, ensure_ascii=False, default=str),
                status="processing",
                push_status="processing",
                discovered_at=datetime.utcnow(),
            )
            db.add(article)
            db.flush()
            new_count += 1

            push_payload = {
                "type": "wewe_rss",
                "content_id": entry.entry_id,
                "wewe_subscription_id": subscription.id,
                "feed_id": subscription.feed_id,
                "feed_name": subscription.name,
                "uploader_name": subscription.name,
                "title": entry.title,
                "text": entry.content_text or entry.title,
                "summary": "",
                "details": "",
                "key_points": [],
                "tags": [],
                "stocks": [],
                "insights": "",
                "pub_time": entry.pub_date or "",
                "url": entry.link,
                "source_url": entry.link,
            }
            target_meta, target_error = resolve_push_target(push_payload, channel="feishu", db=db)
            if target_error:
                article.status = "failed"
                article.push_status = "failed"
                article.last_error = target_error
                failed_count += 1
                continue
            push_payload["push_target"] = target_meta
            push_result = push_content(push_payload, ["feishu"])
            if push_result.get("silented"):
                article.status = "skipped"
                article.push_status = "skipped"
                article.last_error = push_result.get("reason")
                skipped_count += 1
            elif push_result.get("success"):
                article.status = "sent"
                article.push_status = "success"
                article.pushed_at = datetime.utcnow()
                article.last_error = None
                pushed_count += 1
            else:
                article.status = "failed"
                article.push_status = "failed"
                article.last_error = str(push_result.get("reason") or "push failed")
                failed_count += 1

        if latest_entry:
            subscription.last_entry_id = latest_entry.entry_id
            subscription.last_entry_pub_time = latest_entry.pub_date
        subscription.last_check_time = datetime.utcnow()
        subscription.last_success_time = datetime.utcnow()
        subscription.consecutive_failures = 0
        if discovered_entries:
            subscription.last_response_cursor_json = json.dumps(
                {
                    "feed_format": feed_format,
                    "manual_update": manual_update,
                    "bootstrap_limit": bootstrap_limit,
                    "pages": min(max_pages, len(discovered_entries)),
                    "last_seen_entry_id": last_entry_id,
                },
                ensure_ascii=False,
            )
        db.commit()
        return {
            "success": True,
            "new_count": new_count,
            "pushed_count": pushed_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "latest_entry_id": latest_entry.entry_id if latest_entry else None,
            "error": None,
        }
    except WeWeRssError as exc:
        error = str(exc)
        subscription.consecutive_failures = int(subscription.consecutive_failures or 0) + 1
        subscription.last_check_time = datetime.utcnow()
        db.commit()
        return {
            "success": False,
            "new_count": 0,
            "pushed_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "latest_entry_id": None,
            "error": error,
        }
    except Exception as exc:
        error = str(exc)
        subscription.consecutive_failures = int(subscription.consecutive_failures or 0) + 1
        subscription.last_check_time = datetime.utcnow()
        db.commit()
        return {
            "success": False,
            "new_count": 0,
            "pushed_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "latest_entry_id": None,
            "error": error,
        }
    finally:
        client.close()


def sync_active_subscriptions(*, db: Session | None = None, manual_update_ids: set[int] | None = None) -> dict[str, Any]:
    managed_db = db is None
    session = db or get_db()
    try:
        manual_update_ids = manual_update_ids or set()
        subscriptions = session.query(WeWeRssSubscription).filter(WeWeRssSubscription.is_active.is_(True)).all()
        results: list[dict[str, Any]] = []
        new_count = 0
        pushed_count = 0
        failed_count = 0
        skipped_count = 0
        for subscription in subscriptions:
            result = sync_subscription_articles(
                session,
                subscription,
                manual_update=subscription.id in manual_update_ids,
            )
            results.append({"subscription_id": subscription.id, "feed_id": subscription.feed_id, **result})
            new_count += int(result["new_count"] or 0)
            pushed_count += int(result["pushed_count"] or 0)
            failed_count += int(result["failed_count"] or 0)
            skipped_count += int(result["skipped_count"] or 0)
        return {
            "success": True,
            "results": results,
            "new_count": new_count,
            "pushed_count": pushed_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
        }
    finally:
        if managed_db:
            session.close()


def build_feed_info_dict(feed: WeWeFeedInfo) -> dict[str, Any]:
    urls = build_feed_urls(Config.WEWE_RSS_BASE_URL, feed.feed_id)
    return {
        "feed_id": feed.feed_id,
        "title": feed.title,
        "homepage_url": feed.homepage_url or urls["homepage_url"],
        "atom_url": feed.atom_url or urls["atom_url"],
        "rss_url": feed.rss_url or urls["rss_url"],
        "json_url": feed.json_url or urls["json_url"],
        "raw": feed.raw,
    }
