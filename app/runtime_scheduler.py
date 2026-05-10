from __future__ import annotations

import schedule
import time
from threading import Event

from app.models.database import get_db
from app.utils.logger import get_logger
from app.utils.task_runtime import (
    SCHEDULER_COMPONENT,
    get_or_create_runtime_state,
    touch_runtime_state,
)
from config import Config

logger = get_logger("scheduler")


def _check_new_videos_job():
    from app.scheduler import check_new_videos

    return check_new_videos()


def _check_new_dynamics_job():
    from app.scheduler import check_new_dynamics

    return check_new_dynamics()


def _check_new_podcast_episodes_job():
    from app.scheduler import check_new_podcast_episodes

    return check_new_podcast_episodes()


def _check_new_wewe_articles_job():
    from app.scheduler import check_new_wewe_articles

    return check_new_wewe_articles()


def _scan_local_video_dirs_job():
    from app.services.manual_push_tasks import scan_local_video_dirs

    return scan_local_video_dirs()


def _wait_or_sleep(stop_event: Event | None, seconds: float) -> bool:
    if stop_event is not None:
        return stop_event.wait(seconds)
    time.sleep(seconds)
    return False


def _configure_jobs() -> tuple[int, int, int, int, int]:
    schedule.clear()
    video_interval = Config.VIDEO_CHECK_INTERVAL
    dynamic_interval = Config.DYNAMIC_CHECK_INTERVAL
    podcast_interval = Config.XYZ_CHECK_INTERVAL
    wewe_interval = Config.WEWE_RSS_CHECK_INTERVAL
    local_video_interval = Config.LOCAL_VIDEO_SCAN_INTERVAL

    if video_interval > 0:
        logger.info("视频检测频率: 每 %d 分钟", video_interval)
        schedule.every(video_interval).minutes.do(_check_new_videos_job).tag("video")
    else:
        logger.info("视频检测已禁用 (VIDEO_CHECK_INTERVAL=%d)", video_interval)

    if dynamic_interval > 0:
        logger.info("动态检测频率: 每 %d 分钟", dynamic_interval)
        schedule.every(dynamic_interval).minutes.do(_check_new_dynamics_job).tag("dynamic")
    else:
        logger.info("动态检测已禁用 (DYNAMIC_CHECK_INTERVAL=%d)", dynamic_interval)

    if podcast_interval > 0:
        logger.info("小宇宙检测频率: 每 %d 分钟", podcast_interval)
        schedule.every(podcast_interval).minutes.do(_check_new_podcast_episodes_job).tag("podcast")
    else:
        logger.info("小宇宙检测已禁用 (XYZ_CHECK_INTERVAL=%d)", podcast_interval)

    if wewe_interval > 0:
        logger.info("公众号检测频率: 每 %d 分钟", wewe_interval)
        schedule.every(wewe_interval).minutes.do(_check_new_wewe_articles_job).tag("wewe_rss")
    else:
        logger.info("公众号检测已禁用 (WEWE_RSS_CHECK_INTERVAL=%d)", wewe_interval)

    if local_video_interval > 0:
        logger.info("Local FLV scan enabled every %d minutes", local_video_interval)
        schedule.every(local_video_interval).minutes.do(_scan_local_video_dirs_job).tag("local_video")
    else:
        logger.info("Local FLV scan disabled (LOCAL_VIDEO_SCAN_INTERVAL=%d)", local_video_interval)

    logger.info("=" * 50)
    return video_interval, dynamic_interval, podcast_interval, wewe_interval, local_video_interval


def start_scheduler(stop_event: Event | None = None):
    """Run the periodic scheduler loop."""
    logger.info("=" * 50)
    logger.info("调度任务启动")

    current_signature = _configure_jobs()
    loop_count = 0

    while stop_event is None or not stop_event.is_set():
        db = get_db()
        try:
            loop_count += 1
            runtime_state = get_or_create_runtime_state(db, SCHEDULER_COMPONENT)
            if runtime_state.is_paused:
                touch_runtime_state(
                    db,
                    SCHEDULER_COMPONENT,
                    status="paused",
                    message="调度已暂停，等待恢复",
                    heartbeat=True,
                )
                if _wait_or_sleep(stop_event, 10):
                    break
                continue

            touch_runtime_state(
                db,
                SCHEDULER_COMPONENT,
                status="running",
                message="调度轮询中",
                heartbeat=True,
                activity=True,
            )

            signature = (
                Config.VIDEO_CHECK_INTERVAL,
                Config.DYNAMIC_CHECK_INTERVAL,
                Config.XYZ_CHECK_INTERVAL,
                Config.WEWE_RSS_CHECK_INTERVAL,
                Config.LOCAL_VIDEO_SCAN_INTERVAL,
            )
            if signature != current_signature:
                logger.info("[调度] 检测到间隔配置变化，重新加载任务")
                current_signature = _configure_jobs()

            schedule.run_pending()
            if loop_count % 6 == 0:
                logger.debug("[调度] 心跳正常，已运行约 %d 分钟", loop_count)

            if _wait_or_sleep(stop_event, 10):
                break
        except Exception as exc:
            logger.error("[调度] 异常: %s", exc, exc_info=True)
            try:
                touch_runtime_state(
                    db,
                    SCHEDULER_COMPONENT,
                    status="error",
                    message="调度循环异常",
                    error=str(exc),
                    heartbeat=True,
                )
            except Exception:
                pass
            if _wait_or_sleep(stop_event, 30):
                break
        finally:
            db.close()
