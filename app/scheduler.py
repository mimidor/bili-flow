from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime

from app.models.database import (
    Dynamic,
    PodcastEpisode,
    PodcastSubscription,
    Subscription,
    Video,
    WeWeRssSubscription,
    get_db,
)
from app.modules.bilibili import fetch_channel_videos
from app.modules.bilibili_auth import get_auth_manager
from app.modules.dynamic import DynamicFetcher, is_dynamic_recent
from app.modules.processor import classify_push_relevance
from app.modules.xiaoyuzhou import XiaoyuzhouClient, XyzApiError
from app.services.wewe_rss import sync_subscription_articles
from app.utils.logger import get_logger
from config import Config

logger = get_logger("scheduler")


def check_and_refresh_cookie():
    """Check whether the Bilibili cookie should be refreshed."""
    if not Config.BILIBILI_COOKIE:
        logger.debug("未配置 BILIBILI_COOKIE，跳过 Cookie 刷新检查")
        return None

    auth = get_auth_manager()
    refresh_token = auth.get_refresh_token()
    if not refresh_token:
        logger.debug("未配置 refresh_token，跳过 Cookie 自动刷新")
        return None

    logger.info("开始检查 Cookie 是否需要刷新...")
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        new_cookie, refreshed = loop.run_until_complete(
            auth.auto_refresh_if_needed(Config.BILIBILI_COOKIE)
        )
        if refreshed:
            logger.info("Cookie 已刷新")
            Config.BILIBILI_COOKIE = new_cookie
            return new_cookie
        logger.debug("Cookie 无需刷新")
        return None
    except Exception as exc:
        logger.error("Cookie 刷新过程出错: %s", exc, exc_info=True)
        return None


def check_new_videos():
    logger.info("[检测] 开始检查新视频...")
    db = get_db()
    try:
        subscriptions = db.query(Subscription).filter_by(is_active=True).all()
        if not subscriptions:
            logger.warning("[检测] 未配置任何 B 站 UP 主订阅")
            logger.info("[检测完成] 发现 0 个新视频，0 个错误")
            return

        new_count = 0
        error_count = 0
        for sub in subscriptions:
            try:
                videos = fetch_channel_videos(sub.mid, limit=10)
                logger.debug("[检测] 用户 %s(%s) 获取 %d 个视频", sub.name, sub.mid, len(videos))
                for video_payload in videos:
                    if db.query(Video).filter_by(bvid=video_payload["bvid"]).first():
                        logger.debug("[检测] 视频已存在: %s", video_payload["bvid"])
                        continue
                    if video_payload.get("pubdate") and not is_dynamic_recent(video_payload.get("pubdate")):
                        logger.debug("[检测] 视频超过 24 小时，跳过: %s", video_payload["bvid"])
                        continue

                    db.add(
                        Video(
                            bvid=video_payload["bvid"],
                            title=video_payload["title"],
                            mid=sub.mid,
                            pub_time=video_payload.get("pubdate", 0),
                            status="pending",
                        )
                    )
                    new_count += 1
                    logger.info("[新视频] %s | %s (%s)", sub.name, video_payload["title"], video_payload["bvid"])

                sub.last_check_time = datetime.utcnow()
            except Exception as exc:
                error_count += 1
                logger.error("[检测] 检查用户 %s(%s) 失败: %s", sub.mid, sub.name, exc, exc_info=True)

        db.commit()
        logger.info("[检测完成] 发现 %d 个新视频，%d 个错误", new_count, error_count)
    except Exception as exc:
        db.rollback()
        logger.error("[检测] 异常: %s", exc, exc_info=True)
    finally:
        db.close()


