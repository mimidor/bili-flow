import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from app.modules.push_channels.base import BaseChannel
from app.modules.push_channels.registry import ChannelRegistry
from app.utils.logger import get_logger
from config import Config

logger = get_logger("push.feishu")

_feishu_token_cache = None
_feishu_token_expire_at = 0
_FEISHU_TEXT_LIMIT = 1800


def _truncate_feishu_text(text: str, limit: int = _FEISHU_TEXT_LIMIT) -> str:
    content = (text or "").strip()
    if len(content) <= limit:
        return content

    suffix = "\n\n...（内容已截断）"
    cutoff = max(0, limit - len(suffix))
    return f"{content[:cutoff].rstrip()}{suffix}"


def get_feishu_tenant_access_token() -> Optional[str]:
    """Get cached Feishu tenant access token."""
    global _feishu_token_cache, _feishu_token_expire_at

    now = datetime.now().timestamp()
    if _feishu_token_cache and now < _feishu_token_expire_at - 300:
        return _feishu_token_cache

    if not Config.FEISHU_APP_ID or not Config.FEISHU_APP_SECRET:
        logger.warning("Feishu APP_ID or APP_SECRET not configured")
        return None

    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    payload = {"app_id": Config.FEISHU_APP_ID, "app_secret": Config.FEISHU_APP_SECRET}

    try:
        resp = requests.post(url, json=payload, timeout=15)
        data = resp.json()
        if data.get("code") == 0:
            _feishu_token_cache = data["tenant_access_token"]
            _feishu_token_expire_at = now + data["expire"]
            return _feishu_token_cache

        logger.error("Feishu token fetch failed: %s", data.get("msg"))
        return None
    except Exception as e:
        logger.error("Feishu token request failed: %s", e)
        return None


def upload_image_to_feishu(image_path: str) -> Optional[str]:
    """Upload an image to Feishu and return image_key."""
    token = get_feishu_tenant_access_token()
    if not token:
        return None

    url = "https://open.feishu.cn/open-apis/im/v1/images"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        path = Path(image_path)
        if not path.exists():
            logger.warning("Image file not found: %s", image_path)
            return None

        files = {"image": (path.name, path.read_bytes(), "image/png")}
        data = {"image_type": "message"}

        resp = requests.post(url, headers=headers, data=data, files=files, timeout=30)
        result = resp.json()
        if result.get("code") == 0:
            return result.get("data", {}).get("image_key")

        logger.error("Image upload failed: code=%s", result.get("code"))
        return None
    except Exception as e:
        logger.error("Image upload error: %s", e)
        return None


def _format_pub_time(value: Any) -> str:
    if not value:
        return ""
    if hasattr(value, "strftime"):
        try:
            return value.strftime("%Y年%m月%d日 %H:%M:%S")
        except Exception:
            return str(value)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(int(value)).strftime("%Y年%m月%d日 %H:%M:%S")
        except Exception:
            return str(value)
    return str(value).strip()


def _resolve_target(content_data: Dict[str, Any]) -> Dict[str, Any] | None:
    target = content_data.get("push_target")
    if isinstance(target, dict) and target.get("receive_id") and target.get("receive_id_type"):
        return target

    if Config.FEISHU_RECEIVE_ID and Config.FEISHU_RECEIVE_ID_TYPE:
        return {
            "id": None,
            "name": "Legacy Default",
            "receive_id": Config.FEISHU_RECEIVE_ID,
            "receive_id_type": Config.FEISHU_RECEIVE_ID_TYPE,
            "is_default": True,
            "is_active": True,
        }
    return None


