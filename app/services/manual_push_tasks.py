from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.database import ManualPushTask, Video, create_session
from app.modules.bilibili import fetch_video_detail
from app.modules.downloader import download_audio_new
from app.modules.feishu_docs import push_video_summary_to_doc
from app.modules.processor import classify_push_relevance, process_text
from app.modules.push import push_content
from app.modules.subtitle import get_subtitles
from app.modules.whisper_ai import transcribe_audio
from app.queue_worker import (
    _format_pub_time,
    _prepend_usage_model_note,
    _resolve_summary_model_name,
    get_uploader_info,
)
from app.services.push_targets import (
    get_default_push_target,
    get_push_target_by_id,
    serialize_push_target_row,
)
from app.utils.logger import get_logger
from app.utils.paths import get_path_manager
from app.utils.runtime_home import get_data_dir
from config import Config

logger = get_logger("manual_push")

_BV_PATTERN = re.compile(r"^BV[0-9A-Za-z]{10}$")
_LOCAL_SOURCE_TYPE = "local_video"
_BILIBILI_SOURCE_TYPE = "bilibili"
_LOCAL_UPLOADER_NAME = "本地视频"
_LOCAL_PUSH_WORKERS = 4
_MANUAL_PUSH_EXECUTOR = ThreadPoolExecutor(
    max_workers=_LOCAL_PUSH_WORKERS,
    thread_name_prefix="manual-push",
)


def _make_session():
    return create_session(
        sqlite_timeout_seconds=3,
        pool_timeout_seconds=3,
        sqlite_busy_timeout_ms=3000,
    )


def normalize_bvid(raw_bvid: str) -> str:
    value = (raw_bvid or "").strip()
    if not value:
        raise ValueError("bvid required")
    if not _BV_PATTERN.match(value):
        raise ValueError("invalid bvid")
    return value