def check_new_dynamics():
    logger.info("[检测] 开始检查新动态...")
    db = get_db()
    try:
        with DynamicFetcher() as fetcher:
            subscriptions = db.query(Subscription).filter_by(is_active=True).all()
            if not subscriptions:
                logger.warning("[检测] 未配置任何 B 站 UP 主订阅")
                logger.info("[检测完成] 发现 0 个新动态，0 个错误")
                return

            all_new_dynamics = []
            error_count = 0

            for sub in subscriptions:
                try:
                    dynamics = fetcher.fetch_dynamic(sub.mid)
                    logger.debug("[检测] 用户 %s(%s) 获取 %d 个动态", sub.name, sub.mid, len(dynamics))

                    for dyn in dynamics:
                        if dyn.get("pub_time") and not is_dynamic_recent(dyn.get("pub_time")):
                            logger.debug("[检测] 动态超过 24 小时，跳过: %s", dyn["dynamic_id"])
                            continue

                        if db.query(Dynamic).filter_by(dynamic_id=dyn["dynamic_id"]).first():
                            logger.debug("[检测] 动态已存在: %s", dyn["dynamic_id"])
                            continue

                        dyn = fetcher.download_images(dyn)
                        dyn["mid"] = sub.mid
                        dyn["sub_name"] = sub.name

                        if dyn.get("type") == "DYNAMIC_TYPE_AV" or dyn.get("is_video"):
                            logger.info("[检测] 动态为视频卡片，仅入库不推送: %s", dyn["dynamic_id"])
                            db.add(
                                Dynamic(
                                    dynamic_id=dyn["dynamic_id"],
                                    mid=dyn["mid"],
                                    type=dyn.get("type", ""),
                                    text=dyn.get("text", ""),
                                    image_count=len(dyn.get("images", [])),
                                    images_path=json.dumps(dyn.get("images", []), ensure_ascii=False),
                                    image_urls=json.dumps(dyn.get("image_urls", []), ensure_ascii=False),
                                    pub_time=dyn.get("pub_time"),
                                    status="sent",
                                    pushed_at=datetime.utcnow(),
                                )
                            )
                            continue

                        all_new_dynamics.append(dyn)

                    sub.last_check_time = datetime.utcnow()
                except Exception as exc:
                    error_count += 1
                    logger.error("[检测] 检查用户 %s(%s) 动态失败: %s", sub.mid, sub.name, exc, exc_info=True)

            all_new_dynamics.sort(key=lambda item: item.get("pub_time") or datetime.min)

            from app.modules.push import push_content

            for dyn in all_new_dynamics:
                pub_time_str = str(dyn["pub_time"]) if dyn.get("pub_time") else ""
                push_payload = {
                    "type": "dynamic",
                    "content_id": dyn["dynamic_id"],
                    "mid": dyn["mid"],
                    "text": dyn.get("text", ""),
                    "images": dyn.get("images", []),
                    "image_urls": dyn.get("image_urls", []),
                    "uploader_name": dyn.get("uploader_name") or dyn.get("sub_name", ""),
                    "summary": dyn.get("text", "")[:80],
                    "details": "",
                    "key_points": [],
                    "tags": [],
                    "stocks": [],
                    "insights": "",
                    "pub_time": pub_time_str,
                    "url": f"https://www.bilibili.com/opus/{dyn['dynamic_id']}",
                }
                push_filter = classify_push_relevance(
                    push_payload,
                    content_type="dynamic",
                    content_id=dyn["dynamic_id"],
                    content_title=push_payload.get("summary", "") or dyn.get("text", "")[:80],
                    uploader_name=push_payload.get("uploader_name", ""),
                )
                push_payload["push_filter"] = push_filter

                new_dynamic = Dynamic(
                    dynamic_id=dyn["dynamic_id"],
                    mid=dyn["mid"],
                    type=dyn.get("type", ""),
                    text=dyn.get("text", ""),
                    image_count=len(dyn.get("images", [])),
                    images_path=json.dumps(dyn.get("images", []), ensure_ascii=False),
                    image_urls=json.dumps(dyn.get("image_urls", []), ensure_ascii=False),
                    pub_time=dyn.get("pub_time"),
                    status="processing",
                    push_status="processing",
                )
                db.add(new_dynamic)

                push_result = push_content(push_payload, ["feishu"])
                if push_result.get("skipped"):
                    new_dynamic.status = "filtered"
                    new_dynamic.push_status = "skipped"
                    new_dynamic.last_error = str(
                        push_result.get("reason")
                        or push_filter.get("reason")
                        or "内容与宏观/社会主题无关"
                    )[:200]
                elif not push_result.get("success", False):
                    new_dynamic.status = "failed"
                    new_dynamic.push_status = "failed"
                    new_dynamic.last_error = str(push_result.get("reason") or "push failed")[:200]
                else:
                    new_dynamic.status = "sent"
                    new_dynamic.push_status = "success"
                    new_dynamic.pushed_at = datetime.utcnow()
                    new_dynamic.last_error = None

                logger.info("[推送] %s | %s...", dyn.get("sub_name", ""), (dyn.get("text", "") or "")[:50])

        db.commit()
        logger.info("[检测完成] 发现 %d 个新动态，%d 个错误", len(all_new_dynamics), error_count)
    except Exception as exc:
        db.rollback()
        logger.error("[检测] 异常: %s", exc, exc_info=True)
    finally:
        db.close()


