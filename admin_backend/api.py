from __future__ import annotations

import json
from datetime import datetime, timedelta
from threading import Thread

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from admin_backend.crud import (
    get_uploader_name_map,
    get_podcast_name_map,
    paginate_query,
    serialize_dynamic,
    serialize_folder_mapping,
    serialize_podcast_episode,
    serialize_podcast_subscription,
    serialize_llm_usage_detail,
    serialize_llm_usage,
    serialize_push_history_detail,
    serialize_push_history,
    serialize_push_target,
    serialize_rule,
    serialize_subscription,
    serialize_video,
    serialize_video_detail,
    serialize_wewe_article,
    serialize_wewe_subscription,
    token_overview,
)
from admin_backend.configs import list_env_config_items, update_env_config
from admin_backend.deps import get_session
from admin_backend.log_reader import get_log_detail, query_logs
from admin_backend.schemas import (
    BatchActiveUpdate,
    BatchIdsRequest,
    BatchStatusUpdate,
    ClassificationRuleCreate,
    ClassificationRuleUpdate,
    EnvConfigResponse,
    EnvConfigUpdateRequest,
    FolderMappingCreate,
    FolderMappingUpdate,
    OverviewResponse,
    TaskListResponse,
    TaskOverviewResponse,
    TaskAcceptedResponse,
    ManualPushTaskCreateRequest,
    ManualPushTaskCreateResponse,
    ManualPushTaskItem,
    ManualPushTaskListResponse,
    TaskRunResponse,
    TaskRetryRequest,
    TaskRetryResponse,
    TaskRuntimeUpdateRequest,
    TaskRuntimeUpdateResponse,
    RetryResponse,
    StatusUpdate,
    PodcastSubscriptionCreate,
    PodcastSubscriptionUpdate,
    WeWeRssArticleItem,
    WeWeRssFeedItem,
    WeWeRssSubscriptionCreate,
    WeWeRssSubscriptionUpdate,
    PushTargetCreate,
    PushTargetUpdate,
    SubscriptionCreate,
    SubscriptionUpdate,
)
from app.models.database import (
    ClassificationRule,
    Dynamic,
    FolderMapping,
    LLMUsage,
    PodcastEpisode,
    PodcastSubscription,
    PushHistory,
    PushTarget,
    Subscription,
    TaskRuntimeState,
    ManualPushTask,
    Video,
    WeWeRssArticle,
    WeWeRssSubscription,
)
from app.modules.wewe_rss import WeWeRssClient, WeWeRssError, build_feed_urls
from config import Config
from app.utils.init import reset_stuck_tasks
from app.utils.logger import get_logger
from app.utils.task_runtime import (
    QUEUE_WORKER_COMPONENT,
    SCHEDULER_COMPONENT,
    ensure_runtime_states,
    serialize_runtime_state,
    set_runtime_pause,
    touch_runtime_state,
)

router = APIRouter()
logger = get_logger("admin_backend")


def check_new_videos() -> None:
    from app.scheduler import check_new_videos as _check_new_videos

    _check_new_videos()


def check_new_dynamics() -> None:
    from app.scheduler import check_new_dynamics as _check_new_dynamics

    _check_new_dynamics()


def check_new_podcast_episodes() -> None:
    from app.scheduler import check_new_podcast_episodes as _check_new_podcast_episodes

    _check_new_podcast_episodes()


def process_single_video(bvid: str) -> None:
    from app.queue_worker import process_single_video as _process_single_video

    _process_single_video(bvid)


def process_single_dynamic(dynamic_id: str) -> None:
    from app.queue_worker import process_single_dynamic as _process_single_dynamic

    _process_single_dynamic(dynamic_id)


def process_single_podcast_episode(eid: str) -> None:
    from app.queue_worker import process_single_podcast_episode as _process_single_podcast_episode

    _process_single_podcast_episode(eid)


def normalize_bvid(raw_bvid: str) -> str:
    from app.services.manual_push_tasks import normalize_bvid as _normalize_bvid

    return _normalize_bvid(raw_bvid)


def create_manual_push_task(bvid: str, push_target_id: int | None = None):
    from app.services.manual_push_tasks import create_manual_push_task as _create_manual_push_task

    return _create_manual_push_task(bvid, push_target_id=push_target_id)


def get_manual_push_task(task_id: int):
    from app.services.manual_push_tasks import get_manual_push_task as _get_manual_push_task

    return _get_manual_push_task(task_id)


def list_manual_push_tasks(*, page: int, page_size: int, q: str | None = None, status: str | None = None):
    from app.services.manual_push_tasks import list_manual_push_tasks as _list_manual_push_tasks

    return _list_manual_push_tasks(page=page, page_size=page_size, q=q, status=status)


def serialize_manual_push_task(row, db: Session | None = None):
    from app.services.manual_push_tasks import serialize_manual_push_task as _serialize_manual_push_task

    return _serialize_manual_push_task(row, db=db)


def serialize_manual_push_task_detail(row, db: Session | None = None):
    from app.services.manual_push_tasks import serialize_manual_push_task_detail as _serialize_manual_push_task_detail

    return _serialize_manual_push_task_detail(row, db=db)


def spawn_manual_push_task(task_id: int):
    from app.services.manual_push_tasks import spawn_manual_push_task as _spawn_manual_push_task

    return _spawn_manual_push_task(task_id)


def _ensure_push_target_exists(db: Session, push_target_id: int | None) -> PushTarget | None:
    if not push_target_id:
        return None
    row = db.query(PushTarget).filter(PushTarget.id == push_target_id, PushTarget.channel == "feishu").first()
    if not row:
        raise HTTPException(status_code=400, detail="push target not found")
    return row


def _normalize_wewe_feed_format(value: str | None) -> str:
    normalized = (value or "atom").strip().lower() or "atom"
    if normalized not in {"atom", "rss", "json"}:
        raise HTTPException(status_code=400, detail="feed_format must be atom, rss, or json")
    return normalized


def _set_default_push_target(db: Session, target: PushTarget) -> None:
    db.query(PushTarget).filter(
        PushTarget.channel == target.channel,
        PushTarget.id != target.id,
    ).update({"is_default": False}, synchronize_session=False)
    target.is_default = True
    target.is_active = True


def _loads_json(value: str | None) -> object:
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return value


def _iso_datetime(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (int, float)):
        try:
            return datetime.utcfromtimestamp(int(value)).isoformat()
        except Exception:
            return str(value)
    return str(value)


def _summary_excerpt(summary_json: str | None, fallback: str | None = None, limit: int = 160) -> str | None:
    data = _loads_json(summary_json)
    text = ""
    if isinstance(data, dict):
        text = str(data.get("summary") or data.get("details") or "")
    if not text:
        text = fallback or ""
    text = text.strip()
    if not text:
        return None
    return text[:limit] + ("..." if len(text) > limit else "")