@ChannelRegistry.register
class FeishuChannel(BaseChannel):
    """Feishu push channel."""

    channel_name = "feishu"

    def send(self, content_data: Dict[str, Any]) -> bool:
        content_type = content_data.get("type", "unknown")
        if content_type == "video":
            return self._send_video(content_data)
        if content_type == "dynamic":
            return self._send_dynamic(content_data)
        if content_type == "podcast":
            return self._send_podcast(content_data)
        if content_type == "wewe_rss":
            return self._send_wewe_rss(content_data)

        logger.warning("Unknown content type: %s", content_type)
        return False

    def _send_video(self, content_data: Dict[str, Any]) -> bool:
        title = content_data.get("title", "无标题")
        uploader_name = (content_data.get("uploader_name") or "").strip()
        summary = content_data.get("summary", "")
        url = content_data.get("url", "")
        tags = content_data.get("tags", [])
        stocks = content_data.get("stocks", [])
        doc_url = content_data.get("doc_url", "")
        pub_time = content_data.get("pub_time", "") or content_data.get("timestamp", "")
        pub_time_str = _format_pub_time(pub_time)

        lines = ["【新视频】", ""]
        if uploader_name:
            lines.extend([f"作者：{uploader_name}", ""])
        lines.append(title)
        if pub_time_str:
            lines.extend(["", f"发布时间：{pub_time_str}"])
        if summary:
            lines.extend(["", summary])
        if stocks:
            lines.extend(["", f"涉及股票：{'、'.join(stocks)}"])
        if tags:
            lines.extend(["", f"标签：{' '.join([f'#{t}' for t in tags])}"])
        if url:
            lines.extend(["", f"原视频：{url}"])
        if doc_url:
            lines.extend(["", f"详细总结：{doc_url}"])

        return self._send_text("\n".join(lines).strip(), content_data)

    def _send_dynamic(self, content_data: Dict[str, Any]) -> bool:
        uploader_name = (content_data.get("uploader_name") or "").strip()
        text = content_data.get("text", "")
        url = content_data.get("url", "")
        pub_time = content_data.get("pub_time", "")
        image_urls = content_data.get("image_urls", []) or content_data.get("images", []) or []

        pub_time_str = _format_pub_time(pub_time)
        full_text = (text or "").strip()
        display_text = full_text

        lines = ["【新动态】"]
        if uploader_name:
            lines.extend(["", f"作者：{uploader_name}"])
        if pub_time_str:
            lines.extend(["", f"发布时间：{pub_time_str}"])
        if display_text:
            lines.extend(["", display_text])
        if url:
            lines.extend([f"原动态：{url}"])
        if image_urls:
            lines.extend(["", "图片："])
            for idx, image_url in enumerate(image_urls[:4], start=1):
                lines.append(f"{idx}. {image_url}")
            if len(image_urls) > 4:
                lines.append(f"... 其余 {len(image_urls) - 4} 张图片")

        return self._send_text("\n".join(lines).strip(), content_data)

    def _send_podcast(self, content_data: Dict[str, Any]) -> bool:
        title = content_data.get("title", "无标题")
        uploader_name = (content_data.get("uploader_name") or "").strip()
        summary = content_data.get("summary", "")
        url = content_data.get("url", "")
        doc_url = content_data.get("doc_url", "")
        pub_time = content_data.get("pub_time", "") or content_data.get("timestamp", "")
        pub_time_str = _format_pub_time(pub_time)

        lines = ["【小宇宙新集】", ""]
        if uploader_name:
            lines.extend([f"作者：{uploader_name}", ""])
        lines.append(title)
        if pub_time_str:
            lines.extend(["", f"发布时间：{pub_time_str}"])
        if summary:
            lines.extend(["", summary])
        if url:
            lines.extend(["", f"原链接：{url}"])
        if doc_url:
            lines.extend(["", f"详细总结：{doc_url}"])

        return self._send_text("\n".join(lines).strip(), content_data)

    def _send_wewe_rss(self, content_data: Dict[str, Any]) -> bool:
        title = content_data.get("title", "无标题")
        feed_name = (content_data.get("uploader_name") or content_data.get("feed_name") or "").strip()
        text = (content_data.get("text") or content_data.get("content_text") or "").strip()
        url = content_data.get("url", "") or content_data.get("source_url", "") or ""
        pub_time = content_data.get("pub_time", "") or content_data.get("timestamp", "")
        pub_time_str = _format_pub_time(pub_time)

        lines = ["【公众号文章】", ""]
        if feed_name:
            lines.extend([f"来源：{feed_name}", ""])
        lines.append(title)
        if pub_time_str:
            lines.extend(["", f"发布时间：{pub_time_str}"])
        if text:
            lines.extend(["", text])
        if url:
            lines.extend(["", f"原链接：{url}"])

        return self._send_text("\n".join(lines).strip(), content_data)

    def _send_text(self, text: str, content_data: Dict[str, Any] | None = None) -> bool:
        token = get_feishu_tenant_access_token()
        if not token:
            return False

        target = _resolve_target(content_data or {})
        if not target:
            logger.warning("Feishu target not configured")
            return False

        prepared_text = _truncate_feishu_text(text)
        if prepared_text != (text or "").strip():
            logger.info(
                "Feishu text truncated from %d to %d chars before sending",
                len((text or "").strip()),
                len(prepared_text),
            )

        url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={target['receive_id_type']}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        content_json = json.dumps({"text": prepared_text}, ensure_ascii=False)
        payload = {
            "receive_id": target["receive_id"],
            "msg_type": "text",
            "content": content_json,
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            try:
                data = resp.json()
            except ValueError:
                logger.warning(
                    "Feishu text push returned non-JSON response: status=%s body=%s",
                    resp.status_code,
                    resp.text[:500],
                )
                return False

            if data.get("code") == 0:
                return True

            logger.warning(
                "Feishu text push rejected: code=%s msg=%s body=%s",
                data.get("code"),
                data.get("msg") or data.get("error") or data.get("message"),
                str(data)[:500],
            )
            return False
        except Exception as e:
            logger.error("Feishu text push error: %s", e)
            return False

    def send_text(self, text: str) -> bool:
        return self._send_text(text)