def check_new_podcast_episodes():
    logger.info("[检测] 开始检查小宇宙节目更新...")
    db = get_db()
    try:
        subscriptions = db.query(PodcastSubscription).filter_by(is_active=True).all()
        if not subscriptions:
            logger.warning("[检测] 未配置任何小宇宙节目订阅")
            logger.info("[检测完成] 发现 0 个小宇宙新单集，0 个错误")
            return

        new_count = 0
        error_count = 0
        client = XiaoyuzhouClient(
            device_id=getattr(Config, "XYZ_DEVICE_ID", "") or os.getenv("XIAOYUZHOU_ID", "")
        )
        try:
            for sub in subscriptions:
                try:
                    bootstrap_recent_episodes = int(
                        sub.bootstrap_recent_episodes or Config.XYZ_BOOTSTRAP_RECENT_EPISODES or 3
                    )
                    discovered, gap_detected, latest, cursor = client.discover_new_episodes(
                        sub.pid,
                        last_seen_eid=sub.last_episode_eid,
                        bootstrap_recent_episodes=bootstrap_recent_episodes,
                        max_pages=int(Config.XYZ_MAX_PAGES_PER_POLL or 5),
                    )
                    sub.last_check_time = datetime.utcnow()

                    if gap_detected:
                        logger.warning("[检测] 小宇宙节目分页未完全覆盖最新增量: %s(%s)", sub.name, sub.pid)

                    for episode_payload in discovered:
                        if db.query(PodcastEpisode).filter_by(eid=episode_payload.eid).first():
                            logger.debug("[检测] 小宇宙单集已存在: %s", episode_payload.eid)
                            continue

                        db.add(
                            PodcastEpisode(
                                eid=episode_payload.eid,
                                pid=episode_payload.pid or sub.pid,
                                title=episode_payload.title,
                                pub_time=episode_payload.pub_date,
                                audio_url=episode_payload.audio_url,
                                audio_mime=episode_payload.audio_mime,
                                audio_size=episode_payload.audio_size,
                                raw_episode_json=json.dumps(
                                    episode_payload.raw,
                                    ensure_ascii=False,
                                    default=str,
                                ),
                                status="pending",
                                push_status="pending",
                                discovered_at=datetime.utcnow(),
                            )
                        )
                        new_count += 1
                        logger.info("[新单集] %s | %s (%s)", sub.name, episode_payload.title, episode_payload.eid)

                    sub.last_response_cursor_json = (
                        json.dumps(cursor, ensure_ascii=False, default=str) if cursor else None
                    )
                    if latest:
                        sub.last_episode_eid = latest.eid
                        sub.last_episode_pub_time = latest.pub_date
                    sub.last_success_time = datetime.utcnow()
                    sub.consecutive_failures = 0
                except (XyzApiError, Exception) as exc:
                    error_count += 1
                    sub.consecutive_failures = int(sub.consecutive_failures or 0) + 1
                    logger.error("[检测] 检查小宇宙节目 %s(%s) 失败: %s", sub.pid, sub.name, exc, exc_info=True)
        finally:
            client.close()

        db.commit()
        logger.info("[检测完成] 发现 %d 个小宇宙新单集，%d 个错误", new_count, error_count)
    except Exception as exc:
        db.rollback()
        logger.error("[检测] 小宇宙异常: %s", exc, exc_info=True)
    finally:
        db.close()


def check_new_wewe_articles():
    logger.info("[检测] 开始检查公众号订阅更新...")
    db = get_db()
    try:
        subscriptions = db.query(WeWeRssSubscription).filter_by(is_active=True).all()
        if not subscriptions:
            logger.warning("[检测] 未配置任何公众号订阅")
            logger.info("[检测完成] 发现 0 篇公众号新文章，推送 0，失败 0，跳过 0，0 个错误")
            return

        new_count = 0
        pushed_count = 0
        failed_count = 0
        skipped_count = 0
        error_count = 0

        for sub in subscriptions:
            try:
                result = sync_subscription_articles(db, sub, manual_update=False)
                new_count += int(result.get("new_count") or 0)
                pushed_count += int(result.get("pushed_count") or 0)
                failed_count += int(result.get("failed_count") or 0)
                skipped_count += int(result.get("skipped_count") or 0)
                if not result.get("success"):
                    error_count += 1
                    logger.error(
                        "[检测] 检查公众号 %s(%s) 失败: %s",
                        sub.feed_id,
                        sub.name,
                        result.get("error") or "unknown error",
                    )
                else:
                    logger.info(
                        "[检测] 公众号 %s(%s) 同步完成，新文章 %d，推送 %d，失败 %d，跳过 %d",
                        sub.feed_id,
                        sub.name,
                        int(result.get("new_count") or 0),
                        int(result.get("pushed_count") or 0),
                        int(result.get("failed_count") or 0),
                        int(result.get("skipped_count") or 0),
                    )
            except Exception as exc:
                error_count += 1
                logger.error("[检测] 检查公众号 %s(%s) 失败: %s", sub.feed_id, sub.name, exc, exc_info=True)

        logger.info(
            "[检测完成] 发现 %d 篇公众号新文章，推送 %d，失败 %d，跳过 %d，%d 个错误",
            new_count,
            pushed_count,
            failed_count,
            skipped_count,
            error_count,
        )
    except Exception as exc:
        logger.error("[检测] 异常: %s", exc, exc_info=True)
    finally:
        db.close()


def start_scheduler():
    """Compatibility wrapper for the runtime scheduler."""
    from app.runtime_scheduler import start_scheduler as runtime_start_scheduler

    runtime_start_scheduler(stop_event=None)