def _task_sort_value(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.utcfromtimestamp(int(value))
        except Exception:
            return datetime.min
    return datetime.min


def _build_video_task_item(video: Video, uploader_name: str) -> dict[str, object]:
    return {
        "id": video.id,
        "content_type": "video",
        "content_id": video.bvid,
        "title": video.title,
        "uploader_name": uploader_name,
        "status": video.status,
        "push_status": None,
        "attempt_count": int(video.attempt_count or 0),
        "last_error": video.last_error,
        "pub_time": _iso_datetime(video.pub_time),
        "created_at": _iso_datetime(video.created_at),
        "updated_at": _iso_datetime(video.updated_at),
        "source_url": f"https://www.bilibili.com/video/{video.bvid}",
        "doc_url": video.doc_url,
        "summary_excerpt": _summary_excerpt(video.summary_json, video.transcript_text or video.title),
        "_sort_time": _task_sort_value(video.updated_at or video.created_at),
    }


def _build_dynamic_task_item(dynamic: Dynamic, uploader_name: str) -> dict[str, object]:
    title = (dynamic.text or "").strip() or dynamic.dynamic_id
    return {
        "id": dynamic.id,
        "content_type": "dynamic",
        "content_id": dynamic.dynamic_id,
        "title": title,
        "uploader_name": uploader_name,
        "status": dynamic.status,
        "push_status": dynamic.push_status,
        "attempt_count": int(dynamic.attempt_count or 0),
        "last_error": dynamic.last_error,
        "pub_time": _iso_datetime(dynamic.pub_time),
        "created_at": _iso_datetime(dynamic.created_at),
        "updated_at": _iso_datetime(dynamic.updated_at),
        "source_url": f"https://www.bilibili.com/opus/{dynamic.dynamic_id}",
        "doc_url": dynamic.doc_url,
        "summary_excerpt": _summary_excerpt(dynamic.summary_json, dynamic.text),
        "_sort_time": _task_sort_value(dynamic.updated_at or dynamic.created_at),
    }


def _build_podcast_task_item(episode: PodcastEpisode, podcast_name: str) -> dict[str, object]:
    title = (episode.title or "").strip() or episode.eid
    return {
        "id": episode.id,
        "content_type": "podcast",
        "content_id": episode.eid,
        "title": title,
        "uploader_name": podcast_name,
        "status": episode.status,
        "push_status": episode.push_status,
        "attempt_count": int(episode.attempt_count or 0),
        "last_error": episode.last_error,
        "pub_time": _iso_datetime(episode.pub_time),
        "created_at": _iso_datetime(episode.created_at),
        "updated_at": _iso_datetime(episode.updated_at),
        "source_url": f"https://www.xiaoyuzhoufm.com/episode/{episode.eid}",
        "doc_url": episode.doc_url,
        "summary_excerpt": _summary_excerpt(episode.summary_json, episode.transcript_text or episode.title),
        "_sort_time": _task_sort_value(episode.updated_at or episode.created_at),
    }


def _filter_task_status(status: str | None) -> set[str] | None:
    if not status or status == "all":
        return {"pending", "processing", "failed", "silented"}
    return {status}


def _collect_task_rows(
    db: Session,
    *,
    content_type: str | None = None,
    status: str | None = None,
    q: str | None = None,
    uploader_name: str | None = None,
    pub_after: datetime | None = None,
    pub_before: datetime | None = None,
) -> list[dict[str, object]]:
    status_filter = _filter_task_status(status)
    rows: list[dict[str, object]] = []

    include_videos = content_type in (None, "", "all", "video")
    include_dynamics = content_type in (None, "", "all", "dynamic")
    include_podcasts = content_type in (None, "", "all", "podcast")

    if include_videos:
        query = db.query(Video, Subscription.name.label("uploader_name")).outerjoin(
            Subscription, Subscription.mid == Video.mid
        )
        if status_filter:
            query = query.filter(Video.status.in_(status_filter))
        if q:
            pattern = f"%{q}%"
            query = query.filter(
                or_(
                    Video.title.ilike(pattern),
                    Video.bvid.ilike(pattern),
                    Subscription.name.ilike(pattern),
                    Video.last_error.ilike(pattern),
                )
            )
        if uploader_name:
            query = query.filter(Subscription.name.ilike(f"%{uploader_name}%"))
        if pub_after is not None:
            query = query.filter(Video.pub_time >= int(pub_after.timestamp()))
        if pub_before is not None:
            query = query.filter(Video.pub_time <= int(pub_before.timestamp()))
        for video, name in query.all():
            rows.append(_build_video_task_item(video, name or ""))

    if include_dynamics:
        query = db.query(Dynamic, Subscription.name.label("uploader_name")).outerjoin(
            Subscription, Subscription.mid == Dynamic.mid
        )
        if status_filter:
            query = query.filter(Dynamic.status.in_(status_filter))
        if q:
            pattern = f"%{q}%"
            query = query.filter(
                or_(
                    Dynamic.dynamic_id.ilike(pattern),
                    Dynamic.text.ilike(pattern),
                    Subscription.name.ilike(pattern),
                    Dynamic.last_error.ilike(pattern),
                )
            )
        if uploader_name:
            query = query.filter(Subscription.name.ilike(f"%{uploader_name}%"))
        if pub_after is not None:
            query = query.filter(Dynamic.pub_time >= pub_after)
        if pub_before is not None:
            query = query.filter(Dynamic.pub_time <= pub_before)
        for dynamic, name in query.all():
            rows.append(_build_dynamic_task_item(dynamic, name or ""))

    if include_podcasts:
        query = db.query(PodcastEpisode, PodcastSubscription.name.label("podcast_name")).outerjoin(
            PodcastSubscription, PodcastSubscription.pid == PodcastEpisode.pid
        )
        if status_filter:
            query = query.filter(PodcastEpisode.status.in_(status_filter))
        if q:
            pattern = f"%{q}%"
            query = query.filter(
                or_(
                    PodcastEpisode.eid.ilike(pattern),
                    PodcastEpisode.title.ilike(pattern),
                    PodcastSubscription.name.ilike(pattern),
                    PodcastEpisode.last_error.ilike(pattern),
                )
            )
        if uploader_name:
            query = query.filter(PodcastSubscription.name.ilike(f"%{uploader_name}%"))
        if pub_after is not None:
            query = query.filter(PodcastEpisode.pub_time >= pub_after)
        if pub_before is not None:
            query = query.filter(PodcastEpisode.pub_time <= pub_before)
        for episode, name in query.all():
            rows.append(_build_podcast_task_item(episode, name or ""))

    rows.sort(key=lambda item: item["_sort_time"], reverse=True)
    return rows


def _build_trend_window(db: Session, days: int) -> dict[str, list[dict[str, int | str]]]:
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start_date, datetime.min.time())

    push_rows = (
        db.query(
            func.date(PushHistory.created_at).label("day"),
            func.coalesce(
                func.sum(case((PushHistory.content_type == "video", 1), else_=0)),
                0,
            ).label("videos"),
            func.coalesce(
                func.sum(case((PushHistory.content_type == "dynamic", 1), else_=0)),
                0,
            ).label("dynamics"),
            func.coalesce(
                func.sum(case((PushHistory.content_type == "podcast", 1), else_=0)),
                0,
            ).label("podcasts"),
            func.count(PushHistory.id).label("pushes"),
        )
        .filter(PushHistory.created_at >= start_dt)
        .group_by(func.date(PushHistory.created_at))
        .all()
    )
    push_by_day = {str(row.day): row for row in push_rows}

    llm_rows = (
        db.query(
            func.date(LLMUsage.created_at).label("day"),
            func.count(LLMUsage.id).label("calls"),
            func.coalesce(func.sum(LLMUsage.total_tokens), 0).label("tokens"),
        )
        .filter(LLMUsage.created_at >= start_dt)
        .group_by(func.date(LLMUsage.created_at))
        .all()
    )
    llm_by_day = {str(row.day): row for row in llm_rows}

    push_days: list[dict[str, int | str]] = []
    llm_days: list[dict[str, int | str]] = []
    for offset in range(days):
        day = (start_date + timedelta(days=offset)).isoformat()
        push_row = push_by_day.get(day)
        llm_row = llm_by_day.get(day)
        push_days.append(
            {
                "day": day,
                "videos": int(getattr(push_row, "videos", 0) or 0),
                "dynamics": int(getattr(push_row, "dynamics", 0) or 0),
                "podcasts": int(getattr(push_row, "podcasts", 0) or 0),
                "pushes": int(getattr(push_row, "pushes", 0) or 0),
            }
        )
        llm_days.append(
            {
                "day": day,
                "calls": int(getattr(llm_row, "calls", 0) or 0),
                "tokens": int(getattr(llm_row, "tokens", 0) or 0),
            }
        )

    return {"push_days": push_days, "llm_days": llm_days}


def _build_health_metrics(db: Session) -> list[dict[str, int | float | str]]:
    def _metric(
        module: str,
        label: str,
        total_count: int,
        terminal_total: int,
        success_count: int,
        failure_count: int,
    ) -> dict[str, int | float | str]:
        success_rate = success_count / terminal_total if terminal_total else 0.0
        failure_rate = failure_count / terminal_total if terminal_total else 0.0
        return {
            "module": module,
            "label": label,
            "total_count": int(total_count),
            "terminal_total": int(terminal_total),
            "success_count": int(success_count),
            "failure_count": int(failure_count),
            "success_rate": success_rate,
            "failure_rate": failure_rate,
        }

    video_total = int(db.query(func.count(Video.id)).scalar() or 0)
    video_success = int(db.query(func.count(Video.id)).filter(Video.status == "done").scalar() or 0)
    video_failure = int(db.query(func.count(Video.id)).filter(Video.status == "failed").scalar() or 0)

    dynamic_total = int(db.query(func.count(Dynamic.id)).scalar() or 0)
    dynamic_success = int(db.query(func.count(Dynamic.id)).filter(Dynamic.status == "sent").scalar() or 0)
    dynamic_failure = int(
        db.query(func.count(Dynamic.id))
        .filter(Dynamic.status.in_(("filtered", "failed")))
        .scalar()
        or 0
    )

    podcast_total = int(db.query(func.count(PodcastEpisode.id)).scalar() or 0)
    podcast_success = int(db.query(func.count(PodcastEpisode.id)).filter(PodcastEpisode.status == "done").scalar() or 0)
    podcast_failure = int(
        db.query(func.count(PodcastEpisode.id))
        .filter(PodcastEpisode.status.in_(("failed", "failed_download", "failed_asr", "failed_summary")))
        .scalar()
        or 0
    )

    push_total = int(db.query(func.count(PushHistory.id)).scalar() or 0)
    push_success = int(db.query(func.count(PushHistory.id)).filter(PushHistory.status == "success").scalar() or 0)
    push_failure = int(db.query(func.count(PushHistory.id)).filter(PushHistory.status == "failed").scalar() or 0)

    llm_total = int(db.query(func.count(LLMUsage.id)).scalar() or 0)
    llm_success = int(db.query(func.count(LLMUsage.id)).filter(LLMUsage.success.is_(True)).scalar() or 0)
    llm_failure = int(db.query(func.count(LLMUsage.id)).filter(LLMUsage.success.is_(False)).scalar() or 0)

    return [
        _metric("video", "视频", video_total, video_success + video_failure, video_success, video_failure),
        _metric("dynamic", "动态", dynamic_total, dynamic_success + dynamic_failure, dynamic_success, dynamic_failure),
        _metric("podcast", "小宇宙", podcast_total, podcast_success + podcast_failure, podcast_success, podcast_failure),
        _metric("push", "推送", push_total, push_success + push_failure, push_success, push_failure),
        _metric("llm", "LLM", llm_total, llm_success + llm_failure, llm_success, llm_failure),
    ]