def _loads_json(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


def _task_source_type(row: ManualPushTask) -> str:
    value = getattr(row, "source_type", None) or _BILIBILI_SOURCE_TYPE
    return str(value)


def _task_source_url(row: ManualPushTask) -> str | None:
    if _task_source_type(row) == _LOCAL_SOURCE_TYPE:
        return None
    return f"https://www.bilibili.com/video/{row.bvid}"


def _local_task_identifier(source_path: str) -> str:
    digest = hashlib.md5(source_path.encode("utf-8")).hexdigest()[:12].upper()
    return f"LOCAL-{digest}"


def _normalize_local_source_path(raw_path: str) -> str:
    value = (raw_path or "").strip()
    if not value:
        raise ValueError("source_path required")
    return str(Path(value).expanduser().resolve())


def _local_artifact_paths(source_path: str) -> dict[str, Path]:
    path_hash = hashlib.md5(source_path.encode("utf-8")).hexdigest()
    base_dir = get_data_dir() / "manual_push" / "local_video" / path_hash
    base_dir.mkdir(parents=True, exist_ok=True)
    return {
        "dir": base_dir,
        "transcript": base_dir / "transcript.txt",
        "summary": base_dir / "summary.md",
    }


def _parse_scan_dirs(raw_value: str) -> list[Path]:
    items: list[Path] = []
    for part in (raw_value or "").split(";"):
        text = part.strip()
        if not text:
            continue
        items.append(Path(text).expanduser())
    return items


def serialize_manual_push_task(row: ManualPushTask, db=None) -> dict[str, Any]:
    push_target_id = getattr(row, "push_target_id", None)
    push_target_name = None
    if db is not None and push_target_id:
        try:
            from app.models.database import PushTarget

            push_target_name = (
                db.query(PushTarget.name)
                .filter(PushTarget.id == int(push_target_id), PushTarget.channel == "feishu")
                .scalar()
            )
        except Exception:
            push_target_name = None
    return {
        "id": row.id,
        "bvid": row.bvid,
        "source_type": _task_source_type(row),
        "source_path": getattr(row, "source_path", None),
        "push_target_id": push_target_id,
        "push_target_name": push_target_name,
        "title": row.title,
        "uploader_name": row.uploader_name,
        "source_video_id": row.source_video_id,
        "status": row.status,
        "stage": row.stage,
        "progress": row.progress,
        "message": row.message,
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "source_url": _task_source_url(row),
    }


def serialize_manual_push_task_detail(row: ManualPushTask, db=None) -> dict[str, Any]:
    payload = serialize_manual_push_task(row, db=db)
    payload["result_json"] = _loads_json(row.result_json)
    return payload


def create_manual_push_task(bvid: str, push_target_id: int | None = None) -> ManualPushTask:
    normalized_bvid = normalize_bvid(bvid)
    db = _make_session()
    try:
        resolved_push_target_id = push_target_id
        if resolved_push_target_id is None:
            default_target = get_default_push_target(db, channel="feishu")
            resolved_push_target_id = default_target.id if default_target and default_target.is_active else None
        else:
            target_row = get_push_target_by_id(db, int(resolved_push_target_id), channel="feishu")
            if not target_row:
                raise ValueError("push target not found")
            if not target_row.is_active:
                raise ValueError(f"push target '{target_row.name}' is disabled")

        row = ManualPushTask(
            bvid=normalized_bvid,
            source_type=_BILIBILI_SOURCE_TYPE,
            push_target_id=resolved_push_target_id,
            status="pending",
            stage="created",
            progress=0,
            message="任务已创建",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    finally:
        db.close()


def _create_local_video_task(db, source_path: str, push_target_id: int | None) -> ManualPushTask:
    normalized_path = _normalize_local_source_path(source_path)
    existing = (
        db.query(ManualPushTask)
        .filter(
            ManualPushTask.source_type == _LOCAL_SOURCE_TYPE,
            ManualPushTask.source_path == normalized_path,
        )
        .first()
    )
    if existing:
        return existing

    source_file = Path(normalized_path)
    row = ManualPushTask(
        bvid=_local_task_identifier(normalized_path),
        source_type=_LOCAL_SOURCE_TYPE,
        source_path=normalized_path,
        push_target_id=push_target_id,
        title=source_file.stem,
        uploader_name=_LOCAL_UPLOADER_NAME,
        status="pending",
        stage="created",
        progress=0,
        message="本地视频任务已创建",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _resolve_manual_push_target(db, task: ManualPushTask) -> dict[str, Any] | None:
    source_type = _task_source_type(task)
    if task.push_target_id:
        target_row = get_push_target_by_id(db, int(task.push_target_id), channel="feishu")
        if not target_row:
            raise RuntimeError(f"manual push target not found: {task.push_target_id}")
        if not target_row.is_active:
            raise RuntimeError(f"manual push target '{target_row.name}' is disabled")
        return serialize_push_target_row(target_row)

    if source_type == _LOCAL_SOURCE_TYPE:
        raise RuntimeError("local video scan push target not configured")

    target_row = get_default_push_target(db, channel="feishu")
    if target_row and not target_row.is_active:
        raise RuntimeError(f"default feishu push target '{target_row.name}' is disabled")
    if not target_row:
        return None
    return serialize_push_target_row(target_row)


def list_manual_push_tasks(
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
    status: str | None = None,
):
    db = _make_session()
    try:
        query = db.query(ManualPushTask)
        if q:
            pattern = f"%{q.strip()}%"
            query = query.filter(
                (ManualPushTask.bvid.ilike(pattern))
                | (ManualPushTask.title.ilike(pattern))
                | (ManualPushTask.uploader_name.ilike(pattern))
                | (ManualPushTask.message.ilike(pattern))
                | (ManualPushTask.source_path.ilike(pattern))
            )
        if status:
            query = query.filter(ManualPushTask.status == status)
        total = query.order_by(None).count()
        rows = (
            query.order_by(ManualPushTask.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return total, rows
    finally:
        db.close()


def get_manual_push_task(task_id: int) -> ManualPushTask | None:
    db = _make_session()
    try:
        return db.query(ManualPushTask).filter(ManualPushTask.id == task_id).first()
    finally:
        db.close()


def _update_task(
    db,
    task: ManualPushTask,
    *,
    status: str | None = None,
    stage: str | None = None,
    progress: int | None = None,
    message: str | None = None,
    error_message: str | None = None,
    result_json: dict[str, Any] | None = None,
    started: bool = False,
    finished: bool = False,
) -> None:
    if status is not None:
        task.status = status
    if stage is not None:
        task.stage = stage
    if progress is not None:
        task.progress = int(progress)
    if message is not None:
        task.message = message
    if error_message is not None:
        task.error_message = error_message
    if result_json is not None:
        task.result_json = json.dumps(result_json, ensure_ascii=False)
    if started and not task.started_at:
        task.started_at = datetime.utcnow()
    if finished:
        task.finished_at = datetime.utcnow()
    db.commit()


def _build_video_markdown(
    title: str,
    uploader_name: str,
    source_label: str,
    pub_time: int | None,
    details: str,
) -> str:
    video_pub_time_str = _format_pub_time(pub_time)
    markdown_content = f"# {title}\n\n"
    markdown_content += f"**来源**: {source_label}\n\n"
    markdown_content += f"**作者**: {uploader_name}\n\n"
    if video_pub_time_str:
        markdown_content += f"**发布时间**: {video_pub_time_str}\n\n"
    markdown_content += "---\n\n"
    markdown_content += details
    return markdown_content


def _build_local_video_markdown(title: str, source_path: str, details: str) -> str:
    markdown_content = f"# {title}\n\n"
    markdown_content += f"**来源文件**: {source_path}\n\n"
    markdown_content += f"**作者**: {_LOCAL_UPLOADER_NAME}\n\n"
    markdown_content += "---\n\n"
    markdown_content += details
    return markdown_content


def _summarize_text(
    *,
    task: ManualPushTask,
    title: str,
    uploader_name: str,
    raw_text: str,
) -> dict[str, Any]:
    process_result = process_text(
        raw_text=raw_text,
        video_title=title,
        duration=0,
        content_type="video",
        content_id=task.bvid,
        uploader_name=uploader_name,
    )
    return {
        "summary": process_result.get("summary", ""),
        "details": process_result.get("details", ""),
        "key_points": process_result.get("key_points", []),
        "tags": process_result.get("tags", []),
        "stocks": process_result.get("stocks", []),
        "insights": process_result.get("insights", ""),
        "duration_minutes": 0,
    }


def _build_push_payload(
    *,
    task: ManualPushTask,
    title: str,
    uploader_name: str,
    subtitles: str,
    summary_data: dict[str, Any],
    source_url: str | None,
    doc_url: str | None,
    pub_time: int | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "video",
        "content_id": task.bvid,
        "title": title,
        "uploader_name": uploader_name,
        "summary": summary_data.get("summary", ""),
        "details": summary_data.get("details", ""),
        "key_points": summary_data.get("key_points", []),
        "tags": summary_data.get("tags", []),
        "stocks": summary_data.get("stocks", []),
        "insights": summary_data.get("insights", ""),
        "text": subtitles,
        "url": source_url or "",
        "doc_url": doc_url,
        "pub_time": _format_pub_time(pub_time),
        "timestamp": pub_time,
        "duration_minutes": summary_data.get("duration_minutes", 0),
    }
    if extra_fields:
        payload.update(extra_fields)
    return payload


def _process_bilibili_video_task(db, task: ManualPushTask) -> dict[str, Any]:
    pm = get_path_manager()
    push_target = _resolve_manual_push_target(db, task)

    _update_task(
        db,
        task,
        status="running",
        stage="fetching",
        progress=5,
        message="开始拉取视频详情",
        started=True,
    )

    detail = fetch_video_detail(task.bvid)
    title = str(detail.get("title") or task.bvid)
    mid = str(detail.get("mid") or "")
    if not mid:
        raise RuntimeError(f"video detail missing uploader mid for {task.bvid}")
    pub_time = detail.get("pub_time")

    video = db.query(Video).filter(Video.bvid == task.bvid).first()
    if not video:
        video = Video(
            bvid=task.bvid,
            title=title,
            mid=mid,
            pub_time=pub_time,
            status="pending",
        )
        db.add(video)
        db.flush()
    else:
        video.title = title
        video.mid = mid
        video.pub_time = pub_time

    task.source_video_id = video.id
    task.title = title

    uploader_name, uploader_mid = get_uploader_info(db, mid)
    if not uploader_name:
        uploader_name = f"UP主_{mid}"
    task.uploader_name = uploader_name
    video.status = "processing"
    video.last_error = None

    paths = pm.get_video_paths(uploader_name, task.bvid, title, pub_time, uploader_mid)
    subtitles = ""
    transcript_text = (video.transcript_text or "").strip()
    _update_task(db, task, stage="fetching", progress=12, message="检查已有字幕")
    if paths["transcript"].exists():
        subtitles = paths["transcript"].read_text("utf-8")
    elif transcript_text:
        subtitles = transcript_text
        paths["transcript"].write_text(subtitles, "utf-8")
    else:
        old_text_file = get_data_dir() / "text" / f"{task.bvid}.txt"
        if old_text_file.exists():
            subtitles = old_text_file.read_text("utf-8")
            paths["transcript"].write_text(subtitles, "utf-8")

    if not subtitles:
        _update_task(db, task, stage="fetching", progress=18, message="尝试获取 B 站字幕")
        subtitles = get_subtitles(task.bvid)
        if subtitles and not paths["transcript"].exists():
            paths["transcript"].write_text(subtitles, "utf-8")

    if subtitles:
        video.transcript_text = subtitles
        video.has_subtitle = True
        if not paths["transcript"].exists():
            paths["transcript"].write_text(subtitles, "utf-8")
    else:
        video.has_subtitle = False

    media_path = None
    media_type = None
    if not subtitles:
        _update_task(db, task, stage="downloading", progress=25, message="下载音频或视频中")
        if video.has_video and paths["video"].exists():
            media_path = str(paths["video"])
            media_type = "video"
        elif video.has_audio and paths["audio"].exists():
            media_path = str(paths["audio"])
            media_type = "audio"
        else:
            try:
                audio_file = download_audio_new(
                    bvid=task.bvid,
                    mid=mid,
                    title=title,
                    pub_time=pub_time,
                    uploader_name=uploader_name,
                )
            except Exception as exc:
                raise RuntimeError(f"download failed: {exc}") from exc
            if not audio_file or not Path(audio_file).exists():
                raise RuntimeError("audio download returned empty path")
            media_path = str(audio_file)
            media_type = "audio"
            video.has_audio = True
            video.audio_path = str(Path(audio_file).resolve())

        if media_path and not subtitles:
            _update_task(db, task, stage="asr", progress=55, message="正在识别音频")
            try:
                subtitles = transcribe_audio(media_path)
            except Exception as exc:
                raise RuntimeError(f"asr failed: {exc}") from exc
            if media_type == "audio":
                video.has_audio = True
            elif media_type == "video":
                video.has_video = True

    if subtitles:
        _update_task(db, task, stage="summarizing", progress=72, message="生成总结")
        summary_data = _summarize_text(task=task, title=title, uploader_name=uploader_name, raw_text=subtitles)
        video.summary_json = json.dumps(summary_data, ensure_ascii=False)
    else:
        _update_task(db, task, stage="summarizing", progress=72, message="未获取到字幕，使用摘要兜底")
        summary_data = {
            "summary": f"无法获取字幕或音频：{title}",
            "details": "",
            "key_points": [],
            "tags": [],
            "stocks": [],
            "insights": "",
            "duration_minutes": 0,
        }
        video.summary_json = json.dumps(summary_data, ensure_ascii=False)

    push_payload = _build_push_payload(
        task=task,
        title=title,
        uploader_name=uploader_name,
        subtitles=subtitles,
        summary_data=summary_data,
        source_url=f"https://www.bilibili.com/video/{task.bvid}",
        doc_url=None,
        pub_time=pub_time,
        extra_fields={"mid": mid},
    )
    push_filter = classify_push_relevance(
        push_payload,
        content_type="video",
        content_id=task.bvid,
        content_title=title,
        uploader_name=uploader_name,
    )
    summary_data["push_filter"] = push_filter
    video.summary_json = json.dumps(summary_data, ensure_ascii=False)

    md_content = _build_video_markdown(
        title,
        uploader_name,
        f"https://www.bilibili.com/video/{task.bvid}",
        pub_time,
        summary_data.get("details", ""),
    )
    if not paths["summary"].exists():
        paths["summary"].write_text(md_content, "utf-8")

    doc_url = None
    try:
        doc_markdown = _prepend_usage_model_note(md_content, _resolve_summary_model_name("video_summary"))
        doc_result = push_video_summary_to_doc(
            title=title,
            markdown_content=doc_markdown,
            bvid=task.bvid,
            pub_time=pub_time,
            uploader_name=uploader_name,
        )
        if doc_result:
            doc_url = doc_result.get("url")
            video.doc_url = doc_url
    except Exception as exc:
        logger.warning("manual push feishu doc failed: %s", exc)

    _update_task(db, task, stage="pushing", progress=88, message="推送飞书中")
    push_payload["doc_url"] = doc_url
    push_payload["push_filter"] = push_filter
    push_payload["push_target"] = push_target
    push_result = push_content(push_payload, ["feishu"])

    result_json = {
        "bvid": task.bvid,
        "video_id": video.id,
        "title": title,
        "uploader_name": uploader_name,
        "summary": summary_data,
        "doc_url": doc_url,
        "push_result": push_result,
    }

    if push_result.get("silented"):
        video.status = "silented"
        task.message = "静默时段，已暂缓推送"
    elif push_result.get("skipped") or not push_filter.get("should_push", True):
        reason = str(push_result.get("reason") or push_filter.get("reason") or "内容与投资/财经无关")
        video.status = "filtered"
        video.last_error = reason[:200]
        task.message = reason[:200]
    elif not push_result.get("success", False):
        raise RuntimeError(str(push_result.get("reason") or "push failed"))
    else:
        video.status = "done"
        video.last_error = None
        task.message = "任务完成"

    video.updated_at = datetime.utcnow()
    return {
        "task_message": task.message or "任务完成",
        "result_json": result_json,
    }


def _process_local_video_task(db, task: ManualPushTask) -> dict[str, Any]:
    push_target = _resolve_manual_push_target(db, task)
    source_path = _normalize_local_source_path(task.source_path or "")
    source_file = Path(source_path)
    if not source_file.exists():
        raise RuntimeError(f"local video not found: {source_path}")
    if source_file.suffix.lower() != ".flv":
        raise RuntimeError(f"unsupported local video file: {source_path}")

    title = source_file.stem
    task.title = title
    task.uploader_name = _LOCAL_UPLOADER_NAME
    _update_task(
        db,
        task,
        status="running",
        stage="downloading",
        progress=12,
        message="检查本地视频文件",
        started=True,
    )

    paths = _local_artifact_paths(source_path)
    subtitles = ""
    if paths["transcript"].exists():
        subtitles = paths["transcript"].read_text("utf-8")

    if not subtitles:
        _update_task(db, task, stage="asr", progress=45, message="正在识别本地视频")
        try:
            subtitles = transcribe_audio(source_path)
        except Exception as exc:
            raise RuntimeError(f"asr failed: {exc}") from exc
        paths["transcript"].write_text(subtitles, "utf-8")

    _update_task(db, task, stage="summarizing", progress=72, message="生成总结")
    summary_data = _summarize_text(task=task, title=title, uploader_name=_LOCAL_UPLOADER_NAME, raw_text=subtitles)

    source_label = source_path
    md_content = _build_local_video_markdown(title, source_path, summary_data.get("details", ""))
    if not paths["summary"].exists():
        paths["summary"].write_text(md_content, "utf-8")

    pseudo_bvid = task.bvid or _local_task_identifier(source_path)
    doc_url = None
    try:
        doc_markdown = _prepend_usage_model_note(md_content, _resolve_summary_model_name("video_summary"))
        doc_result = push_video_summary_to_doc(
            title=title,
            markdown_content=doc_markdown,
            bvid=pseudo_bvid,
            pub_time=None,
            uploader_name=_LOCAL_UPLOADER_NAME,
        )
        if doc_result:
            doc_url = doc_result.get("url")
    except Exception as exc:
        logger.warning("local video feishu doc failed: %s", exc)

    push_payload = _build_push_payload(
        task=task,
        title=title,
        uploader_name=_LOCAL_UPLOADER_NAME,
        subtitles=subtitles,
        summary_data=summary_data,
        source_url=None,
        doc_url=doc_url,
        pub_time=None,
        extra_fields={"source_path": source_path},
    )
    push_filter = classify_push_relevance(
        push_payload,
        content_type="video",
        content_id=task.bvid,
        content_title=title,
        uploader_name=_LOCAL_UPLOADER_NAME,
    )
    summary_data["push_filter"] = push_filter

    _update_task(db, task, stage="pushing", progress=88, message="推送飞书中")
    push_payload["push_filter"] = push_filter
    push_payload["push_target"] = push_target
    push_result = push_content(push_payload, ["feishu"])

    if push_result.get("silented"):
        task.message = "静默时段，已暂缓推送"
    elif push_result.get("skipped") or not push_filter.get("should_push", True):
        task.message = str(push_result.get("reason") or push_filter.get("reason") or "内容与投资/财经无关")[:200]
    elif not push_result.get("success", False):
        raise RuntimeError(str(push_result.get("reason") or "push failed"))
    else:
        task.message = "任务完成"

    return {
        "task_message": task.message or "任务完成",
        "result_json": {
            "bvid": pseudo_bvid,
            "source_type": _LOCAL_SOURCE_TYPE,
            "source_path": source_path,
            "title": title,
            "uploader_name": _LOCAL_UPLOADER_NAME,
            "summary": summary_data,
            "doc_url": doc_url,
            "push_result": push_result,
        },
    }


def _process_manual_task(task_id: int) -> None:
    db = _make_session()
    task: ManualPushTask | None = None
    try:
        task = db.query(ManualPushTask).filter(ManualPushTask.id == task_id).first()
        if not task:
            return

        if _task_source_type(task) == _LOCAL_SOURCE_TYPE:
            outcome = _process_local_video_task(db, task)
        else:
            outcome = _process_bilibili_video_task(db, task)

        _update_task(
            db,
            task,
            status="success",
            stage="done",
            progress=100,
            message=outcome.get("task_message") or "任务完成",
            error_message=None,
            result_json=outcome.get("result_json"),
            finished=True,
        )
        db.commit()
    except Exception as exc:
        logger.error("manual push task failed | id=%s | error=%s", task_id, exc, exc_info=True)
        try:
            task = db.query(ManualPushTask).filter(ManualPushTask.id == task_id).first()
            if task:
                task.status = "failed"
                task.stage = "failed"
                task.progress = min(int(task.progress or 0), 99)
                task.error_message = str(exc)[:500]
                task.message = str(exc)[:200]
                task.finished_at = datetime.utcnow()
                db.commit()
        except Exception as db_exc:
            logger.error("manual push task update failed: %s", db_exc)
        try:
            video_bvid = task.bvid if task and _task_source_type(task) == _BILIBILI_SOURCE_TYPE else None
            video = db.query(Video).filter(Video.bvid == video_bvid).first() if video_bvid else None
            if video:
                video.status = "failed"
                video.last_error = str(exc)[:200]
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def spawn_manual_push_task(task_id: int):
    return _MANUAL_PUSH_EXECUTOR.submit(_process_manual_task, task_id)


def scan_local_video_dirs() -> dict[str, Any]:
    scan_dirs = _parse_scan_dirs(getattr(Config, "LOCAL_VIDEO_SCAN_DIRS", "") or "")
    if not scan_dirs:
        logger.info("[local-video] no scan dirs configured")
        return {"created": 0, "skipped": 0, "errors": 0}

    raw_push_target_id = int(getattr(Config, "LOCAL_VIDEO_SCAN_PUSH_TARGET_ID", 0) or 0)
    push_target_id = raw_push_target_id if raw_push_target_id > 0 else None

    created = 0
    skipped = 0
    errors = 0
    db = _make_session()
    try:
        for scan_dir in scan_dirs:
            try:
                normalized_dir = scan_dir.resolve()
            except Exception:
                normalized_dir = scan_dir
            if not normalized_dir.exists():
                logger.warning("[local-video] scan dir not found: %s", normalized_dir)
                errors += 1
                continue
            if not normalized_dir.is_dir():
                logger.warning("[local-video] scan path is not a directory: %s", normalized_dir)
                errors += 1
                continue

            try:
                for file_path in normalized_dir.rglob("*"):
                    if not file_path.is_file():
                        continue
                    if file_path.suffix.lower() != ".flv":
                        continue
                    normalized_path = _normalize_local_source_path(str(file_path))
                    existing = (
                        db.query(ManualPushTask.id)
                        .filter(
                            ManualPushTask.source_type == _LOCAL_SOURCE_TYPE,
                            ManualPushTask.source_path == normalized_path,
                        )
                        .first()
                    )
                    if existing:
                        skipped += 1
                        continue
                    task = _create_local_video_task(db, normalized_path, push_target_id)
                    spawn_manual_push_task(task.id)
                    created += 1
            except Exception as exc:
                logger.warning("[local-video] scan dir failed: %s | error=%s", normalized_dir, exc)
                errors += 1
        return {"created": created, "skipped": skipped, "errors": errors}
    finally:
        db.close()
