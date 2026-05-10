from __future__ import annotations

from app.models.database import Dynamic, PodcastEpisode, Video, get_db
from app.utils.logger import get_logger

logger = get_logger("init")


def reset_stuck_tasks() -> dict[str, int]:
    """Reset unfinished processing tasks back to pending."""
    db = get_db()
    stats = {
        "videos": 0,
        "dynamics": 0,
        "podcasts": 0,
    }
    try:
        stuck_videos = db.query(Video).filter_by(status="processing").all()
        for video in stuck_videos:
            logger.warning("重置卡住的视频任务: %s | %s", video.bvid, video.title)
            video.status = "pending"
            video.attempt_count += 1
        stats["videos"] = len(stuck_videos)

        stuck_dynamics = db.query(Dynamic).filter_by(status="processing").all()
        for dynamic in stuck_dynamics:
            logger.warning("重置卡住的动态任务: %s", dynamic.dynamic_id)
            dynamic.status = "pending"
            dynamic.attempt_count += 1
        stats["dynamics"] = len(stuck_dynamics)

        stuck_podcasts = db.query(PodcastEpisode).filter_by(status="processing").all()
        for episode in stuck_podcasts:
            logger.warning("重置卡住的小宇宙任务: %s", episode.eid)
            episode.status = "pending"
            episode.push_status = "pending"
            episode.attempt_count += 1
        stats["podcasts"] = len(stuck_podcasts)

        db.commit()
        logger.info(
            "已重置卡住任务: 视频 %d, 动态 %d, 小宇宙 %d",
            stats["videos"],
            stats["dynamics"],
            stats["podcasts"],
        )
        return stats
    except Exception as exc:
        logger.error("重置卡住任务时出错: %s", exc, exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


def graceful_shutdown() -> None:
    """Best-effort shutdown hook."""
    logger.info("执行优雅关闭...")
    logger.info("优雅关闭完成，下次启动时会重置卡住的任务")