def _build_recent_errors(db: Session, limit: int = 12) -> list[dict[str, str | None]]:
    errors: list[dict[str, str | None] | dict[str, str | None | datetime]] = []

    def _append(
        *,
        module: str,
        label: str,
        item_label: str,
        item_id: str,
        item_title: str | None,
        status: str | None,
        error_message: str | None,
        occurred_at: datetime | None,
    ) -> None:
        errors.append(
            {
                "module": module,
                "label": label,
                "item_label": item_label,
                "item_id": item_id,
                "item_title": item_title,
                "status": status,
                "error_message": error_message or "任务失败",
                "occurred_at": occurred_at or datetime.min,
            }
        )

    for row in (
        db.query(Video)
        .filter(Video.status == "failed")
        .order_by(Video.updated_at.desc(), Video.id.desc())
        .limit(limit)
        .all()
    ):
        _append(
            module="video",
            label="视频",
            item_label="BVID",
            item_id=row.bvid,
            item_title=row.title,
            status=row.status,
            error_message=row.last_error or "视频处理失败",
            occurred_at=row.updated_at or row.created_at,
        )

    for row in (
        db.query(Dynamic)
        .filter(Dynamic.status == "failed")
        .order_by(Dynamic.updated_at.desc(), Dynamic.id.desc())
        .limit(limit)
        .all()
    ):
        _append(
            module="dynamic",
            label="动态",
            item_label="动态ID",
            item_id=row.dynamic_id,
            item_title=row.text or None,
            status=row.status,
            error_message=row.last_error or "动态处理失败",
            occurred_at=row.updated_at or row.created_at,
        )

    for row in (
        db.query(PodcastEpisode)
        .filter(PodcastEpisode.status.in_(("failed", "failed_download", "failed_asr", "failed_summary")))
        .order_by(PodcastEpisode.updated_at.desc(), PodcastEpisode.id.desc())
        .limit(limit)
        .all()
    ):
        _append(
            module="podcast",
            label="小宇宙",
            item_label="单集ID",
            item_id=row.eid,
            item_title=row.title,
            status=row.status,
            error_message=row.last_error or "小宇宙处理失败",
            occurred_at=row.updated_at or row.created_at,
        )

    for row in (
        db.query(PushHistory)
        .filter(PushHistory.status == "failed")
        .order_by(PushHistory.created_at.desc(), PushHistory.id.desc())
        .limit(limit)
        .all()
    ):
        _append(
            module="push",
            label="推送",
            item_label="内容ID",
            item_id=row.content_id,
            item_title=row.content_title or None,
            status=row.status,
            error_message=row.error_message or row.response_summary or "推送失败",
            occurred_at=row.updated_at or row.created_at,
        )

    for row in (
        db.query(LLMUsage)
        .filter(LLMUsage.success.is_(False))
        .order_by(LLMUsage.created_at.desc(), LLMUsage.id.desc())
        .limit(limit)
        .all()
    ):
        _append(
            module="llm",
            label="LLM",
            item_label="内容ID",
            item_id=row.content_id or f"llm-{row.id}",
            item_title=row.content_title or row.model or row.provider,
            status="failed",
            error_message=row.error_message or "LLM 调用失败",
            occurred_at=row.updated_at or row.created_at,
        )

    errors.sort(key=lambda item: item["occurred_at"] if isinstance(item.get("occurred_at"), datetime) else datetime.min, reverse=True)

    return [
        {
            "module": item["module"],
            "label": item["label"],
            "item_label": item["item_label"],
            "item_id": item["item_id"],
            "item_title": item["item_title"],
            "status": item["status"],
            "error_message": item["error_message"],
            "occurred_at": item["occurred_at"].isoformat() if isinstance(item.get("occurred_at"), datetime) else None,
        }
        for item in errors[:limit]
    ]


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/overview", response_model=OverviewResponse)
def overview(db: Session = Depends(get_session)):
    video_count = db.query(func.count(Video.id)).scalar() or 0
    dynamic_count = db.query(func.count(Dynamic.id)).scalar() or 0
    podcast_count = db.query(func.count(PodcastEpisode.id)).scalar() or 0
    push_count = db.query(func.count(PushHistory.id)).scalar() or 0
    llm_count = db.query(func.count(LLMUsage.id)).scalar() or 0
    tokens = token_overview(db)
    return {
        "videos": int(video_count),
        "dynamics": int(dynamic_count),
        "podcasts": int(podcast_count),
        "push_records": int(push_count),
        "llm_calls": int(llm_count),
        "llm_total_tokens": tokens["total_tokens"],
        "llm_prompt_tokens": tokens["prompt_tokens"],
        "llm_completion_tokens": tokens["completion_tokens"],
    }


@router.get("/tasks/overview", response_model=TaskOverviewResponse)
def task_overview(db: Session = Depends(get_session)):
    ensure_runtime_states()
    video_pending = int(db.query(func.count(Video.id)).filter(Video.status == "pending").scalar() or 0)
    video_processing = int(db.query(func.count(Video.id)).filter(Video.status == "processing").scalar() or 0)
    video_failed = int(db.query(func.count(Video.id)).filter(Video.status == "failed").scalar() or 0)

    dynamic_pending = int(db.query(func.count(Dynamic.id)).filter(Dynamic.status == "pending").scalar() or 0)
    dynamic_processing = int(db.query(func.count(Dynamic.id)).filter(Dynamic.status == "processing").scalar() or 0)
    dynamic_failed = int(db.query(func.count(Dynamic.id)).filter(Dynamic.status == "failed").scalar() or 0)

    podcast_pending = int(db.query(func.count(PodcastEpisode.id)).filter(PodcastEpisode.status == "pending").scalar() or 0)
    podcast_processing = int(
        db.query(func.count(PodcastEpisode.id)).filter(PodcastEpisode.status == "processing").scalar() or 0
    )
    podcast_failed = int(
        db.query(func.count(PodcastEpisode.id))
        .filter(PodcastEpisode.status.in_(("failed", "failed_download", "failed_asr", "failed_summary")))
        .scalar()
        or 0
    )

    runtime_rows = (
        db.query(TaskRuntimeState)
        .filter(TaskRuntimeState.component.in_([SCHEDULER_COMPONENT, QUEUE_WORKER_COMPONENT]))
        .all()
    )
    runtime_by_component = {row.component: serialize_runtime_state(row) for row in runtime_rows}
    runtime_states = [
        runtime_by_component.get(
            component,
            {
                "component": component,
                "label": component,
                "is_paused": False,
                "status": "running",
                "last_heartbeat_at": None,
                "last_run_at": None,
                "last_message": None,
                "last_error": None,
            },
        )
        for component in (SCHEDULER_COMPONENT, QUEUE_WORKER_COMPONENT)
    ]

    return {
        "video_pending": video_pending,
        "video_processing": video_processing,
        "video_failed": video_failed,
        "dynamic_pending": dynamic_pending,
        "dynamic_processing": dynamic_processing,
        "dynamic_failed": dynamic_failed,
        "podcast_pending": podcast_pending,
        "podcast_processing": podcast_processing,
        "podcast_failed": podcast_failed,
        "total_pending": video_pending + dynamic_pending + podcast_pending,
        "total_processing": video_processing + dynamic_processing + podcast_processing,
        "total_failed": video_failed + dynamic_failed + podcast_failed,
        "runtime_states": runtime_states,
    }


@router.get("/tasks", response_model=TaskListResponse)
def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    content_type: str | None = None,
    status: str | None = None,
    q: str | None = None,
    uploader_name: str | None = None,
    pub_after: datetime | None = None,
    pub_before: datetime | None = None,
    db: Session = Depends(get_session),
):
    rows = _collect_task_rows(
        db,
        content_type=content_type,
        status=status,
        q=q,
        uploader_name=uploader_name,
        pub_after=pub_after,
        pub_before=pub_before,
    )
    total = len(rows)
    items = [{k: v for k, v in row.items() if k != "_sort_time"} for row in rows[(page - 1) * page_size : page * page_size]]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.post("/tasks/retry", response_model=TaskRetryResponse)
def retry_tasks(payload: TaskRetryRequest, db: Session = Depends(get_session)):
    if not payload.items:
        raise HTTPException(status_code=400, detail="items required")

    requeued = 0
    failed = 0
    messages: list[str] = []

    for item in payload.items:
        if item.content_type == "video":
            row = db.query(Video).filter(Video.id == item.id).first()
            if not row:
                failed += 1
                messages.append(f"video#{item.id} not found")
                continue
            row.status = "pending"
            row.last_error = None
            row.attempt_count = 0
            requeued += 1
            continue

        if item.content_type == "dynamic":
            row = db.query(Dynamic).filter(Dynamic.id == item.id).first()
            if not row:
                failed += 1
                messages.append(f"dynamic#{item.id} not found")
                continue
            row.status = "pending"
            row.push_status = "pending"
            row.last_error = None
            row.attempt_count = 0
            requeued += 1
            continue

        row = db.query(PodcastEpisode).filter(PodcastEpisode.id == item.id).first()
        if not row:
            failed += 1
            messages.append(f"podcast#{item.id} not found")
            continue
        row.status = "pending"
        row.push_status = "pending"
        row.last_error = None
        row.attempt_count = 0
        requeued += 1

    db.commit()
    return {
        "success": failed == 0,
        "requeued": requeued,
        "failed": failed,
        "message": "; ".join(messages) if messages else "tasks requeued",
    }


@router.post("/tasks/reset-stuck")
def reset_task_queue():
    result = reset_stuck_tasks()
    return {"success": True, "result": result}


def _spawn_background_task(task_name: str, target: str | None, func, *args, **kwargs) -> None:
    def runner() -> None:
        logger.info("[tasks] background task started | task=%s | target=%s", task_name, target)
        try:
            func(*args, **kwargs)
            logger.info("[tasks] background task finished | task=%s | target=%s", task_name, target)
        except Exception as exc:
            logger.error(
                "[tasks] background task failed | task=%s | target=%s | error=%s",
                task_name,
                target,
                exc,
                exc_info=True,
            )

    thread = Thread(target=runner, name=f"task-{task_name}-{target or 'all'}", daemon=True)
    thread.start()


@router.post("/tasks/run/videos", response_model=TaskRunResponse)
def run_video_scan():
    check_new_videos()
    return {
        "success": True,
        "task": "scan_videos",
        "target": None,
        "message": "video scan finished",
    }


@router.post("/tasks/run/dynamics", response_model=TaskRunResponse)
def run_dynamic_scan():
    check_new_dynamics()
    return {
        "success": True,
        "task": "scan_dynamics",
        "target": None,
        "message": "dynamic scan finished",
    }


@router.post("/tasks/run/podcasts", response_model=TaskRunResponse)
def run_podcast_scan():
    check_new_podcast_episodes()
    return {
        "success": True,
        "task": "scan_podcasts",
        "target": None,
        "message": "podcast scan finished",
    }


@router.post("/tasks/async/videos", response_model=TaskAcceptedResponse)
def run_video_scan_async():
    _spawn_background_task("scan_videos", None, check_new_videos)
    return {
        "accepted": True,
        "task": "scan_videos",
        "target": None,
        "message": "video scan accepted",
    }


@router.post("/tasks/async/dynamics", response_model=TaskAcceptedResponse)
def run_dynamic_scan_async():
    _spawn_background_task("scan_dynamics", None, check_new_dynamics)
    return {
        "accepted": True,
        "task": "scan_dynamics",
        "target": None,
        "message": "dynamic scan accepted",
    }


@router.post("/tasks/async/podcasts", response_model=TaskAcceptedResponse)
def run_podcast_scan_async():
    _spawn_background_task("scan_podcasts", None, check_new_podcast_episodes)
    return {
        "accepted": True,
        "task": "scan_podcasts",
        "target": None,
        "message": "podcast scan accepted",
    }


@router.post("/tasks/run/video/{bvid}", response_model=TaskRunResponse)
def run_single_video_task(bvid: str):
    process_single_video(bvid)
    return {
        "success": True,
        "task": "process_video",
        "target": bvid,
        "message": f"video {bvid} processed",
    }


