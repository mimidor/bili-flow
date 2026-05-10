"""
Push channel registry and unified push entry.
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Any

from app.modules.push_channels import feishu  # noqa: F401
from app.modules.push_channels.registry import (
    get_channel,
    list_channels,
    send_to_channel,
    send_to_channels,
)
from app.modules.processor import classify_push_relevance
from app.services.push_targets import resolve_push_target
from app.services.telemetry import record_push_history


def is_silent_mode() -> bool:
    """判断当前是否处于静音时段。"""
    from config import Config

    start_str = Config.SILENT_MODE_START
    end_str = Config.SILENT_MODE_END
    if not start_str or not end_str:
        return False
    try:
        start = time(*map(int, str(start_str).strip().split(":")))
        end = time(*map(int, str(end_str).strip().split(":")))
    except (ValueError, TypeError):
        return False
    now = datetime.now().time()
    if start <= end:
        # 同日区间，如 08:00 ~ 18:00
        return start <= now < end
    else:
        # 跨日区间，如 23:00 ~ 07:00
        return now >= start or now < end


def _infer_content_identity(content_data: dict) -> tuple[str, str, str]:
    content_type = content_data.get("type", "unknown")
    content_id = content_data.get("content_id", "") or ""
    title = content_data.get("title", "") or content_data.get("text", "") or ""
    uploader_name = (content_data.get("uploader_name") or "").strip()
    url = content_data.get("url", "") or ""

    if not content_id:
        if content_type == "video" and "/video/" in url:
            content_id = url.rsplit("/", 1)[-1]
        elif content_type == "dynamic" and "/opus/" in url:
            content_id = url.rsplit("/", 1)[-1]
        elif content_type == "wewe_rss" and url:
            content_id = url

    if not content_id:
        content_id = url or title[:32]

    return content_type, content_id, uploader_name


def _build_request_snapshot(content_data: dict) -> dict[str, Any]:
    keys = ["type", "title", "text", "uploader_name", "url", "doc_url", "pub_time"]
    return {key: content_data.get(key) for key in keys if content_data.get(key) is not None}


def _resolve_content_target(content_data: dict[str, Any], channel_name: str) -> tuple[dict[str, Any] | None, str | None]:
    if channel_name == "feishu":
        explicit_target = content_data.get("push_target")
        if isinstance(explicit_target, dict) and explicit_target.get("receive_id") and explicit_target.get("receive_id_type"):
            return explicit_target, None
    return resolve_push_target(content_data, channel=channel_name)


def push_content(content_data: dict, channels: list) -> dict[str, Any]:
    """Unified push entrypoint."""
    from app.utils.logger import get_logger

    logger = get_logger("push")
    content_type, content_id, uploader_name = _infer_content_identity(content_data)
    request_snapshot = _build_request_snapshot(content_data)

    # 静音时段判断：仅暂缓推送，不影响内容处理
    if is_silent_mode():
        reason = "当前处于静音时段，推送已暂缓"
        logger.info(
            "[push] silenced | type=%s | id=%s | reason=%s",
            content_type,
            content_id,
            reason,
        )
        for channel_name in channels:
            target_meta = None
            if channel_name == "feishu":
                target_meta, _ = _resolve_content_target(content_data, channel_name)
            record_push_history(
                content_type=content_type,
                content_id=content_id,
                channel=channel_name,
                status="silented",
                content_title=content_data.get("title") or content_data.get("text"),
                uploader_name=uploader_name,
                target_id=target_meta.get("id") if target_meta else None,
                target_name=target_meta.get("name") if target_meta else None,
                target_receive_id=target_meta.get("receive_id") if target_meta else None,
                error_message=reason,
                response_summary=reason,
                request_payload=request_snapshot,
            )
        return {
            "success": True,
            "skipped": False,
            "silented": True,
            "reason": reason,
            "filter_result": None,
            "channel_results": [],
        }

    filter_result = content_data.get("push_filter")
    if content_type == "wewe_rss":
        filter_result = {"should_push": True, "reason": "wewe rss direct push"}
    elif not isinstance(filter_result, dict):
        filter_result = classify_push_relevance(
            content_data,
            content_type=content_type,
            content_id=content_id,
            content_title=content_data.get("title") or content_data.get("text"),
            uploader_name=uploader_name,
        )

    if not filter_result.get("should_push", True):
        reason = str(filter_result.get("reason") or "内容与投资/宏观/社会完全无关，已跳过推送")
        for channel_name in channels:
            target_meta = None
            if channel_name == "feishu":
                target_meta, _ = _resolve_content_target(content_data, channel_name)
            record_push_history(
                content_type=content_type,
                content_id=content_id,
                channel=channel_name,
                status="skipped",
                content_title=content_data.get("title") or content_data.get("text"),
                uploader_name=uploader_name,
                target_id=target_meta.get("id") if target_meta else None,
                target_name=target_meta.get("name") if target_meta else None,
                target_receive_id=target_meta.get("receive_id") if target_meta else None,
                error_message=reason,
                response_summary=reason,
                request_payload=request_snapshot,
                response_payload={"filter_result": filter_result},
            )
        logger.info(
            "[push] skipped by relevance filter | type=%s | id=%s | reason=%s",
            content_type,
            content_id,
            reason,
        )
        return {
            "success": True,
            "skipped": True,
            "reason": reason,
            "filter_result": filter_result,
            "channel_results": [],
        }

    success = True
    channel_results: list[dict[str, Any]] = []

    for channel_name in channels:
        target_meta = None
        target_error = None
        if channel_name == "feishu":
            target_meta, target_error = _resolve_content_target(content_data, channel_name)

        if target_error:
            logger.warning("[%s] target resolution failed: %s", channel_name, target_error)
            record_push_history(
                content_type=content_type,
                content_id=content_id,
                channel=channel_name,
                status="failed",
                content_title=content_data.get("title") or content_data.get("text"),
                uploader_name=uploader_name,
                target_id=target_meta.get("id") if target_meta else None,
                target_name=target_meta.get("name") if target_meta else None,
                target_receive_id=target_meta.get("receive_id") if target_meta else None,
                error_message=target_error,
                response_summary="push target resolution failed",
                request_payload=request_snapshot,
            )
            success = False
            channel_results.append({
                "channel": channel_name,
                "success": False,
                "error": target_error,
            })
            continue

        channel = get_channel(channel_name)
        if not channel:
            logger.warning("Unknown push channel: %s", channel_name)
            record_push_history(
                content_type=content_type,
                content_id=content_id,
                channel=channel_name,
                status="failed",
                content_title=content_data.get("title") or content_data.get("text"),
                uploader_name=uploader_name,
                target_id=target_meta.get("id") if target_meta else None,
                target_name=target_meta.get("name") if target_meta else None,
                target_receive_id=target_meta.get("receive_id") if target_meta else None,
                error_message="unknown channel",
                response_summary="channel not found",
                request_payload=request_snapshot,
            )
            success = False
            channel_results.append({
                "channel": channel_name,
                "success": False,
                "error": "unknown channel",
            })
            continue

        try:
            send_payload = {**content_data, "push_target": target_meta} if target_meta else dict(content_data)
            channel_success = channel.send(send_payload)
            if channel_success:
                logger.debug("[%s] push success", channel_name)
                record_push_history(
                    content_type=content_type,
                    content_id=content_id,
                    channel=channel_name,
                    status="success",
                    content_title=content_data.get("title") or content_data.get("text"),
                    uploader_name=uploader_name,
                    target_id=target_meta.get("id") if target_meta else None,
                    target_name=target_meta.get("name") if target_meta else None,
                    target_receive_id=target_meta.get("receive_id") if target_meta else None,
                    response_summary="channel.send returned True",
                    request_payload=request_snapshot,
                )
            else:
                logger.warning("[%s] push failed", channel_name)
                record_push_history(
                    content_type=content_type,
                    content_id=content_id,
                    channel=channel_name,
                    status="failed",
                    content_title=content_data.get("title") or content_data.get("text"),
                    uploader_name=uploader_name,
                    target_id=target_meta.get("id") if target_meta else None,
                    target_name=target_meta.get("name") if target_meta else None,
                    target_receive_id=target_meta.get("receive_id") if target_meta else None,
                    error_message="channel returned False",
                    response_summary="channel.send returned False",
                    request_payload=request_snapshot,
                )
                success = False
            channel_results.append({
                "channel": channel_name,
                "success": bool(channel_success),
            })
        except Exception as e:
            logger.error("[%s] push error: %s", channel_name, e)
            record_push_history(
                content_type=content_type,
                content_id=content_id,
                channel=channel_name,
                status="failed",
                content_title=content_data.get("title") or content_data.get("text"),
                uploader_name=uploader_name,
                target_id=target_meta.get("id") if target_meta else None,
                target_name=target_meta.get("name") if target_meta else None,
                target_receive_id=target_meta.get("receive_id") if target_meta else None,
                error_message=str(e),
                response_summary="exception raised",
                request_payload=request_snapshot,
            )
            success = False
            channel_results.append({
                "channel": channel_name,
                "success": False,
                "error": str(e),
            })

    if content_type == "video":
        logger.info(
            "[push] video: %s | title: %s | channels: %s",
            content_data.get("url", ""),
            content_data.get("title", "")[:50],
            channels,
        )
    elif content_type == "dynamic":
        logger.info(
            "[push] dynamic: %s | text: %s | channels: %s",
            content_data.get("url", ""),
            content_data.get("text", "")[:50],
            channels,
        )
    elif content_type == "podcast":
        logger.info(
            "[push] podcast: %s | title: %s | channels: %s",
            content_data.get("url", ""),
            content_data.get("title", "")[:50],
            channels,
        )

    return {
        "success": success,
        "skipped": False,
        "reason": None,
        "filter_result": filter_result,
        "channel_results": channel_results,
    }


def push_video_to_feishu(content_data: dict) -> bool:
    """Backward-compatible helper."""
    channel = get_channel("feishu")
    if channel:
        return channel.send({**content_data, "type": "video"})
    return False


def push_dynamic_to_feishu(content_data: dict) -> bool:
    """Backward-compatible helper."""
    channel = get_channel("feishu")
    if channel:
        return channel.send({**content_data, "type": "dynamic"})
    return False
