import time
import json
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import wraps
from app.utils.logger import get_logger
from app.models.database import get_db, Video, Dynamic, Subscription, PodcastEpisode, PodcastSubscription
from app.modules.bilibili import fetch_dynamic_detail, fetch_video_detail
from app.modules.subtitle import get_subtitles
from app.modules.downloader import download_audio, _generate_filename
from app.modules.whisper_ai import transcribe_audio
from app.modules.processor import classify_push_relevance, process_text
from app.modules.dynamic_summary import process_dynamic_text
from app.modules.podcast_summary import process_podcast_text
from app.modules.xiaoyuzhou import download_episode_audio
from app.modules.push import push_content
from app.modules.push_channels import is_silent_mode
from app.modules.feishu_docs import push_video_summary_to_doc, push_dynamic_summary_to_doc, push_podcast_summary_to_doc
from app.modules.dynamic import should_push_dynamic, is_dynamic_recent
from app.utils.paths import PathManager, get_path_manager
from app.utils.runtime_home import get_data_dir, get_install_root, get_runtime_home, get_source_root
from app.utils.llm_client import get_llm_config, get_llm_profiles

logger = get_logger("queue_worker")


def retry_on_db_lock(max_retries=3, delay=0.5):
    """数据库锁定重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if "database is locked" in str(e) and attempt < max_retries - 1:
                        logger.warning("数据库锁定，第%d次重试: %s", attempt + 1, e)
                        time.sleep(delay * (attempt + 1))
                    else:
                        raise
        return wrapper
    return decorator

# 数据保存路径（旧路径，用于向后兼容）
DATA_ROOT = get_data_dir()
TEXT_DIR = DATA_ROOT / "text"
MARKDOWN_DIR = DATA_ROOT / "markdown"

# 确保目录存在
TEXT_DIR.mkdir(parents=True, exist_ok=True)
MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_stored_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    candidates = [
        get_runtime_home() / path,
        get_source_root() / path,
        get_install_root() / path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def get_uploader_info(db, mid: str) -> tuple:
    """获取 UP 主信息"""
    sub = db.query(Subscription).filter_by(mid=mid).first()
    if sub:
        return sub.name, sub.mid
    return f"UP主_{mid}", mid


def get_podcast_info(db, pid: str) -> tuple[str, str]:
    """获取小宇宙节目名称。"""
    row = db.query(PodcastSubscription).filter_by(pid=pid).first()
    if row:
        return row.name, row.pid
    return f"节目_{pid}", pid


def _format_pub_time(value) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(int(value)).strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, OSError, OverflowError, TypeError):
            return str(value)
    return str(value).strip()


def _resolve_summary_model_name(use_case_key: str) -> str:
    _, profiles = get_llm_profiles(use_case_key)
    model_names = [
        str(getattr(profile, "model_name", "")).strip()
        for profile in profiles
        if str(getattr(profile, "model_name", "")).strip()
    ]
    if model_names:
        return ", ".join(dict.fromkeys(model_names))

    _, profile = get_llm_config(use_case_key)
    if profile and getattr(profile, "model_name", ""):
        return str(profile.model_name).strip()
    return "gpt-3.5-turbo"


def _prepend_model_note(markdown_content: str, model_name: str) -> str:
    model_name = (model_name or "").strip()
    if not model_name:
        return markdown_content

    model_line = f"**使用模型**: {model_name}"
    if model_line in markdown_content:
        return markdown_content

    marker = "\n---\n"
    if marker in markdown_content:
        head, tail = markdown_content.split(marker, 1)
        head = head.rstrip()
        return f"{head}\n\n{model_line}\n\n---\n{tail.lstrip()}"

    lines = markdown_content.splitlines()
    if lines and lines[0].startswith("#"):
        head = lines[0].rstrip()
        rest = "\n".join(lines[1:]).lstrip()
        return f"{head}\n\n{model_line}\n\n{rest}" if rest else f"{head}\n\n{model_line}"

    content = markdown_content.strip()
    return f"{model_line}\n\n{content}" if content else model_line


def _prepend_usage_model_note(markdown_content: str, model_name: str) -> str:
    model_name = (model_name or "").strip()
    if not model_name:
        return markdown_content

    model_line = f"使用模型：{model_name}"
    if model_line in markdown_content:
        return markdown_content

    marker = "\n---\n"
    if marker in markdown_content:
        head, tail = markdown_content.split(marker, 1)
        head = head.rstrip()
        return f"{head}\n\n{model_line}\n\n---\n{tail.lstrip()}"

    lines = markdown_content.splitlines()
    if lines and lines[0].startswith("#"):
        head = lines[0].rstrip()
        rest = "\n".join(lines[1:]).lstrip()
        return f"{head}\n\n{model_line}\n\n{rest}" if rest else f"{head}\n\n{model_line}"

    content = markdown_content.strip()
    return f"{model_line}\n\n{content}" if content else model_line


def process_single_video(bvid: str):
    """处理单个视频的完整流程（使用新路径结构）"""
    db = get_db()
    pm = get_path_manager()

    try:
        video = db.query(Video).filter_by(bvid=bvid).first()
        if not video:
            logger.info("视频不存在: %s，自动拉取结构并建表", bvid)
            detail = fetch_video_detail(bvid)
            video = Video(
                bvid=detail.get("bvid") or bvid,
                title=detail.get("title") or bvid,
                mid=str(detail.get("mid") or ""),
                pub_time=detail.get("pub_time"),
                status="pending",
            )
            db.add(video)
            db.commit()
            video = db.query(Video).filter_by(bvid=bvid).first()
            if not video:
                logger.warning("视频创建失败: %s", bvid)
                return

        # 检查视频发布时间是否超过12小时
        if video.pub_time and not is_dynamic_recent(video.pub_time):
            logger.info("视频发布时间超过12小时，跳过推送: %s", bvid)
            video.status = "filtered"
            video.last_error = "发布时间超过12小时"
            db.commit()
            return

        # 获取 UP 主信息
        uploader_name, uploader_mid = get_uploader_info(db, video.mid)

        logger.info("开始处理视频 %s | UP主: %s | 标题: %s", bvid, uploader_name, video.title)
        video.status = "processing"
        db.commit()
        video_pub_time_str = _format_pub_time(video.pub_time)

        # 获取新路径结构
        paths = pm.get_video_paths(uploader_name, bvid, video.title, video.pub_time, uploader_mid)

        # 第0步：检查是否已有识别后的文本（优先检查新路径）
        subtitles = ""
        transcript_text = (video.transcript_text or "").strip()
        if paths["transcript"].exists():
            logger.debug("[文本] 发现已有识别文本（新路径）: %s", paths["transcript"])
            subtitles = paths["transcript"].read_text("utf-8")
        elif transcript_text:
            logger.debug("[文本] 发现已有识别文本（数据库）: %s", video.id)
            subtitles = transcript_text
            paths["transcript"].write_text(subtitles, "utf-8")
            logger.debug("[文本] 已同步到新路径: %s", paths["transcript"])
        else:
            # 检查旧路径
            old_text_file = TEXT_DIR / f"{bvid}.txt"
            if old_text_file.exists():
                logger.debug("[文本] 发现已有识别文本（旧路径）: %s", old_text_file)
                subtitles = old_text_file.read_text("utf-8")
                # 复制到新路径
                paths["transcript"].write_text(subtitles, "utf-8")
                logger.debug("[文本] 已迁移到新路径: %s", paths["transcript"])

        if not subtitles:
            # 第1步：获取字幕
            logger.debug("[字幕] 尝试从B站获取...")
            subtitles = get_subtitles(bvid)
            video.has_subtitle = bool(subtitles)

            if subtitles:
                logger.debug("[字幕] 获取成功，长度: %d", len(subtitles))
            else:
                # 第2步：检查是否已下载过视频或音频（优先检查新路径）
                media_path = None
                media_type = None

                # 先检查新路径下的视频
                if video.has_video and paths["video"].exists():
                    logger.debug("[视频] 复用已有视频文件（新路径）: %s", paths["video"])
                    media_path = str(paths["video"])
                    media_type = "video"
                # 再检查新路径下的音频
                elif video.has_audio and paths["audio"].exists():
                    logger.debug("[音频] 复用已有音频文件（新路径）: %s", paths["audio"])
                    media_path = str(paths["audio"])
                    media_type = "audio"
                else:
                    # 回退到旧路径检查
                    if video.has_video and video.video_path:
                        check_path = video.video_path
                        if not os.path.isabs(check_path):
                            check_path = str(_resolve_stored_path(check_path))
                        if os.path.exists(check_path):
                            logger.debug("[视频] 复用已有视频文件（旧路径）: %s", check_path)
                            media_path = check_path
                            media_type = "video"
                            # 复制到新路径
                            import shutil
                            shutil.copy2(check_path, paths["video"])
                            video.video_path = str(Path(paths["video"]).resolve())
                            logger.debug("[视频] 已迁移到新路径: %s", paths["video"])

                    if not media_path and video.has_audio and video.audio_path:
                        check_path = video.audio_path
                        if not os.path.isabs(check_path):
                            check_path = str(_resolve_stored_path(check_path))
                        if os.path.exists(check_path):
                            logger.debug("[音频] 复用已有音频文件（旧路径）: %s", check_path)
                            media_path = check_path
                            media_type = "audio"
                            # 复制到新路径
                            import shutil
                            shutil.copy2(check_path, paths["audio"])
                            video.audio_path = str(Path(paths["audio"]).resolve())
                            logger.debug("[音频] 已迁移到新路径: %s", paths["audio"])

                # 如果都没有，下载音频
                if not media_path:
                    logger.info("[媒体] 未找到视频或音频文件，开始下载音频...")
                    try:
                        from app.modules.downloader import download_audio_new
                        audio_file = download_audio_new(
                            bvid=bvid,
                            mid=video.mid,
                            title=video.title,
                            pub_time=video.pub_time,
                            uploader_name=uploader_name
                        )
                        if audio_file and Path(audio_file).exists():
                            media_path = audio_file
                            media_type = "audio"
                            video.has_audio = True
                            video.audio_path = str(Path(audio_file).resolve())
                            logger.info("[音频] 下载成功: %s", audio_file)
                        else:
                            logger.warning("[音频] 下载失败或文件不存在")
                            subtitles = ""
                            media_path = None
                    except Exception as e:
                        logger.error("[音频] 下载失败: %s", e)
                        subtitles = ""
                        media_path = None

                # 用ASR转写
                if media_path:
                    logger.info("[%s] 开始识别，识别中请稍候...", media_type)
                    try:
                        subtitles = transcribe_audio(media_path)
                        logger.info("[%s] 识别完成，文本长度 %d", media_type, len(subtitles))
                    except Exception as e:
                        logger.error("[%s] 识别失败: %s", media_type, e)
                        subtitles = ""

        if subtitles:
            video.transcript_text = subtitles
            video.has_subtitle = True
            if not paths["transcript"].exists():
                paths["transcript"].write_text(subtitles, "utf-8")
                logger.debug("[保存] 文本已保存: %s", paths["transcript"])

        # 第3步：统一 LLM 处理（纠错 + 总结）
        summary_data = None
        if subtitles:
            logger.debug("[LLM] 开始统一处理（纠错+总结）...")
            process_result = process_text(
                raw_text=subtitles,
                video_title=video.title,
                duration=0,
                content_type="video",
                content_id=bvid,
                uploader_name=uploader_name,
            )
            summary_data = {
                "summary": process_result.get("summary", ""),
                "details": process_result.get("details", ""),
                "key_points": process_result.get("key_points", []),
                "tags": process_result.get("tags", []),
                "stocks": process_result.get("stocks", []),
                "insights": process_result.get("insights", ""),
                "duration_minutes": 0
            }
            video.summary_json = json.dumps(summary_data, ensure_ascii=False)
            logger.debug("[LLM] 处理完成")

            push_payload = {
                "type": "video",
                "content_id": bvid,
                "mid": video.mid,
                "title": video.title,
                "uploader_name": uploader_name,
                "summary": summary_data.get("summary", ""),
                "details": summary_data.get("details", ""),
                "key_points": summary_data.get("key_points", []),
                "tags": summary_data.get("tags", []),
                "stocks": summary_data.get("stocks", []),
                "insights": summary_data.get("insights", ""),
                "text": subtitles,
                "url": f"https://www.bilibili.com/video/{bvid}",
                "pub_time": video_pub_time_str,
                "timestamp": video.pub_time,
                "duration_minutes": summary_data.get("duration_minutes", 0),
            }
            push_filter = classify_push_relevance(
                push_payload,
                content_type="video",
                content_id=bvid,
                content_title=video.title,
                uploader_name=uploader_name,
            )
            summary_data["push_filter"] = push_filter
            video.summary_json = json.dumps(summary_data, ensure_ascii=False)
            if not push_filter.get("should_push", True):
                reason = str(push_filter.get("reason") or "内容与投资/宏观/社会完全无关，已跳过推送")
                logger.info("[LLM] 视频内容无关，跳过推送: %s | %s", bvid, reason)
                push_content({**push_payload, "push_filter": push_filter}, ["feishu"])
                video.status = "filtered"
                video.last_error = reason[:200]
                db.commit()
                return

            # 保存 summary 到新路径
            md_content = f"# {video.title}\n\n"
            md_content += f"**URL**: https://www.bilibili.com/video/{bvid}\n\n"
            md_content += f"**UP主**: {uploader_name}\n\n"
            video_pub_time_str = _format_pub_time(video.pub_time)
            if video_pub_time_str:
                md_content += f"**发布时间**: {video_pub_time_str}\n\n"
            else:
                md_content += "**发布时间**: 未知\n\n"
            md_content += "---\n\n"
            md_content += summary_data["details"]

            if not paths["summary"].exists():
                paths["summary"].write_text(md_content, "utf-8")
                logger.debug("[保存] 详情已保存: %s", paths["summary"])

            # 上传到飞书文档
            doc_url = None
            try:
                doc_markdown = _prepend_usage_model_note(md_content, _resolve_summary_model_name("video_summary"))
                doc_result = push_video_summary_to_doc(
                    title=video.title,
                    markdown_content=doc_markdown,
                    bvid=bvid,
                    pub_time=video.pub_time,
                    uploader_name=uploader_name
                )
                if doc_result:
                    doc_url = doc_result.get("url")
                    video.doc_url = doc_url
                    logger.info("[飞书文档] 创建成功: %s", doc_url)
            except Exception as e:
                logger.warning("[飞书文档] 创建失败: %s", e)

        else:
            logger.warning("[LLM] 无字幕和音频，跳过处理")
            summary_data = {
                "summary": f"无法获取字幕或音频: {video.title}",
                "details": "",
                "key_points": [],
                "tags": [],
                "stocks": [],
                "insights": "",
                "duration_minutes": 0
            }
            video.summary_json = json.dumps(summary_data, ensure_ascii=False)
            push_payload = {
                "type": "video",
                "content_id": bvid,
                "mid": video.mid,
                "title": video.title,
                "uploader_name": uploader_name,
                "summary": summary_data.get("summary", ""),
                "details": summary_data.get("details", ""),
                "key_points": summary_data.get("key_points", []),
                "tags": summary_data.get("tags", []),
                "stocks": summary_data.get("stocks", []),
                "insights": summary_data.get("insights", ""),
                "text": "",
                "url": f"https://www.bilibili.com/video/{bvid}",
                "pub_time": video_pub_time_str,
                "timestamp": video.pub_time,
                "duration_minutes": summary_data.get("duration_minutes", 0),
            }
            push_filter = classify_push_relevance(
                push_payload,
                content_type="video",
                content_id=bvid,
                content_title=video.title,
                uploader_name=uploader_name,
            )
            summary_data["push_filter"] = push_filter
            video.summary_json = json.dumps(summary_data, ensure_ascii=False)
            if not push_filter.get("should_push", True):
                reason = str(push_filter.get("reason") or "内容与投资/宏观/社会完全无关，已跳过推送")
                logger.info("[LLM] 视频内容无关，跳过推送: %s | %s", bvid, reason)
                push_content({**push_payload, "push_filter": push_filter}, ["feishu"])
                video.status = "filtered"
                video.last_error = reason[:200]
                db.commit()
                return
            doc_url = None

        # 第4步：推送
        logger.debug("[推送] 开始推送...")
        push_result = push_content({
            "type": "video",
            "content_id": bvid,
            "mid": video.mid,
            "title": video.title,
            "uploader_name": uploader_name,
            "summary": summary_data.get("summary", ""),
            "details": summary_data.get("details", ""),
            "key_points": summary_data.get("key_points", []),
            "tags": summary_data.get("tags", []),
            "stocks": summary_data.get("stocks", []),
            "insights": summary_data.get("insights", ""),
            "text": subtitles,
            "url": f"https://www.bilibili.com/video/{bvid}",
            "doc_url": doc_url,
            "pub_time": video_pub_time_str,
            "duration_minutes": summary_data.get("duration_minutes", 0),
            "timestamp": video.pub_time,
            "push_filter": push_filter,
        }, ["feishu"])

        if push_result.get("silented"):
            video.status = "silented"
            video.last_error = str(push_result.get("reason") or "静音时段，推送暂缓")[:200]
        elif push_result.get("skipped"):
            video.status = "filtered"
            video.last_error = str(push_result.get("reason") or push_filter.get("reason") or "内容与投资/宏观/社会完全无关")[:200]
        elif not push_result.get("success", False):
            raise RuntimeError(str(push_result.get("reason") or "push failed"))
        else:
            video.status = "done"
            video.last_error = None

        db.commit()
        logger.info("✅ 处理完成: %s", bvid)

    except Exception as e:
        logger.error("❌ 处理失败 %s: %s", bvid, e, exc_info=True)
        try:
            # 重新获取 video 对象，避免 session 问题
            video = db.query(Video).filter_by(bvid=bvid).first()
            if video:
                video.status = "failed"
                video.last_error = str(e)[:200]
                video.attempt_count += 1

                if video.attempt_count >= 3:
                    logger.error("放弃重试: %s (已尝试3次)", bvid)
                else:
                    logger.info("将重新入队: %s (第%d次重试)", bvid, video.attempt_count)

                db.commit()
        except Exception as db_err:
            logger.error("更新视频状态失败: %s", db_err)
    finally:
        db.close()


def process_single_dynamic(dynamic_id: str):
    """处理单个动态的完整流程"""
    db = get_db()
    pm = get_path_manager()
    try:
        dynamic = db.query(Dynamic).filter_by(dynamic_id=dynamic_id).first()
        if not dynamic:
            logger.info("动态不存在: %s，自动拉取结构并建表", dynamic_id)
            detail = fetch_dynamic_detail(dynamic_id)
            dynamic = Dynamic(
                dynamic_id=detail.get("dynamic_id") or dynamic_id,
                mid=str(detail.get("mid") or ""),
                type=detail.get("type"),
                text=detail.get("text") or "",
                image_count=len(detail.get("image_urls") or []),
                images_path=json.dumps([], ensure_ascii=False),
                image_urls=json.dumps(detail.get("image_urls") or [], ensure_ascii=False),
                status="pending",
                push_status="pending",
                pub_time=detail.get("pub_time"),
            )
            db.add(dynamic)
            db.commit()
            dynamic = db.query(Dynamic).filter_by(dynamic_id=dynamic_id).first()
            if not dynamic:
                logger.warning("动态创建失败: %s", dynamic_id)
                return

        dynamic_text = dynamic.text or ""
        logger.info("开始处理动态 %s | 内容: %s...", dynamic_id, dynamic_text[:50])
        dynamic.status = "processing"
        db.commit()

        if dynamic.pub_time and not is_dynamic_recent(dynamic.pub_time):
            logger.info("动态发布时间超过12小时，跳过推送: %s", dynamic_id)
            dynamic.status = "filtered"
            dynamic.last_error = "发布时间超过12小时"
            db.commit()
            return

        # 预过滤
        if (dynamic.type or "") == "DYNAMIC_TYPE_AV":
            logger.info("鍔ㄦ€佷负瑙嗛鍗℃锛屼粎鍏ユ暟鎹簱涓嶆帹閫? %s", dynamic_id)
            dynamic.status = "sent"
            dynamic.pushed_at = datetime.utcnow()
            dynamic.last_error = None
            db.commit()
            return

        if not should_push_dynamic({"text": dynamic_text}):
            logger.info("动态不符合推送条件: %s", dynamic_id)
            dynamic.status = "filtered"
            dynamic.last_error = "预过滤过滤不符合"
            db.commit()
            return

        # 准备推送数据
        image_paths = json.loads(dynamic.images_path or "[]") if dynamic.images_path else []
        image_urls = json.loads(dynamic.image_urls or "[]") if dynamic.image_urls else []
        uploader_name, _uploader_mid = get_uploader_info(db, dynamic.mid)
        pub_time_str = _format_pub_time(dynamic.pub_time)
        dynamic_url = f"https://www.bilibili.com/opus/{dynamic.dynamic_id}"
        paths = pm.get_dynamic_paths(uploader_name, dynamic.dynamic_id, dynamic.mid)

        logger.debug("[动态数据] 文本: %d字, 图片: %d张", len(dynamic_text), len(image_paths))

        # 统一 LLM 处理（整理 + 总结）
        summary_data = process_dynamic_text(
            raw_text=dynamic_text,
            uploader_name=uploader_name,
            pub_time=pub_time_str,
            dynamic_url=dynamic_url,
        )

        if not isinstance(summary_data, dict):
            summary_data = {}

        dynamic.summary_json = json.dumps(summary_data, ensure_ascii=False)

        push_payload = {
            "type": "dynamic",
            "content_id": dynamic.dynamic_id,
            "mid": dynamic.mid,
            "uploader_name": uploader_name,
            "text": dynamic_text,
            "summary": summary_data.get("summary", "") or (dynamic.text or "")[:80],
            "details": summary_data.get("details", "") or "",
            "key_points": summary_data.get("key_points", []),
            "tags": summary_data.get("tags", []),
            "stocks": summary_data.get("stocks", []),
            "insights": summary_data.get("insights", ""),
            "url": dynamic_url,
            "pub_time": pub_time_str,
        }
        push_filter = classify_push_relevance(
            push_payload,
            content_type="dynamic",
            content_id=dynamic.dynamic_id,
            content_title=summary_data.get("summary", "") or (dynamic.text or "")[:80],
            uploader_name=uploader_name,
        )
        summary_data["push_filter"] = push_filter
        dynamic.summary_json = json.dumps(summary_data, ensure_ascii=False)

        if not push_filter.get("should_push", True):
            reason = str(push_filter.get("reason") or "内容与投资/宏观/社会完全无关，已跳过推送")
            logger.info("[LLM] 动态内容无关，跳过推送: %s | %s", dynamic_id, reason)
            push_content({**push_payload, "push_filter": push_filter}, ["feishu"])
            dynamic.status = "filtered"
            dynamic.push_status = "skipped"
            dynamic.last_error = reason[:200]
            db.commit()
            return

        summary_text = summary_data.get("summary", "") or (dynamic.text or "")[:80]
        details_text = summary_data.get("details", "") or ""
        markdown_content = f"# {summary_text}\n\n"
        markdown_content += f"**作者**: {uploader_name}\n\n"
        markdown_content += f"**发布时间**: {pub_time_str or '未知'}\n\n"
        markdown_content += f"**原动态链接**: {dynamic_url}\n\n"
        markdown_content += "---\n\n"
        markdown_content += "## 原始动态\n\n"
        markdown_content += f"{dynamic_text.strip()}\n\n"
        if details_text:
            markdown_content += "---\n\n"
            markdown_content += details_text

        if dynamic_text and not paths["text"].exists():
            paths["text"].write_text(dynamic_text, "utf-8")
            logger.debug("[保存] 动态原文已保存: %s", paths["text"])

        if markdown_content and not paths["summary"].exists():
            paths["summary"].write_text(markdown_content, "utf-8")
            logger.debug("[保存] 动态总结已保存: %s", paths["summary"])

        doc_url = None
        try:
            doc_markdown = _prepend_usage_model_note(markdown_content, _resolve_summary_model_name("dynamic_summary"))
            doc_result = push_dynamic_summary_to_doc(
                title=summary_text,
                markdown_content=doc_markdown,
                dynamic_id=dynamic.dynamic_id,
                pub_time=int(dynamic.pub_time.timestamp()) if dynamic.pub_time else None,
                uploader_name=uploader_name,
            )
            if doc_result:
                doc_url = doc_result.get("url")
                dynamic.doc_url = doc_url
                logger.info("[飞书文档] 动态总结创建成功: %s", doc_url)
        except Exception as e:
            logger.warning("[飞书文档] 动态总结创建失败: %s", e)

        # 推送
        push_result = push_content({
            "type": "dynamic",
            "content_id": dynamic.dynamic_id,
            "mid": dynamic.mid,
            "uploader_name": uploader_name,
            "text": dynamic_text,
            "images": image_paths,
            "image_urls": image_urls,
            "summary": summary_text,
            "details": details_text,
            "key_points": summary_data.get("key_points", []),
            "tags": summary_data.get("tags", []),
            "stocks": summary_data.get("stocks", []),
            "insights": summary_data.get("insights", ""),
            "pub_time": pub_time_str,
            "timestamp": dynamic.pub_time,
            "url": dynamic_url,
            "doc_url": doc_url,
            "push_filter": push_filter,
        }, ["feishu"])

        if push_result.get("silented"):
            dynamic.status = "silented"
            dynamic.push_status = "silented"
            dynamic.last_error = str(push_result.get("reason") or "静音时段，推送暂缓")[:200]
        elif push_result.get("skipped"):
            dynamic.status = "filtered"
            dynamic.push_status = "skipped"
            dynamic.last_error = str(push_result.get("reason") or push_filter.get("reason") or "内容与投资/宏观/社会完全无关")[:200]
        elif not push_result.get("success", False):
            raise RuntimeError(str(push_result.get("reason") or "push failed"))
        else:
            dynamic.status = "sent"
            dynamic.push_status = "success"
            dynamic.pushed_at = datetime.utcnow()
            dynamic.last_error = None

        db.commit()
        logger.info("✅ 动态推送完成: %s", dynamic_id)

    except Exception as e:
        logger.error("❌ 动态处理失败 %s: %s", dynamic_id, e, exc_info=True)
        try:
            dynamic = db.query(Dynamic).filter_by(dynamic_id=dynamic_id).first()
            if dynamic:
                dynamic.status = "failed"
                dynamic.push_status = "failed"
                dynamic.last_error = str(e)[:200]
                dynamic.attempt_count += 1

                if dynamic.attempt_count >= 3:
                    logger.error("放弃重试: %s (已尝试3次)", dynamic_id)
                else:
                    logger.info("将重新入队: %s (第%d次重试)", dynamic_id, dynamic.attempt_count)

                db.commit()
        except Exception as db_err:
            logger.error("更新动态状态失败: %s", db_err)
    finally:
        db.close()


def process_single_podcast_episode(eid: str):
    """处理单个小宇宙单集的完整流程。"""
    db = get_db()
    pm = get_path_manager()

    try:
        episode = db.query(PodcastEpisode).filter_by(eid=eid).first()
        if not episode:
            logger.warning("小宇宙单集不存在: %s", eid)
            return

        podcast_name, podcast_pid = get_podcast_info(db, episode.pid)
        episode.status = "processing"
        episode.push_status = "processing"
        db.commit()

        pub_time_str = _format_pub_time(episode.pub_time)
        pub_ts = int(episode.pub_time.timestamp()) if episode.pub_time else None
        paths = pm.get_podcast_episode_paths(podcast_name, eid, episode.title, pub_ts, podcast_pid)

        subtitles = ""
        if paths["transcript"].exists():
            subtitles = paths["transcript"].read_text("utf-8")
        elif episode.local_transcript_path:
            check_path = episode.local_transcript_path
            if not os.path.isabs(check_path):
                check_path = str(_resolve_stored_path(check_path))
            if os.path.exists(check_path):
                subtitles = Path(check_path).read_text("utf-8")
                paths["transcript"].write_text(subtitles, "utf-8")

        media_path = None
        if not subtitles:
            if paths["audio"].exists():
                media_path = str(paths["audio"])
            elif episode.local_audio_path:
                check_path = episode.local_audio_path
                if not os.path.isabs(check_path):
                    check_path = str(_resolve_stored_path(check_path))
                if os.path.exists(check_path):
                    media_path = check_path
                    import shutil

                    shutil.copy2(check_path, paths["audio"])
                    episode.local_audio_path = str(Path(paths["audio"]).resolve())

        if not media_path:
            if not episode.audio_url:
                raise RuntimeError("missing podcast audio url")
            downloaded_audio = download_episode_audio(episode.audio_url, paths["audio"])
            media_path = str(downloaded_audio)
            episode.local_audio_path = str(Path(downloaded_audio).resolve())
            episode.downloaded_at = datetime.utcnow()
            episode.download_attempts = int(episode.download_attempts or 0) + 1

        if media_path and not subtitles:
            try:
                subtitles = transcribe_audio(media_path)
                episode.transcribed_at = datetime.utcnow()
                episode.asr_attempts = int(episode.asr_attempts or 0) + 1
            except Exception as exc:
                episode.status = "failed_asr"
                episode.push_status = "failed"
                episode.last_error = str(exc)[:200]
                episode.attempt_count += 1
                db.commit()
                raise

        summary_data = None
        episode_url = f"https://www.xiaoyuzhoufm.com/episode/{eid}"
        if subtitles:
            process_result = process_podcast_text(
                raw_text=subtitles,
                uploader_name=podcast_name,
                pub_time=pub_time_str,
                episode_url=episode_url,
            )
            summary_data = {
                "summary": process_result.get("summary", ""),
                "details": process_result.get("details", ""),
                "key_points": process_result.get("key_points", []),
                "stocks": process_result.get("stocks", []),
                "insights": process_result.get("insights", ""),
                "duration_minutes": 0,
            }
            episode.summary_json = json.dumps(summary_data, ensure_ascii=False)

            push_payload = {
                "type": "podcast",
                "content_id": eid,
                "title": episode.title,
                "uploader_name": podcast_name,
                "summary": summary_data.get("summary", ""),
                "details": summary_data.get("details", ""),
                "key_points": summary_data.get("key_points", []),
                "tags": [],
                "stocks": summary_data.get("stocks", []),
                "insights": summary_data.get("insights", ""),
                "text": subtitles,
                "url": episode_url,
                "pub_time": pub_time_str,
                "timestamp": episode.pub_time,
                "duration_minutes": 0,
            }
            push_filter = classify_push_relevance(
                push_payload,
                content_type="podcast",
                content_id=eid,
                content_title=episode.title,
                uploader_name=podcast_name,
            )
            summary_data["push_filter"] = push_filter
            episode.summary_json = json.dumps(summary_data, ensure_ascii=False)

            if not push_filter.get("should_push", True):
                reason = str(push_filter.get("reason") or "内容与投资/宏观/社会完全无关，已跳过推送")
                logger.info("[LLM] 小宇宙内容无关，跳过推送: %s | %s", eid, reason)
                push_content({**push_payload, "push_filter": push_filter}, ["feishu"])
                episode.status = "filtered"
                episode.push_status = "skipped"
                episode.last_error = reason[:200]
                db.commit()
                return

            markdown_content = f"# {episode.title}\n\n"
            markdown_content += f"**作者**: {podcast_name}\n\n"
            markdown_content += f"**发布时间**: {pub_time_str or '未知'}\n\n"
            markdown_content += f"**原链接**: {episode_url}\n\n"
            markdown_content += "---\n\n"
            markdown_content += "## 原始转写\n\n"
            markdown_content += f"{subtitles.strip()}\n\n"
            if summary_data.get("details"):
                markdown_content += "---\n\n"
                markdown_content += summary_data["details"]

            if subtitles and not paths["transcript"].exists():
                paths["transcript"].write_text(subtitles, "utf-8")
                episode.local_transcript_path = str(Path(paths["transcript"]).resolve())

            if markdown_content and not paths["summary"].exists():
                paths["summary"].write_text(markdown_content, "utf-8")
                episode.local_summary_path = str(Path(paths["summary"]).resolve())

            doc_url = None
            try:
                doc_markdown = _prepend_usage_model_note(markdown_content, _resolve_summary_model_name("podcast_summary"))
                doc_result = push_podcast_summary_to_doc(
                    title=episode.title,
                    markdown_content=doc_markdown,
                    episode_id=eid,
                    pub_time=pub_ts,
                    uploader_name=podcast_name,
                )
                if doc_result:
                    doc_url = doc_result.get("url")
                    episode.doc_url = doc_url
                    logger.info("[飞书文档] 小宇宙节目创建成功: %s", doc_url)
            except Exception as exc:
                logger.warning("[飞书文档] 小宇宙节目创建失败: %s", exc)

            push_result = push_content(
                {
                    "type": "podcast",
                    "content_id": eid,
                    "title": episode.title,
                    "uploader_name": podcast_name,
                    "summary": summary_data.get("summary", ""),
                    "details": summary_data.get("details", ""),
                    "key_points": summary_data.get("key_points", []),
                    "tags": [],
                    "stocks": summary_data.get("stocks", []),
                    "insights": summary_data.get("insights", ""),
                    "text": subtitles,
                    "url": episode_url,
                    "doc_url": doc_url,
                    "pub_time": pub_time_str,
                    "timestamp": episode.pub_time,
                    "duration_minutes": 0,
                    "push_filter": push_filter,
                },
                ["feishu"],
            )

            if push_result.get("silented"):
                episode.status = "silented"
                episode.push_status = "silented"
                episode.last_error = str(push_result.get("reason") or "静音时段，推送暂缓")[:200]
            elif push_result.get("skipped"):
                episode.status = "filtered"
                episode.push_status = "skipped"
                episode.last_error = str(push_result.get("reason") or push_filter.get("reason") or "内容被过滤")[:200]
            elif not push_result.get("success", False):
                raise RuntimeError(str(push_result.get("reason") or "push failed"))
            else:
                episode.status = "done"
                episode.push_status = "success"
                episode.pushed_at = datetime.utcnow()
                episode.last_error = None
        else:
            logger.warning("[LLM] 无字幕和音频，跳过处理")
            summary_data = {
                "summary": f"无法获取字幕或音频: {episode.title}",
                "details": "",
                "key_points": [],
                "stocks": [],
                "insights": "",
                "duration_minutes": 0,
            }
            episode.summary_json = json.dumps(summary_data, ensure_ascii=False)
            push_payload = {
                "type": "podcast",
                "content_id": eid,
                "title": episode.title,
                "uploader_name": podcast_name,
                "summary": summary_data.get("summary", ""),
                "details": summary_data.get("details", ""),
                "key_points": summary_data.get("key_points", []),
                "tags": [],
                "stocks": summary_data.get("stocks", []),
                "insights": summary_data.get("insights", ""),
                "text": "",
                "url": episode_url,
                "pub_time": pub_time_str,
                "timestamp": episode.pub_time,
                "duration_minutes": 0,
            }
            push_result = push_content(push_payload, ["feishu"])
            if push_result.get("silented"):
                episode.status = "silented"
                episode.push_status = "silented"
                episode.last_error = str(push_result.get("reason") or "静音时段，推送暂缓")[:200]
            elif push_result.get("skipped"):
                episode.status = "filtered"
                episode.push_status = "skipped"
                episode.last_error = str(push_result.get("reason") or "内容被过滤")[:200]
            elif not push_result.get("success", False):
                episode.status = "failed"
                episode.push_status = "failed"
                episode.last_error = str(push_result.get("reason") or "push failed")[:200]
            else:
                episode.status = "done"
                episode.push_status = "success"
                episode.pushed_at = datetime.utcnow()
                episode.last_error = None

        db.commit()
        logger.info("✅ 小宇宙单集处理完成: %s", eid)

    except Exception as e:
        logger.error("❌ 小宇宙单集处理失败 %s: %s", eid, e, exc_info=True)
        try:
            episode = db.query(PodcastEpisode).filter_by(eid=eid).first()
            if episode:
                if episode.status not in {"filtered", "done"}:
                    episode.status = "failed"
                    episode.push_status = "failed"
                episode.last_error = str(e)[:200]
                episode.attempt_count += 1
                if episode.status == "failed_asr":
                    episode.asr_attempts = int(episode.asr_attempts or 0)
                elif episode.status == "failed_download":
                    episode.download_attempts = int(episode.download_attempts or 0)
                elif episode.status == "failed_summary":
                    episode.summary_attempts = int(episode.summary_attempts or 0)
                db.commit()
        except Exception as db_err:
            logger.error("更新小宇宙状态失败: %s", db_err)
    finally:
        db.close()


def start_queue_worker(max_workers: int = 3):
    """启动队列处理worker，持续处理待处理任务"""
    logger.info("=" * 50)
    logger.info("队列处理线程启动，max_workers=%d", max_workers)
    logger.info("=" * 50)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        loop_count = 0
        while True:
            loop_count += 1

            try:
                db = get_db()
                try:
                    # 静音时段结束，恢复 silented 状态的任务为 pending（重新推送）
                    if not is_silent_mode():
                        for model_cls in (Video, Dynamic, PodcastEpisode):
                            silented_items = db.query(model_cls).filter_by(status="silented").all()
                            for item in silented_items:
                                item.status = "pending"
                                item.last_error = None
                        if silented_items:
                            db.commit()
                            logger.info("[静音恢复] 已将 %d 个任务恢复为 pending", len(silented_items))

                    # 优先处理动态（处理快）- 按发布时间升序，先处理最早的
                    pending_dynamics = db.query(Dynamic).filter_by(
                        status="pending"
                    ).order_by(Dynamic.pub_time.asc().nullslast()).limit(5).all()

                    pending_podcasts = db.query(PodcastEpisode).filter_by(
                        status="pending"
                    ).order_by(PodcastEpisode.pub_time.asc().nullslast()).limit(5).all()

                    # 然后处理视频
                    pending_videos = db.query(Video).filter_by(
                        status="pending"
                    ).order_by(Video.created_at).limit(5).all()

                    # 处理已失败但还能重试的任务
                    retry_videos = db.query(Video).filter_by(
                        status="failed"
                    ).filter(Video.attempt_count < 3).limit(2).all()

                    retry_dynamics = db.query(Dynamic).filter_by(
                        status="failed"
                    ).filter(Dynamic.attempt_count < 3).limit(2).all()

                    retry_podcasts = db.query(PodcastEpisode).filter(
                        PodcastEpisode.status.in_(["failed", "failed_download", "failed_asr", "failed_summary"])
                    ).filter(PodcastEpisode.attempt_count < 3).limit(2).all()

                    total_pending = len(pending_dynamics) + len(pending_podcasts) + len(pending_videos)
                    total_retry = len(retry_videos) + len(retry_dynamics) + len(retry_podcasts)

                    if loop_count % 6 == 0:  # 每30秒（6个5秒循环）打印一次统计
                        logger.info(
                            "[定期统计] 待处理动态: %d, 待处理小宇宙: %d, 待处理视频: %d, 重试队列: %d",
                            len(pending_dynamics),
                            len(pending_podcasts),
                            len(pending_videos),
                            total_retry,
                        )

                    if (
                        not pending_dynamics
                        and not pending_podcasts
                        and not pending_videos
                        and not retry_dynamics
                        and not retry_podcasts
                        and not retry_videos
                    ):
                        logger.debug("暂无待处理任务，休眠...")
                        time.sleep(30)
                        continue

                    # 提交动态任务 - 先更新状态为 processing
                    for dyn in pending_dynamics:
                        dyn.status = "processing"
                        retry_on_db_lock()(db.commit)()
                        executor.submit(process_single_dynamic, dyn.dynamic_id)

                    for episode in pending_podcasts:
                        episode.status = "processing"
                        retry_on_db_lock()(db.commit)()
                        executor.submit(process_single_podcast_episode, episode.eid)

                    # 提交已失败但可重试的动态 - 先更新状态为 processing
                    for dyn in retry_dynamics:
                        logger.info("重新处理失败动态: %s (第%d次重试)", dyn.dynamic_id, dyn.attempt_count + 1)
                        dyn.status = "processing"
                        retry_on_db_lock()(db.commit)()
                        executor.submit(process_single_dynamic, dyn.dynamic_id)

                    for episode in retry_podcasts:
                        logger.info("重新处理失败小宇宙单集: %s (第%d次重试)", episode.eid, episode.attempt_count + 1)
                        episode.status = "processing"
                        retry_on_db_lock()(db.commit)()
                        executor.submit(process_single_podcast_episode, episode.eid)

                    # 提交视频任务 - 先更新状态为 processing
                    for vid in pending_videos:
                        vid.status = "processing"
                        retry_on_db_lock()(db.commit)()
                        executor.submit(process_single_video, vid.bvid)

                    # 提交已失败但可重试的视频 - 先更新状态为 processing
                    for vid in retry_videos:
                        logger.info("重新处理失败视频: %s (第%d次重试)", vid.bvid, vid.attempt_count + 1)
                        vid.status = "processing"
                        retry_on_db_lock()(db.commit)()
                        executor.submit(process_single_video, vid.bvid)

                    time.sleep(5)

                finally:
                    db.close()

            except Exception as e:
                logger.error("队列处理循环异常: %s", e, exc_info=True)
                time.sleep(10)  # 出错时休眠较长时间