@router.post("/tasks/run/dynamic/{dynamic_id}", response_model=TaskRunResponse)
def run_single_dynamic_task(dynamic_id: str):
    process_single_dynamic(dynamic_id)
    return {
        "success": True,
        "task": "process_dynamic",
        "target": dynamic_id,
        "message": f"dynamic {dynamic_id} processed",
    }


@router.post("/tasks/run/podcast/{eid}", response_model=TaskRunResponse)
def run_single_podcast_task(eid: str):
    process_single_podcast_episode(eid)
    return {
        "success": True,
        "task": "process_podcast",
        "target": eid,
        "message": f"podcast {eid} processed",
    }


@router.post("/tasks/async/video/{bvid}", response_model=TaskAcceptedResponse)
def run_single_video_task_async(bvid: str):
    _spawn_background_task("process_video", bvid, process_single_video, bvid)
    return {
        "accepted": True,
        "task": "process_video",
        "target": bvid,
        "message": f"video {bvid} accepted",
    }


@router.post("/tasks/async/dynamic/{dynamic_id}", response_model=TaskAcceptedResponse)
def run_single_dynamic_task_async(dynamic_id: str):
    _spawn_background_task("process_dynamic", dynamic_id, process_single_dynamic, dynamic_id)
    return {
        "accepted": True,
        "task": "process_dynamic",
        "target": dynamic_id,
        "message": f"dynamic {dynamic_id} accepted",
    }


@router.post("/tasks/async/podcast/{eid}", response_model=TaskAcceptedResponse)
def run_single_podcast_task_async(eid: str):
    _spawn_background_task("process_podcast", eid, process_single_podcast_episode, eid)
    return {
        "accepted": True,
        "task": "process_podcast",
        "target": eid,
        "message": f"podcast {eid} accepted",
    }


@router.post("/manual-push/tasks", response_model=ManualPushTaskCreateResponse)
def create_manual_push_task_endpoint(payload: ManualPushTaskCreateRequest, db: Session = Depends(get_session)):
    bvid = normalize_bvid(payload.bvid)
    _ensure_push_target_exists(db, payload.push_target_id)
    task = create_manual_push_task(bvid, push_target_id=payload.push_target_id)
    task_item = serialize_manual_push_task(task, db=db)
    spawn_manual_push_task(task.id)
    return {
        "accepted": True,
        "task_id": task.id,
        "bvid": task.bvid,
        "push_target_id": task_item.get("push_target_id"),
        "push_target_name": task_item.get("push_target_name"),
        "message": f"manual push task {task.id} accepted",
    }


@router.get("/manual-push/tasks", response_model=ManualPushTaskListResponse)
def list_manual_push_tasks_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_session),
):
    total, rows = list_manual_push_tasks(page=page, page_size=page_size, q=q, status=status)
    items = [serialize_manual_push_task(row, db=db) for row in rows]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/manual-push/tasks/{task_id}", response_model=ManualPushTaskItem)
def get_manual_push_task_endpoint(task_id: int, db: Session = Depends(get_session)):
    row = get_manual_push_task(task_id)
    if not row:
        raise HTTPException(status_code=404, detail="manual push task not found")
    return serialize_manual_push_task_detail(row, db=db)


@router.put("/tasks/runtime", response_model=TaskRuntimeUpdateResponse)
def update_task_runtime(payload: TaskRuntimeUpdateRequest, db: Session = Depends(get_session)):
    ensure_runtime_states()
    runtime_rows = []
    if payload.scheduler_paused is not None:
        runtime_rows.append(set_runtime_pause(db, SCHEDULER_COMPONENT, payload.scheduler_paused, "调度中心暂停" if payload.scheduler_paused else "调度中心恢复"))
    if payload.queue_paused is not None:
        runtime_rows.append(set_runtime_pause(db, QUEUE_WORKER_COMPONENT, payload.queue_paused, "队列监控暂停" if payload.queue_paused else "队列监控恢复"))

    if not runtime_rows:
        runtime_rows = (
            db.query(TaskRuntimeState)
            .filter(TaskRuntimeState.component.in_([SCHEDULER_COMPONENT, QUEUE_WORKER_COMPONENT]))
            .all()
        )
    return {"runtime_states": [serialize_runtime_state(row) for row in runtime_rows]}


@router.get("/configs/env", response_model=EnvConfigResponse)
def list_env_configs():
    return {"items": list_env_config_items()}


@router.put("/configs/env", response_model=EnvConfigResponse)
def save_env_configs(payload: EnvConfigUpdateRequest):
    return {"items": update_env_config(payload.updates)}


