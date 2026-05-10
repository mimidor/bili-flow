from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from sqlalchemy.exc import OperationalError

from app.models.database import Dynamic, PodcastEpisode, Video, get_db
from app.utils.logger import get_logger
from app.utils.task_runtime import (
    QUEUE_WORKER_COMPONENT,
    get_or_create_runtime_state,
    touch_runtime_state,
)

logger = get_logger("queue_worker")

PENDING_BATCH_SIZE = 5
RETRY_BATCH_SIZE = 2
MAX_ATTEMPTS = 3
IDLE_SLEEP_SECONDS = 30
ACTIVE_SLEEP_SECONDS = 5
ERROR_SLEEP_SECONDS = 10


def _commit_with_retry(db, *, retries: int = 5, base_delay: float = 0.2) -> None:
    for attempt in range(retries):
        try:
            db.commit()
            return
        except OperationalError as exc:
            db.rollback()
            if "database is locked" not in str(exc).lower() or attempt >= retries - 1:
                raise
            time.sleep(base_delay * (attempt + 1))


def _process_single_video(bvid: str) -> None:
    from app.queue_worker import process_single_video

    process_single_video(bvid)


def _process_single_dynamic(dynamic_id: str) -> None:
    from app.queue_worker import process_single_dynamic

    process_single_dynamic(dynamic_id)


def _process_single_podcast_episode(eid: str) -> None:
    from app.queue_worker import process_single_podcast_episode

    process_single_podcast_episode(eid)


def _wait_or_sleep(stop_event: Event | None, seconds: float) -> bool:
    if stop_event is not None:
        return stop_event.wait(seconds)
    time.sleep(seconds)
    return False


def _load_pending_and_retry_tasks(db):
    pending_dynamics = (
        db.query(Dynamic)
        .filter_by(status="pending")
        .order_by(Dynamic.pub_time.asc().nullslast())
        .limit(PENDING_BATCH_SIZE)
        .all()
    )
    pending_podcasts = (
        db.query(PodcastEpisode)
        .filter_by(status="pending")
        .order_by(PodcastEpisode.pub_time.asc().nullslast())
        .limit(PENDING_BATCH_SIZE)
        .all()
    )
    pending_videos = (
        db.query(Video)
        .filter_by(status="pending")
        .order_by(Video.created_at)
        .limit(PENDING_BATCH_SIZE)
        .all()
    )
    retry_videos = (
        db.query(Video)
        .filter_by(status="failed")
        .filter(Video.attempt_count < MAX_ATTEMPTS)
        .limit(RETRY_BATCH_SIZE)
        .all()
    )
    retry_dynamics = (
        db.query(Dynamic)
        .filter_by(status="failed")
        .filter(Dynamic.attempt_count < MAX_ATTEMPTS)
        .limit(RETRY_BATCH_SIZE)
        .all()
    )
    retry_podcasts = (
        db.query(PodcastEpisode)
        .filter(PodcastEpisode.status.in_(["failed", "failed_download", "failed_asr", "failed_summary"]))
        .filter(PodcastEpisode.attempt_count < MAX_ATTEMPTS)
        .limit(RETRY_BATCH_SIZE)
        .all()
    )
    return (
        pending_dynamics,
        pending_podcasts,
        pending_videos,
        retry_dynamics,
        retry_podcasts,
        retry_videos,
    )


def _submit_tasks(db, executor, items, processor, *, retry: bool = False, label: str = "") -> None:
    for item in items:
        item_id = getattr(item, "dynamic_id", None) or getattr(item, "eid", None) or getattr(item, "bvid", None)
        if retry:
            logger.info("重新处理失败%s: %s (第%d次重试)", label, item_id, item.attempt_count + 1)
        item.status = "processing"
        _commit_with_retry(db)
        executor.submit(processor, item_id)


def start_queue_worker(max_workers: int = 3, stop_event: Event | None = None):
    """Continuously process pending queue items."""
    logger.info("=" * 50)
    logger.info("队列处理线程启动，max_workers=%d", max_workers)
    logger.info("=" * 50)

    executor = ThreadPoolExecutor(max_workers=max_workers)
    try:
        loop_count = 0
        while stop_event is None or not stop_event.is_set():
            loop_count += 1
            db = get_db()
            try:
                runtime_state = get_or_create_runtime_state(db, QUEUE_WORKER_COMPONENT)
                if runtime_state.is_paused:
                    touch_runtime_state(
                        db,
                        QUEUE_WORKER_COMPONENT,
                        status="paused",
                        message="队列已暂停，等待恢复",
                        heartbeat=True,
                    )
                    if _wait_or_sleep(stop_event, IDLE_SLEEP_SECONDS):
                        break
                    continue

                (
                    pending_dynamics,
                    pending_podcasts,
                    pending_videos,
                    retry_dynamics,
                    retry_podcasts,
                    retry_videos,
                ) = _load_pending_and_retry_tasks(db)

                total_retry = len(retry_videos) + len(retry_dynamics) + len(retry_podcasts)
                touch_runtime_state(
                    db,
                    QUEUE_WORKER_COMPONENT,
                    status="running",
                    message=(
                        f"待处理动态 {len(pending_dynamics)} 条，待处理小宇宙 {len(pending_podcasts)} 条，"
                        f"待处理视频 {len(pending_videos)} 条，重试任务 {total_retry} 条"
                    ),
                    heartbeat=True,
                    activity=True,
                )

                if loop_count % 6 == 0:
                    logger.info(
                        "[定期统计] 待处理动态 %d, 待处理小宇宙 %d, 待处理视频 %d, 重试队列: %d",
                        len(pending_dynamics),
                        len(pending_podcasts),
                        len(pending_videos),
                        total_retry,
                    )

                if not any(
                    [
                        pending_dynamics,
                        pending_podcasts,
                        pending_videos,
                        retry_dynamics,
                        retry_podcasts,
                        retry_videos,
                    ]
                ):
                    logger.debug("暂无待处理任务，休眠...")
                    if _wait_or_sleep(stop_event, IDLE_SLEEP_SECONDS):
                        break
                    continue

                _submit_tasks(db, executor, pending_dynamics, _process_single_dynamic, label="动态")
                _submit_tasks(db, executor, pending_podcasts, _process_single_podcast_episode, label="小宇宙单集")
                _submit_tasks(db, executor, retry_dynamics, _process_single_dynamic, retry=True, label="动态")
                _submit_tasks(db, executor, retry_podcasts, _process_single_podcast_episode, retry=True, label="小宇宙单集")
                _submit_tasks(db, executor, pending_videos, _process_single_video, label="视频")
                _submit_tasks(db, executor, retry_videos, _process_single_video, retry=True, label="视频")

                if _wait_or_sleep(stop_event, ACTIVE_SLEEP_SECONDS):
                    break
            except Exception as exc:
                logger.error("队列处理循环异常: %s", exc, exc_info=True)
                try:
                    touch_runtime_state(
                        db,
                        QUEUE_WORKER_COMPONENT,
                        status="error",
                        message="队列循环异常",
                        error=str(exc),
                        heartbeat=True,
                    )
                except Exception:
                    pass
                if _wait_or_sleep(stop_event, ERROR_SLEEP_SECONDS):
                    break
            finally:
                db.close()
    finally:
        executor.shutdown(wait=not (stop_event is not None and stop_event.is_set()), cancel_futures=True)