@router.get("/videos")
def list_videos(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = None,
    status: str | None = None,
    uploader_name: str | None = None,
    pub_after: datetime | None = None,
    pub_before: datetime | None = None,
    db: Session = Depends(get_session),
):
    query = db.query(Video, Subscription.name.label("uploader_name")).outerjoin(
        Subscription, Subscription.mid == Video.mid
    )
    if q:
        pattern = f"%{q}%"
        query = query.filter(or_(Video.title.ilike(pattern), Video.bvid.ilike(pattern)))
    if status:
        query = query.filter(Video.status == status)
    if uploader_name:
        query = query.filter(Subscription.name.ilike(f"%{uploader_name}%"))
    if pub_after is not None:
        query = query.filter(Video.pub_time >= int(pub_after.timestamp()))
    if pub_before is not None:
        query = query.filter(Video.pub_time <= int(pub_before.timestamp()))

    total = query.order_by(None).count()
    rows = (
        query.order_by(Video.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [serialize_video(video, uploader_name=name or "") for video, name in rows]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/videos/{video_id}")
def get_video(video_id: int, db: Session = Depends(get_session)):
    row = db.query(Video).filter(Video.id == video_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="video not found")
    uploader_name = db.query(Subscription.name).filter(Subscription.mid == row.mid).scalar() or ""
    return serialize_video_detail(row, uploader_name=uploader_name)


@router.patch("/videos/{video_id}")
def update_video_status(video_id: int, payload: StatusUpdate, db: Session = Depends(get_session)):
    row = db.query(Video).filter(Video.id == video_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="video not found")
    row.status = payload.status
    db.commit()
    return {"success": True}


@router.post("/videos/{video_id}/retry", response_model=RetryResponse)
def retry_video(video_id: int, db: Session = Depends(get_session)):
    row = db.query(Video).filter(Video.id == video_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="video not found")
    row.status = "pending"
    row.last_error = None
    row.attempt_count = 0
    db.commit()
    return {"success": True, "message": "video marked pending"}


@router.post("/videos/batch-retry")
def batch_retry_videos(payload: BatchIdsRequest, db: Session = Depends(get_session)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="ids required")
    affected = (
        db.query(Video)
        .filter(Video.id.in_(payload.ids))
        .update(
            {"status": "pending", "last_error": None, "attempt_count": 0},
            synchronize_session=False,
        )
    )
    db.commit()
    return {"success": True, "affected": affected}


@router.patch("/videos/batch-status")
def batch_update_videos_status(payload: BatchStatusUpdate, db: Session = Depends(get_session)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="ids required")
    affected = (
        db.query(Video)
        .filter(Video.id.in_(payload.ids))
        .update({"status": payload.status}, synchronize_session=False)
    )
    db.commit()
    return {"success": True, "affected": affected}


@router.get("/dynamics")
def list_dynamics(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = None,
    status: str | None = None,
    push_status: str | None = None,
    uploader_name: str | None = None,
    pub_after: datetime | None = None,
    pub_before: datetime | None = None,
    db: Session = Depends(get_session),
):
    query = db.query(Dynamic, Subscription.name.label("uploader_name")).outerjoin(
        Subscription, Subscription.mid == Dynamic.mid
    )
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(Dynamic.text.ilike(pattern), Dynamic.dynamic_id.ilike(pattern), Subscription.name.ilike(pattern))
        )
    if status:
        query = query.filter(Dynamic.status == status)
    if push_status:
        query = query.filter(Dynamic.push_status == push_status)
    if uploader_name:
        query = query.filter(Subscription.name.ilike(f"%{uploader_name}%"))
    if pub_after is not None:
        query = query.filter(Dynamic.pub_time >= pub_after)
    if pub_before is not None:
        query = query.filter(Dynamic.pub_time <= pub_before)

    total = query.order_by(None).count()
    rows = (
        query.order_by(Dynamic.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [serialize_dynamic(dynamic, uploader_name=name or "") for dynamic, name in rows]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/dynamics/{dynamic_pk}")
def get_dynamic(dynamic_pk: int, db: Session = Depends(get_session)):
    row = db.query(Dynamic).filter(Dynamic.id == dynamic_pk).first()
    if not row:
        raise HTTPException(status_code=404, detail="dynamic not found")
    uploader_name = db.query(Subscription.name).filter(Subscription.mid == row.mid).scalar() or ""
    return serialize_dynamic(row, uploader_name=uploader_name)


@router.patch("/dynamics/{dynamic_pk}")
def update_dynamic_status(dynamic_pk: int, payload: StatusUpdate, db: Session = Depends(get_session)):
    row = db.query(Dynamic).filter(Dynamic.id == dynamic_pk).first()
    if not row:
        raise HTTPException(status_code=404, detail="dynamic not found")
    row.status = payload.status
    db.commit()
    return {"success": True}


@router.post("/dynamics/{dynamic_pk}/retry", response_model=RetryResponse)
def retry_dynamic(dynamic_pk: int, db: Session = Depends(get_session)):
    row = db.query(Dynamic).filter(Dynamic.id == dynamic_pk).first()
    if not row:
        raise HTTPException(status_code=404, detail="dynamic not found")
    row.status = "pending"
    row.push_status = "pending"
    row.last_error = None
    row.attempt_count = 0
    db.commit()
    return {"success": True, "message": "dynamic marked pending"}


@router.post("/dynamics/batch-retry")
def batch_retry_dynamics(payload: BatchIdsRequest, db: Session = Depends(get_session)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="ids required")
    affected = (
        db.query(Dynamic)
        .filter(Dynamic.id.in_(payload.ids))
        .update(
            {"status": "pending", "push_status": "pending", "last_error": None, "attempt_count": 0},
            synchronize_session=False,
        )
    )
    db.commit()
    return {"success": True, "affected": affected}


@router.patch("/dynamics/batch-status")
def batch_update_dynamics_status(payload: BatchStatusUpdate, db: Session = Depends(get_session)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="ids required")
    affected = (
        db.query(Dynamic)
        .filter(Dynamic.id.in_(payload.ids))
        .update({"status": payload.status}, synchronize_session=False)
    )
    db.commit()
    return {"success": True, "affected": affected}


@router.get("/push-history")
def list_push_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    content_type: str | None = None,
    channel: str | None = None,
    status: str | None = None,
    uploader_name: str | None = None,
    content_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    q: str | None = None,
    db: Session = Depends(get_session),
):
    query = db.query(PushHistory)
    if content_type:
        query = query.filter(PushHistory.content_type == content_type)
    if channel:
        query = query.filter(PushHistory.channel == channel)
    if status:
        query = query.filter(PushHistory.status == status)
    if uploader_name:
        query = query.filter(PushHistory.uploader_name.ilike(f"%{uploader_name}%"))
    if content_id:
        query = query.filter(PushHistory.content_id.ilike(f"%{content_id}%"))
    if start is not None:
        query = query.filter(PushHistory.created_at >= start)
    if end is not None:
        query = query.filter(PushHistory.created_at <= end)
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                PushHistory.content_title.ilike(pattern),
                PushHistory.content_id.ilike(pattern),
                PushHistory.response_summary.ilike(pattern),
            )
        )

    total = query.order_by(None).count()
    rows = (
        query.order_by(PushHistory.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [serialize_push_history(row) for row in rows]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/push-history/{history_id}")
def get_push_history(history_id: int, db: Session = Depends(get_session)):
    row = db.query(PushHistory).filter(PushHistory.id == history_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="push history not found")
    return serialize_push_history_detail(row)


@router.get("/llm-usage")
def list_llm_usage(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    content_type: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    success: bool | None = None,
    uploader_name: str | None = None,
    content_id: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_session),
):
    query = db.query(LLMUsage)
    if content_type:
        query = query.filter(LLMUsage.content_type == content_type)
    if provider:
        query = query.filter(LLMUsage.provider == provider)
    if model:
        query = query.filter(LLMUsage.model == model)
    if success is not None:
        query = query.filter(LLMUsage.success == success)
    if uploader_name:
        query = query.filter(LLMUsage.uploader_name.ilike(f"%{uploader_name}%"))
    if content_id:
        query = query.filter(LLMUsage.content_id.ilike(f"%{content_id}%"))
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                LLMUsage.content_title.ilike(pattern),
                LLMUsage.content_id.ilike(pattern),
                LLMUsage.error_message.ilike(pattern),
            )
        )

    total = query.order_by(None).count()
    rows = (
        query.order_by(LLMUsage.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [serialize_llm_usage(row) for row in rows]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/llm-usage/{usage_id}")
def get_llm_usage(usage_id: int, db: Session = Depends(get_session)):
    row = db.query(LLMUsage).filter(LLMUsage.id == usage_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="llm usage not found")
    return serialize_llm_usage_detail(row)


@router.get("/stats/tokens/daily")
def token_stats_daily(db: Session = Depends(get_session)):
    rows = (
        db.query(
            func.date(LLMUsage.created_at).label("day"),
            func.coalesce(func.sum(LLMUsage.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(LLMUsage.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(LLMUsage.total_tokens), 0).label("total_tokens"),
            func.count(LLMUsage.id).label("calls"),
        )
        .group_by(func.date(LLMUsage.created_at))
        .order_by(func.date(LLMUsage.created_at).desc())
        .all()
    )
    return [
        {
            "day": row.day,
            "prompt_tokens": int(row.prompt_tokens or 0),
            "completion_tokens": int(row.completion_tokens or 0),
            "total_tokens": int(row.total_tokens or 0),
            "calls": int(row.calls or 0),
        }
        for row in rows
    ]


@router.get("/stats/tokens/models")
def token_stats_models(db: Session = Depends(get_session)):
    rows = (
        db.query(
            LLMUsage.provider,
            LLMUsage.model,
            func.coalesce(func.sum(LLMUsage.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(LLMUsage.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(LLMUsage.total_tokens), 0).label("total_tokens"),
            func.count(LLMUsage.id).label("calls"),
        )
        .group_by(LLMUsage.provider, LLMUsage.model)
        .order_by(func.count(LLMUsage.id).desc())
        .all()
    )
    return [
        {
            "provider": row.provider,
            "model": row.model,
            "prompt_tokens": int(row.prompt_tokens or 0),
            "completion_tokens": int(row.completion_tokens or 0),
            "total_tokens": int(row.total_tokens or 0),
            "calls": int(row.calls or 0),
        }
        for row in rows
    ]


@router.get("/stats/summary")
def stats_summary(db: Session = Depends(get_session)):
    def _status_rows(model, status_column):
        rows = (
            db.query(status_column.label("status"), func.count(model.id).label("count"))
            .group_by(status_column)
            .order_by(func.count(model.id).desc())
            .all()
        )
        return [{"status": row.status, "count": int(row.count or 0)} for row in rows]

    def _count_by(column, model):
        rows = (
            db.query(column.label("name"), func.count(model.id).label("count"))
            .group_by(column)
            .order_by(func.count(model.id).desc())
            .all()
        )
        return [{"name": row.name, "count": int(row.count or 0)} for row in rows]

    trend_7_days = _build_trend_window(db, 7)
    trend_30_days = _build_trend_window(db, 30)
    recent_14_days = _build_trend_window(db, 14)

    return {
        "health_metrics": _build_health_metrics(db),
        "video_status": _status_rows(Video, Video.status),
        "dynamic_status": _status_rows(Dynamic, Dynamic.status),
        "podcast_status": _status_rows(PodcastEpisode, PodcastEpisode.status),
        "push_channel_status": [
            {"channel": row.channel, "status": row.status, "count": int(row.count or 0)}
            for row in db.query(
                PushHistory.channel,
                PushHistory.status,
                func.count(PushHistory.id).label("count"),
            )
            .group_by(PushHistory.channel, PushHistory.status)
            .order_by(func.count(PushHistory.id).desc())
            .all()
        ],
        "llm_provider_status": [
            {"provider": row.provider, "success": bool(row.success), "count": int(row.count or 0)}
            for row in db.query(
                LLMUsage.provider,
                LLMUsage.success,
                func.count(LLMUsage.id).label("count"),
            )
            .group_by(LLMUsage.provider, LLMUsage.success)
            .order_by(func.count(LLMUsage.id).desc())
            .all()
        ],
        "trend_7_days": trend_7_days,
        "trend_30_days": trend_30_days,
        "recent_push_days": list(reversed(recent_14_days["push_days"])),
        "recent_llm_days": list(reversed(recent_14_days["llm_days"])),
        "recent_errors": _build_recent_errors(db),
    }


@router.get("/monitor/overview")
def monitor_overview(db: Session = Depends(get_session)):
    task_overview_data = task_overview(db)
    summary = stats_summary(db)
    return {
        "health_metrics": summary["health_metrics"],
        "task_overview": task_overview_data,
        "runtime_states": task_overview_data["runtime_states"],
        "recent_errors": summary["recent_errors"],
        "recent_push_days": summary["recent_push_days"],
        "recent_llm_days": summary["recent_llm_days"],
    }


@router.get("/content-audit/overview")
def content_audit_overview(
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
):
    skipped_query = db.query(PushHistory).filter(PushHistory.status == "skipped")
    skipped_total = skipped_query.count()
    recent_skipped = skipped_query.order_by(PushHistory.created_at.desc()).limit(page_size).all()

    reason_expr = func.coalesce(PushHistory.error_message, PushHistory.response_summary, "未说明").label("reason")
    reason_subquery = (
        db.query(
            reason_expr,
            PushHistory.id.label("push_history_id"),
        )
        .filter(PushHistory.status == "skipped")
        .subquery()
    )
    reason_rows = (
        db.query(
            reason_subquery.c.reason,
            func.count(reason_subquery.c.push_history_id).label("count"),
        )
        .group_by(reason_subquery.c.reason)
        .order_by(func.count(reason_subquery.c.push_history_id).desc())
        .limit(10)
        .all()
    )

    content_rows = (
        db.query(PushHistory.content_type, func.count(PushHistory.id).label("count"))
        .filter(PushHistory.status == "skipped")
        .group_by(PushHistory.content_type)
        .order_by(func.count(PushHistory.id).desc())
        .all()
    )
    uploader_rows = (
        db.query(PushHistory.uploader_name, func.count(PushHistory.id).label("count"))
        .filter(PushHistory.status == "skipped")
        .group_by(PushHistory.uploader_name)
        .order_by(func.count(PushHistory.id).desc())
        .limit(10)
        .all()
    )
    llm_filter_total = db.query(func.count(LLMUsage.id)).filter(LLMUsage.content_type == "push_filter").scalar() or 0
    llm_filter_failed = (
        db.query(func.count(LLMUsage.id))
        .filter(LLMUsage.content_type == "push_filter", LLMUsage.success.is_(False))
        .scalar()
        or 0
    )
    return {
        "skipped_total": int(skipped_total or 0),
        "llm_filter_total": int(llm_filter_total or 0),
        "llm_filter_failed": int(llm_filter_failed or 0),
        "reason_rows": [{"reason": row.reason or "未说明", "count": int(row.count or 0)} for row in reason_rows],
        "content_rows": [{"content_type": row.content_type, "count": int(row.count or 0)} for row in content_rows],
        "uploader_rows": [
            {"uploader_name": row.uploader_name or "未知", "count": int(row.count or 0)} for row in uploader_rows
        ],
        "recent_skipped": [serialize_push_history(row) for row in recent_skipped],
    }

@router.get("/logs")
def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    level: str | None = None,
    module: str | None = None,
    source_file: str | None = None,
    q: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    window_days: int = Query(7, ge=1, le=30),
):
    if start is not None and end is not None and end < start:
        raise HTTPException(status_code=400, detail="end must be after start")
    return query_logs(
        page=page,
        page_size=page_size,
        level=level,
        module=module,
        source_file=source_file,
        q=q,
        start=start,
        end=end,
        window_days=window_days,
    )


@router.get("/logs/{log_id}")
def get_log_detail_endpoint(log_id: str, context_lines: int = Query(12, ge=0, le=50)):
    try:
        return get_log_detail(log_id, context_lines=context_lines)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="log file not found")
    except LookupError:
        raise HTTPException(status_code=404, detail="log record not found")


@router.get("/subscriptions")
def list_subscriptions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = None,
    is_active: bool | None = None,
    push_target_id: int | None = None,
    unbound: bool | None = None,
    db: Session = Depends(get_session),
):
    query = db.query(Subscription)
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                Subscription.name.ilike(pattern),
                Subscription.mid.ilike(pattern),
                Subscription.homepage_url.ilike(pattern),
            )
        )
    if is_active is not None:
        query = query.filter(Subscription.is_active == is_active)
    if unbound:
        query = query.filter(Subscription.push_target_id.is_(None))
    elif push_target_id is not None:
        query = query.filter(Subscription.push_target_id == push_target_id)
    total = query.order_by(None).count()
    rows = (
        query.outerjoin(PushTarget, Subscription.push_target_id == PushTarget.id)
        .order_by(
            Subscription.is_active.desc(),
            case((Subscription.push_target_id.is_(None), 1), else_=0).asc(),
            PushTarget.name.asc(),
            Subscription.name.asc(),
            Subscription.mid.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    target_map = {
        row.id: row.name
        for row in db.query(PushTarget.id, PushTarget.name).filter(PushTarget.channel == "feishu").all()
    }
    items = []
    for row in rows:
        item = serialize_subscription(row)
        item["push_target_name"] = target_map.get(row.push_target_id)
        items.append(item)
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.post("/subscriptions")
def create_subscription(payload: SubscriptionCreate, db: Session = Depends(get_session)):
    existing = db.query(Subscription).filter(Subscription.mid == payload.mid).first()
    if existing:
        raise HTTPException(status_code=409, detail="subscription already exists")
    _ensure_push_target_exists(db, payload.push_target_id)
    row = Subscription(
        mid=payload.mid,
        name=payload.name,
        homepage_url=payload.homepage_url or f"https://space.bilibili.com/{payload.mid}",
        notes=payload.notes,
        push_target_id=payload.push_target_id,
        is_active=payload.is_active,
    )
    db.add(row)
    db.commit()
    item = serialize_subscription(row)
    item["push_target_name"] = (
        db.query(PushTarget.name).filter(PushTarget.id == row.push_target_id).scalar() if row.push_target_id else None
    )
    return item


@router.put("/subscriptions/{subscription_id}")
def update_subscription(subscription_id: int, payload: SubscriptionUpdate, db: Session = Depends(get_session)):
    row = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="subscription not found")
    fields_set = getattr(payload, "model_fields_set", set())
    if payload.name is not None:
        row.name = payload.name
    if payload.homepage_url is not None:
        row.homepage_url = payload.homepage_url or f"https://space.bilibili.com/{row.mid}"
    if payload.notes is not None:
        row.notes = payload.notes
    if "push_target_id" in fields_set:
        _ensure_push_target_exists(db, payload.push_target_id)
        row.push_target_id = payload.push_target_id
    if payload.is_active is not None:
        row.is_active = payload.is_active
    db.commit()
    item = serialize_subscription(row)
    item["push_target_name"] = (
        db.query(PushTarget.name).filter(PushTarget.id == row.push_target_id).scalar() if row.push_target_id else None
    )
    return item


@router.delete("/subscriptions/{subscription_id}")
def delete_subscription(subscription_id: int, db: Session = Depends(get_session)):
    row = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="subscription not found")
    db.delete(row)
    db.commit()
    return {"success": True}


@router.patch("/subscriptions/batch-active")
def batch_update_subscriptions_active(payload: BatchActiveUpdate, db: Session = Depends(get_session)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="ids required")
    affected = (
        db.query(Subscription)
        .filter(Subscription.id.in_(payload.ids))
        .update({"is_active": payload.is_active}, synchronize_session=False)
    )
    db.commit()
    return {"success": True, "affected": affected}


@router.post("/subscriptions/batch-delete")
def batch_delete_subscriptions(payload: BatchIdsRequest, db: Session = Depends(get_session)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="ids required")
    affected = db.query(Subscription).filter(Subscription.id.in_(payload.ids)).delete(synchronize_session=False)
    db.commit()
    return {"success": True, "affected": affected}


@router.get("/push-targets")
def list_push_targets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_session),
):
    query = db.query(PushTarget).filter(PushTarget.channel == "feishu")
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                PushTarget.name.ilike(pattern),
                PushTarget.receive_id.ilike(pattern),
                PushTarget.notes.ilike(pattern),
            )
        )
    if is_active is not None:
        query = query.filter(PushTarget.is_active == is_active)
    total = query.order_by(None).count()
    rows = (
        query.order_by(PushTarget.is_default.desc(), PushTarget.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [serialize_push_target(row) for row in rows]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.post("/push-targets")
def create_push_target(payload: PushTargetCreate, db: Session = Depends(get_session)):
    row = PushTarget(
        channel="feishu",
        name=payload.name,
        receive_id=payload.receive_id,
        receive_id_type=payload.receive_id_type,
        notes=payload.notes,
        is_active=payload.is_active,
        is_default=False,
    )
    db.add(row)
    db.flush()
    if payload.is_default or not db.query(PushTarget).filter(PushTarget.channel == "feishu", PushTarget.id != row.id).count():
        _set_default_push_target(db, row)
    db.commit()
    db.refresh(row)
    return serialize_push_target(row)


@router.put("/push-targets/{target_id}")
def update_push_target(target_id: int, payload: PushTargetUpdate, db: Session = Depends(get_session)):
    row = db.query(PushTarget).filter(PushTarget.id == target_id, PushTarget.channel == "feishu").first()
    if not row:
        raise HTTPException(status_code=404, detail="push target not found")
    fields_set = getattr(payload, "model_fields_set", set())
    if "name" in fields_set:
        row.name = payload.name or row.name
    if "receive_id" in fields_set:
        row.receive_id = payload.receive_id or row.receive_id
    if "receive_id_type" in fields_set:
        row.receive_id_type = payload.receive_id_type or row.receive_id_type
    if "notes" in fields_set:
        row.notes = payload.notes
    if "is_active" in fields_set and payload.is_active is not None:
        row.is_active = payload.is_active
    if "is_default" in fields_set and payload.is_default is not None:
        if payload.is_default:
            _set_default_push_target(db, row)
        elif row.is_default:
            raise HTTPException(status_code=400, detail="default push target cannot be unset directly")
    db.commit()
    db.refresh(row)
    return serialize_push_target(row)


@router.patch("/push-targets/{target_id}/default")
def set_push_target_default(target_id: int, db: Session = Depends(get_session)):
    row = db.query(PushTarget).filter(PushTarget.id == target_id, PushTarget.channel == "feishu").first()
    if not row:
        raise HTTPException(status_code=404, detail="push target not found")
    _set_default_push_target(db, row)
    db.commit()
    db.refresh(row)
    return serialize_push_target(row)


@router.patch("/push-targets/{target_id}/active")
def set_push_target_active(target_id: int, payload: StatusUpdate, db: Session = Depends(get_session)):
    row = db.query(PushTarget).filter(PushTarget.id == target_id, PushTarget.channel == "feishu").first()
    if not row:
        raise HTTPException(status_code=404, detail="push target not found")
    normalized = str(payload.status).strip().lower()
    if normalized not in {"active", "inactive"}:
        raise HTTPException(status_code=400, detail="status must be active or inactive")
    if row.is_default and normalized != "active":
        raise HTTPException(status_code=400, detail="default push target cannot be disabled")
    row.is_active = normalized == "active"
    db.commit()
    db.refresh(row)
    return serialize_push_target(row)


@router.delete("/push-targets/{target_id}")
def delete_push_target(target_id: int, db: Session = Depends(get_session)):
    row = db.query(PushTarget).filter(PushTarget.id == target_id, PushTarget.channel == "feishu").first()
    if not row:
        raise HTTPException(status_code=404, detail="push target not found")
    if row.is_default:
        raise HTTPException(status_code=400, detail="default push target cannot be deleted")
    bound_count = db.query(Subscription).filter(Subscription.push_target_id == row.id).count()
    if bound_count:
        raise HTTPException(status_code=400, detail="push target is still bound by subscriptions")
    db.delete(row)
    db.commit()
    return {"success": True}


@router.get("/podcast-subscriptions")
def list_podcast_subscriptions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_session),
):
    query = db.query(PodcastSubscription)
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                PodcastSubscription.name.ilike(pattern),
                PodcastSubscription.pid.ilike(pattern),
                PodcastSubscription.homepage_url.ilike(pattern),
            )
        )
    if is_active is not None:
        query = query.filter(PodcastSubscription.is_active == is_active)
    total = query.order_by(None).count()
    rows = (
        query.order_by(PodcastSubscription.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [serialize_podcast_subscription(row) for row in rows]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.post("/podcast-subscriptions")
def create_podcast_subscription(payload: PodcastSubscriptionCreate, db: Session = Depends(get_session)):
    existing = db.query(PodcastSubscription).filter(PodcastSubscription.pid == payload.pid).first()
    if existing:
        raise HTTPException(status_code=409, detail="podcast subscription already exists")
    row = PodcastSubscription(
        pid=payload.pid,
        name=payload.name,
        homepage_url=payload.homepage_url or f"https://www.xiaoyuzhoufm.com/podcast/{payload.pid}",
        notes=payload.notes,
        is_active=payload.is_active,
        bootstrap_recent_episodes=payload.bootstrap_recent_episodes,
    )
    db.add(row)
    db.commit()
    return serialize_podcast_subscription(row)


@router.put("/podcast-subscriptions/{subscription_id}")
def update_podcast_subscription(
    subscription_id: int, payload: PodcastSubscriptionUpdate, db: Session = Depends(get_session)
):
    row = db.query(PodcastSubscription).filter(PodcastSubscription.id == subscription_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="podcast subscription not found")
    if payload.name is not None:
        row.name = payload.name
    if payload.homepage_url is not None:
        row.homepage_url = payload.homepage_url or f"https://www.xiaoyuzhoufm.com/podcast/{row.pid}"
    if payload.notes is not None:
        row.notes = payload.notes
    if payload.is_active is not None:
        row.is_active = payload.is_active
    if payload.bootstrap_recent_episodes is not None:
        row.bootstrap_recent_episodes = payload.bootstrap_recent_episodes
    db.commit()
    return serialize_podcast_subscription(row)


@router.delete("/podcast-subscriptions/{subscription_id}")
def delete_podcast_subscription(subscription_id: int, db: Session = Depends(get_session)):
    row = db.query(PodcastSubscription).filter(PodcastSubscription.id == subscription_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="podcast subscription not found")
    db.delete(row)
    db.commit()
    return {"success": True}


@router.patch("/podcast-subscriptions/batch-active")
def batch_update_podcast_subscriptions_active(payload: BatchActiveUpdate, db: Session = Depends(get_session)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="ids required")
    affected = (
        db.query(PodcastSubscription)
        .filter(PodcastSubscription.id.in_(payload.ids))
        .update({"is_active": payload.is_active}, synchronize_session=False)
    )
    db.commit()
    return {"success": True, "affected": affected}


@router.post("/podcast-subscriptions/batch-delete")
def batch_delete_podcast_subscriptions(payload: BatchIdsRequest, db: Session = Depends(get_session)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="ids required")
    affected = db.query(PodcastSubscription).filter(PodcastSubscription.id.in_(payload.ids)).delete(
        synchronize_session=False
    )
    db.commit()
    return {"success": True, "affected": affected}


@router.get("/podcast-episodes")
def list_podcast_episodes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = None,
    status: str | None = None,
    push_status: str | None = None,
    uploader_name: str | None = None,
    pid: str | None = None,
    db: Session = Depends(get_session),
):
    query = db.query(PodcastEpisode, PodcastSubscription.name.label("podcast_name")).outerjoin(
        PodcastSubscription, PodcastSubscription.pid == PodcastEpisode.pid
    )
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                PodcastEpisode.eid.ilike(pattern),
                PodcastEpisode.title.ilike(pattern),
                PodcastEpisode.last_error.ilike(pattern),
                PodcastSubscription.name.ilike(pattern),
            )
        )
    if status:
        query = query.filter(PodcastEpisode.status == status)
    if push_status:
        query = query.filter(PodcastEpisode.push_status == push_status)
    if uploader_name:
        query = query.filter(PodcastSubscription.name.ilike(f"%{uploader_name}%"))
    if pid:
        query = query.filter(PodcastEpisode.pid == pid)
    total = query.order_by(None).count()
    rows = (
        query.order_by(PodcastEpisode.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = []
    for episode, podcast_name in rows:
        item = serialize_podcast_episode(episode)
        item["uploader_name"] = podcast_name or ""
        item["source_url"] = f"https://www.xiaoyuzhoufm.com/episode/{episode.eid}"
        items.append(item)
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/podcast-episodes/{episode_pk}")
def get_podcast_episode(episode_pk: int, db: Session = Depends(get_session)):
    row = db.query(PodcastEpisode).filter(PodcastEpisode.id == episode_pk).first()
    if not row:
        raise HTTPException(status_code=404, detail="podcast episode not found")
    item = serialize_podcast_episode(row)
    item["uploader_name"] = db.query(PodcastSubscription.name).filter(PodcastSubscription.pid == row.pid).scalar() or ""
    item["source_url"] = f"https://www.xiaoyuzhoufm.com/episode/{row.eid}"
    return item


@router.post("/podcast-episodes/{episode_pk}/retry", response_model=RetryResponse)
def retry_podcast_episode(episode_pk: int, db: Session = Depends(get_session)):
    row = db.query(PodcastEpisode).filter(PodcastEpisode.id == episode_pk).first()
    if not row:
        raise HTTPException(status_code=404, detail="podcast episode not found")
    row.status = "pending"
    row.push_status = "pending"
    row.last_error = None
    row.attempt_count = 0
    db.commit()
    return {"success": True, "message": "podcast episode marked pending"}


@router.post("/podcast-episodes/batch-retry")
def batch_retry_podcast_episodes(payload: BatchIdsRequest, db: Session = Depends(get_session)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="ids required")
    affected = (
        db.query(PodcastEpisode)
        .filter(PodcastEpisode.id.in_(payload.ids))
        .update({"status": "pending", "push_status": "pending", "last_error": None, "attempt_count": 0}, synchronize_session=False)
    )
    db.commit()
    return {"success": True, "affected": affected}


@router.patch("/podcast-episodes/batch-status")
def batch_update_podcast_episodes_status(payload: BatchStatusUpdate, db: Session = Depends(get_session)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="ids required")
    affected = (
        db.query(PodcastEpisode)
        .filter(PodcastEpisode.id.in_(payload.ids))
        .update({"status": payload.status}, synchronize_session=False)
    )
    db.commit()
    return {"success": True, "affected": affected}


@router.get("/wewe-rss/feeds")
def list_wewe_rss_feeds(
    q: str | None = None,
    db: Session = Depends(get_session),
):
    if not Config.WEWE_RSS_BASE_URL:
        raise HTTPException(status_code=400, detail="WEWE_RSS_BASE_URL is not configured")
    try:
        client = WeWeRssClient(Config.WEWE_RSS_BASE_URL, auth_code=Config.WEWE_RSS_AUTH_CODE)
        feeds = client.list_feeds()
    except WeWeRssError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        try:
            client.close()
        except Exception:
            pass

    items = []
    for feed in feeds:
        item = {
            "feed_id": feed.feed_id,
            "title": feed.title,
            "homepage_url": feed.homepage_url or build_feed_urls(Config.WEWE_RSS_BASE_URL, feed.feed_id)["homepage_url"],
            "atom_url": feed.atom_url or build_feed_urls(Config.WEWE_RSS_BASE_URL, feed.feed_id)["atom_url"],
            "rss_url": feed.rss_url or build_feed_urls(Config.WEWE_RSS_BASE_URL, feed.feed_id)["rss_url"],
            "json_url": feed.json_url or build_feed_urls(Config.WEWE_RSS_BASE_URL, feed.feed_id)["json_url"],
            "raw": feed.raw,
        }
        if q:
            pattern = q.lower()
            if pattern not in item["feed_id"].lower() and pattern not in item["title"].lower():
                continue
        items.append(item)
    return {"total": len(items), "items": items}


@router.get("/wewe-rss-subscriptions")
def list_wewe_rss_subscriptions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = None,
    is_active: bool | None = None,
    push_target_id: int | None = None,
    unbound: bool | None = None,
    db: Session = Depends(get_session),
):
    query = db.query(WeWeRssSubscription)
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                WeWeRssSubscription.name.ilike(pattern),
                WeWeRssSubscription.feed_id.ilike(pattern),
                WeWeRssSubscription.homepage_url.ilike(pattern),
            )
        )
    if is_active is not None:
        query = query.filter(WeWeRssSubscription.is_active == is_active)
    if unbound:
        query = query.filter(WeWeRssSubscription.push_target_id.is_(None))
    elif push_target_id is not None:
        query = query.filter(WeWeRssSubscription.push_target_id == push_target_id)
    total = query.order_by(None).count()
    rows = (
        query.outerjoin(PushTarget, WeWeRssSubscription.push_target_id == PushTarget.id)
        .order_by(
            WeWeRssSubscription.is_active.desc(),
            case((WeWeRssSubscription.push_target_id.is_(None), 1), else_=0).asc(),
            PushTarget.name.asc(),
            WeWeRssSubscription.name.asc(),
            WeWeRssSubscription.feed_id.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    target_map = {
        row.id: row.name
        for row in db.query(PushTarget.id, PushTarget.name).filter(PushTarget.channel == "feishu").all()
    }
    items = []
    for row in rows:
        item = serialize_wewe_subscription(row)
        item["push_target_name"] = target_map.get(row.push_target_id)
        items.append(item)
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.post("/wewe-rss-subscriptions")
def create_wewe_rss_subscription(payload: WeWeRssSubscriptionCreate, db: Session = Depends(get_session)):
    existing = db.query(WeWeRssSubscription).filter(WeWeRssSubscription.feed_id == payload.feed_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="wewe rss subscription already exists")
    _ensure_push_target_exists(db, payload.push_target_id)
    feed_format = _normalize_wewe_feed_format(payload.feed_format)
    homepage_url = payload.homepage_url or (
        build_feed_urls(Config.WEWE_RSS_BASE_URL, payload.feed_id)["homepage_url"]
        if Config.WEWE_RSS_BASE_URL
        else None
    )
    row = WeWeRssSubscription(
        feed_id=payload.feed_id,
        name=payload.name,
        homepage_url=homepage_url,
        feed_format=feed_format,
        notes=payload.notes,
        push_target_id=payload.push_target_id,
        bootstrap_recent_items=payload.bootstrap_recent_items,
        is_active=payload.is_active,
    )
    db.add(row)
    db.commit()
    item = serialize_wewe_subscription(row)
    item["push_target_name"] = (
        db.query(PushTarget.name).filter(PushTarget.id == row.push_target_id).scalar() if row.push_target_id else None
    )
    return item


@router.put("/wewe-rss-subscriptions/{subscription_id}")
def update_wewe_rss_subscription(
    subscription_id: int, payload: WeWeRssSubscriptionUpdate, db: Session = Depends(get_session)
):
    row = db.query(WeWeRssSubscription).filter(WeWeRssSubscription.id == subscription_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="wewe rss subscription not found")
    fields_set = getattr(payload, "model_fields_set", set())
    if payload.name is not None:
        row.name = payload.name
    if payload.homepage_url is not None:
        row.homepage_url = payload.homepage_url or (
            build_feed_urls(Config.WEWE_RSS_BASE_URL, row.feed_id)["homepage_url"]
            if Config.WEWE_RSS_BASE_URL
            else row.homepage_url
        )
    if payload.notes is not None:
        row.notes = payload.notes
    if "push_target_id" in fields_set:
        _ensure_push_target_exists(db, payload.push_target_id)
        row.push_target_id = payload.push_target_id
    if "feed_format" in fields_set and payload.feed_format is not None:
        row.feed_format = _normalize_wewe_feed_format(payload.feed_format)
    if "bootstrap_recent_items" in fields_set and payload.bootstrap_recent_items is not None:
        row.bootstrap_recent_items = payload.bootstrap_recent_items
    if payload.is_active is not None:
        row.is_active = payload.is_active
    db.commit()
    item = serialize_wewe_subscription(row)
    item["push_target_name"] = (
        db.query(PushTarget.name).filter(PushTarget.id == row.push_target_id).scalar() if row.push_target_id else None
    )
    return item


@router.delete("/wewe-rss-subscriptions/{subscription_id}")
def delete_wewe_rss_subscription(subscription_id: int, db: Session = Depends(get_session)):
    row = db.query(WeWeRssSubscription).filter(WeWeRssSubscription.id == subscription_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="wewe rss subscription not found")
    db.delete(row)
    db.commit()
    return {"success": True}


@router.patch("/wewe-rss-subscriptions/batch-active")
def batch_update_wewe_rss_subscriptions_active(payload: BatchActiveUpdate, db: Session = Depends(get_session)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="ids required")
    affected = (
        db.query(WeWeRssSubscription)
        .filter(WeWeRssSubscription.id.in_(payload.ids))
        .update({"is_active": payload.is_active}, synchronize_session=False)
    )
    db.commit()
    return {"success": True, "affected": affected}


@router.post("/wewe-rss-subscriptions/batch-delete")
def batch_delete_wewe_rss_subscriptions(payload: BatchIdsRequest, db: Session = Depends(get_session)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="ids required")
    affected = db.query(WeWeRssSubscription).filter(WeWeRssSubscription.id.in_(payload.ids)).delete(
        synchronize_session=False
    )
    db.commit()
    return {"success": True, "affected": affected}


@router.post("/wewe-rss-subscriptions/{subscription_id}/refresh")
def refresh_wewe_rss_subscription(subscription_id: int, db: Session = Depends(get_session)):
    row = db.query(WeWeRssSubscription).filter(WeWeRssSubscription.id == subscription_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="wewe rss subscription not found")
    from app.services.wewe_rss import sync_subscription_articles

    result = sync_subscription_articles(db, row, manual_update=True)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("error") or "refresh failed")
    return result


@router.get("/wewe-rss-articles")
def list_wewe_rss_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = None,
    status: str | None = None,
    push_status: str | None = None,
    feed_id: str | None = None,
    db: Session = Depends(get_session),
):
    query = db.query(WeWeRssArticle, WeWeRssSubscription.name.label("feed_name")).outerjoin(
        WeWeRssSubscription, WeWeRssSubscription.feed_id == WeWeRssArticle.feed_id
    )
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                WeWeRssArticle.entry_id.ilike(pattern),
                WeWeRssArticle.title.ilike(pattern),
                WeWeRssArticle.content_text.ilike(pattern),
                WeWeRssSubscription.name.ilike(pattern),
            )
        )
    if status:
        query = query.filter(WeWeRssArticle.status == status)
    if push_status:
        query = query.filter(WeWeRssArticle.push_status == push_status)
    if feed_id:
        query = query.filter(WeWeRssArticle.feed_id == feed_id)
    total = query.order_by(None).count()
    rows = (
        query.order_by(WeWeRssArticle.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = []
    for article, feed_name in rows:
        item = serialize_wewe_article(article)
        item["feed_name"] = feed_name or ""
        items.append(item)
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/wewe-rss-articles/{article_pk}")
def get_wewe_rss_article(article_pk: int, db: Session = Depends(get_session)):
    row = db.query(WeWeRssArticle).filter(WeWeRssArticle.id == article_pk).first()
    if not row:
        raise HTTPException(status_code=404, detail="wewe rss article not found")
    item = serialize_wewe_article(row)
    item["feed_name"] = db.query(WeWeRssSubscription.name).filter(WeWeRssSubscription.feed_id == row.feed_id).scalar() or ""
    return item


@router.post("/wewe-rss-articles/{article_pk}/retry", response_model=RetryResponse)
def retry_wewe_rss_article(article_pk: int, db: Session = Depends(get_session)):
    row = db.query(WeWeRssArticle).filter(WeWeRssArticle.id == article_pk).first()
    if not row:
        raise HTTPException(status_code=404, detail="wewe rss article not found")
    row.status = "pending"
    row.push_status = "pending"
    row.last_error = None
    row.attempt_count = 0
    db.commit()
    return {"success": True, "message": "wewe rss article marked pending"}


@router.post("/wewe-rss-articles/batch-retry")
def batch_retry_wewe_rss_articles(payload: BatchIdsRequest, db: Session = Depends(get_session)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="ids required")
    affected = (
        db.query(WeWeRssArticle)
        .filter(WeWeRssArticle.id.in_(payload.ids))
        .update({"status": "pending", "push_status": "pending", "last_error": None, "attempt_count": 0}, synchronize_session=False)
    )
    db.commit()
    return {"success": True, "affected": affected}


@router.patch("/wewe-rss-articles/batch-status")
def batch_update_wewe_rss_articles_status(payload: BatchStatusUpdate, db: Session = Depends(get_session)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="ids required")
    affected = (
        db.query(WeWeRssArticle)
        .filter(WeWeRssArticle.id.in_(payload.ids))
        .update({"status": payload.status}, synchronize_session=False)
    )
    db.commit()
    return {"success": True, "affected": affected}


@router.get("/classification-rules")
def list_classification_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = None,
    uploader_name: str | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_session),
):
    query = db.query(ClassificationRule)
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                ClassificationRule.pattern.ilike(pattern),
                ClassificationRule.target_folder.ilike(pattern),
                ClassificationRule.uploader_name.ilike(pattern),
            )
        )
    if uploader_name:
        query = query.filter(ClassificationRule.uploader_name.ilike(f"%{uploader_name}%"))
    if is_active is not None:
        query = query.filter(ClassificationRule.is_active == is_active)
    total = query.order_by(None).count()
    rows = (
        query.order_by(ClassificationRule.priority.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [serialize_rule(row) for row in rows]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.post("/classification-rules")
def create_classification_rule(payload: ClassificationRuleCreate, db: Session = Depends(get_session)):
    row = ClassificationRule(
        uploader_name=payload.uploader_name,
        pattern=payload.pattern,
        target_folder=payload.target_folder,
        priority=payload.priority,
        is_active=payload.is_active,
    )
    db.add(row)
    db.commit()
    return serialize_rule(row)


@router.put("/classification-rules/{rule_id}")
def update_classification_rule(rule_id: int, payload: ClassificationRuleUpdate, db: Session = Depends(get_session)):
    row = db.query(ClassificationRule).filter(ClassificationRule.id == rule_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="rule not found")
    if payload.uploader_name is not None:
        row.uploader_name = payload.uploader_name
    if payload.pattern is not None:
        row.pattern = payload.pattern
    if payload.target_folder is not None:
        row.target_folder = payload.target_folder
    if payload.priority is not None:
        row.priority = payload.priority
    if payload.is_active is not None:
        row.is_active = payload.is_active
    db.commit()
    return serialize_rule(row)


@router.delete("/classification-rules/{rule_id}")
def delete_classification_rule(rule_id: int, db: Session = Depends(get_session)):
    row = db.query(ClassificationRule).filter(ClassificationRule.id == rule_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="rule not found")
    db.delete(row)
    db.commit()
    return {"success": True}


@router.patch("/classification-rules/batch-active")
def batch_update_classification_rules_active(
    payload: BatchActiveUpdate, db: Session = Depends(get_session)
):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="ids required")
    affected = (
        db.query(ClassificationRule)
        .filter(ClassificationRule.id.in_(payload.ids))
        .update({"is_active": payload.is_active}, synchronize_session=False)
    )
    db.commit()
    return {"success": True, "affected": affected}


@router.post("/classification-rules/batch-delete")
def batch_delete_classification_rules(payload: BatchIdsRequest, db: Session = Depends(get_session)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="ids required")
    affected = (
        db.query(ClassificationRule)
        .filter(ClassificationRule.id.in_(payload.ids))
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"success": True, "affected": affected}


@router.get("/folder-mappings")
def list_folder_mappings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = None,
    uploader_name: str | None = None,
    db: Session = Depends(get_session),
):
    query = db.query(FolderMapping)
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                FolderMapping.folder_path.ilike(pattern),
                FolderMapping.folder_token.ilike(pattern),
                FolderMapping.category.ilike(pattern),
                FolderMapping.uploader_name.ilike(pattern),
            )
        )
    if uploader_name:
        query = query.filter(FolderMapping.uploader_name.ilike(f"%{uploader_name}%"))
    total = query.order_by(None).count()
    rows = (
        query.order_by(FolderMapping.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [serialize_folder_mapping(row) for row in rows]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.post("/folder-mappings")
def create_folder_mapping(payload: FolderMappingCreate, db: Session = Depends(get_session)):
    row = FolderMapping(
        uploader_name=payload.uploader_name,
        category=payload.category,
        folder_token=payload.folder_token,
        folder_path=payload.folder_path,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_folder_mapping(row)


@router.put("/folder-mappings/{mapping_id}")
def update_folder_mapping(mapping_id: int, payload: FolderMappingUpdate, db: Session = Depends(get_session)):
    row = db.query(FolderMapping).filter(FolderMapping.id == mapping_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="mapping not found")
    if payload.uploader_name is not None:
        row.uploader_name = payload.uploader_name
    if payload.category is not None:
        row.category = payload.category
    if payload.folder_token is not None:
        row.folder_token = payload.folder_token
    if payload.folder_path is not None:
        row.folder_path = payload.folder_path
    db.commit()
    db.refresh(row)
    return serialize_folder_mapping(row)


@router.delete("/folder-mappings/{mapping_id}")
def delete_folder_mapping(mapping_id: int, db: Session = Depends(get_session)):
    row = db.query(FolderMapping).filter(FolderMapping.id == mapping_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="mapping not found")
    db.delete(row)
    db.commit()
    return {"success": True}


@router.post("/folder-mappings/batch-delete")
def batch_delete_folder_mappings(payload: BatchIdsRequest, db: Session = Depends(get_session)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="ids required")
    affected = db.query(FolderMapping).filter(FolderMapping.id.in_(payload.ids)).delete(synchronize_session=False)
    db.commit()
    return {"success": True, "affected": affected}

from admin_backend.routers.llm import router as llm_router
router.include_router(llm_router)
