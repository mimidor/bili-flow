from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Any

import dashscope
import oss2
import requests

from app.utils.logger import get_logger
from config import Config

logger = get_logger("bailian_asr")

FILETRANS_MODEL = "qwen3-asr-flash-filetrans"
SYNC_MODEL_PREFIX = "qwen3-asr-flash"


def _normalize_model_name(model_name: str) -> str:
    model_name = (model_name or "").strip()
    if not model_name:
        return FILETRANS_MODEL
    return model_name


def _is_filetrans_model(model_name: str) -> bool:
    return "filetrans" in (model_name or "")


def _is_sync_model(model_name: str) -> bool:
    model_name = (model_name or "").strip()
    return model_name.startswith(SYNC_MODEL_PREFIX) and "filetrans" not in model_name


def _require(value: str, name: str) -> str:
    if not value:
        raise RuntimeError(f"阿里百炼 ASR 缺少配置: {name}")
    return value


def _sanitize_object_part(value: str, fallback: str = "audio") -> str:
    value = (value or "").strip()
    value = re.sub(r"[^\w.\-]+", "_", value, flags=re.UNICODE)
    value = value.strip("._-")
    return value or fallback


def _build_object_key(audio_path: str) -> str:
    path = Path(audio_path)
    prefix = (Config.ALIYUN_OSS_PREFIX or "bili-auto/asr").strip("/")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = _sanitize_object_part(path.stem)
    suffix = path.suffix or ".m4a"
    unique = uuid.uuid4().hex[:12]
    return f"{prefix}/{timestamp}_{stem}_{unique}{suffix}"


def _build_bucket() -> oss2.Bucket:
    endpoint = _require(Config.ALIYUN_OSS_ENDPOINT, "ALIYUN_OSS_ENDPOINT")
    bucket_name = _require(Config.ALIYUN_OSS_BUCKET, "ALIYUN_OSS_BUCKET")
    access_key_id = _require(Config.ALIYUN_OSS_ACCESS_KEY_ID, "ALIYUN_OSS_ACCESS_KEY_ID")
    access_key_secret = _require(Config.ALIYUN_OSS_ACCESS_KEY_SECRET, "ALIYUN_OSS_ACCESS_KEY_SECRET")

    if not endpoint.startswith(("http://", "https://")):
        endpoint = f"https://{endpoint}"

    auth = oss2.Auth(access_key_id, access_key_secret)
    return oss2.Bucket(auth, endpoint, bucket_name)


def upload_audio_to_oss(audio_path: str) -> tuple[str, str]:
    """
    Upload an audio file to OSS and return a signed GET URL.
    """
    bucket = _build_bucket()
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"音频文件不存在: {path}")

    object_key = _build_object_key(audio_path)
    logger.info("上传音频到 OSS: %s -> oss://%s/%s", path, Config.ALIYUN_OSS_BUCKET, object_key)
    bucket.put_object_from_file(object_key, str(path))

    expires = max(60, int(Config.ALIYUN_OSS_URL_EXPIRE_SECONDS or 3600))
    signed_url = bucket.sign_url("GET", object_key, expires)
    return object_key, signed_url


def _request_json(method: str, url: str, headers: dict[str, str], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "headers": headers,
        "timeout": 60,
    }
    if payload is not None:
        kwargs["json"] = payload

    response = requests.request(method, url, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"百炼 ASR 请求失败 ({response.status_code}): {response.text}")
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(f"百炼 ASR 响应不是 JSON: {response.text}") from exc


def _find_first_string(data: Any, keys: tuple[str, ...]) -> str | None:
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for value in data.values():
            found = _find_first_string(value, keys)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _find_first_string(item, keys)
            if found:
                return found
    return None


def _extract_plain_text(data: Any) -> str:
    if isinstance(data, str):
        text = data.strip()
        return text

    if isinstance(data, dict):
        for key in ("text", "transcript", "content", "sentence"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        for key in ("segments", "sentences", "utterances", "items", "results"):
            value = data.get(key)
            if isinstance(value, list):
                lines: list[str] = []
                for item in value:
                    if isinstance(item, dict):
                        for candidate in ("text", "transcript", "sentence", "content"):
                            item_value = item.get(candidate)
                            if isinstance(item_value, str) and item_value.strip():
                                lines.append(item_value.strip())
                                break
                    elif isinstance(item, str) and item.strip():
                        lines.append(item.strip())
                if lines:
                    return "\n".join(lines)

        nested = data.get("result")
        if nested is not None:
            text = _extract_plain_text(nested)
            if text:
                return text

        collected: list[str] = []
        for value in data.values():
            text = _extract_plain_text(value)
            if text:
                collected.append(text)
        if collected:
            return "\n".join(collected)

    if isinstance(data, list):
        collected = []
        for item in data:
            text = _extract_plain_text(item)
            if text:
                collected.append(text)
        if collected:
            return "\n".join(collected)

    return ""


def _extract_sync_response_text(response: Any) -> str:
    output = getattr(response, "output", None)
    choices = getattr(output, "choices", None) if output is not None else None
    if choices:
        first_choice = choices[0]
        message = getattr(first_choice, "message", None)
        content = getattr(message, "content", None) if message is not None else None
        if isinstance(content, list):
            lines: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        lines.append(text.strip())
                else:
                    text = getattr(item, "text", None)
                    if isinstance(text, str) and text.strip():
                        lines.append(text.strip())
            if lines:
                return "\n".join(lines)
        if isinstance(content, str) and content.strip():
            return content.strip()

    if isinstance(response, dict):
        text = _extract_plain_text(response)
        if text:
            return text

    text = _extract_plain_text(getattr(response, "__dict__", {}))
    if text:
        return text

    return str(response).strip()


def _poll_filetrans_result(task_id: str, headers: dict[str, str]) -> dict[str, Any]:
    query_url = f"{Config.DASHSCOPE_ASR_BASE_URL.rstrip('/')}/tasks/{task_id}"
    poll_interval = max(1, int(Config.ALIYUN_BAILIAN_ASR_POLL_INTERVAL or 2))

    while True:
        query_data = _request_json("GET", query_url, headers)
        output = query_data.get("output") if isinstance(query_data, dict) else None
        if isinstance(output, dict):
            status = str(output.get("task_status", "")).upper()
            logger.info("百炼 ASR 任务状态: %s", status or "UNKNOWN")
            if status in {"SUCCEEDED", "FAILED", "UNKNOWN"}:
                return query_data
        else:
            logger.info("百炼 ASR 查询返回: %s", query_data)

        time.sleep(poll_interval)


def _fetch_transcription_text(result_data: dict[str, Any]) -> str:
    transcription_url = _find_first_string(result_data, ("transcription_url", "transcriptionUrl"))
    if transcription_url:
        logger.info("获取百炼 ASR 转写结果: %s", transcription_url)
        resp = requests.get(transcription_url, timeout=60)
        if resp.status_code >= 400:
            raise RuntimeError(f"获取转写结果失败 ({resp.status_code}): {resp.text}")
        try:
            payload = resp.json()
        except ValueError as exc:
            raise RuntimeError(f"转写结果不是 JSON: {resp.text}") from exc
        text = _extract_plain_text(payload)
        if text:
            return text
        return json.dumps(payload, ensure_ascii=False)

    text = _extract_plain_text(result_data)
    if text:
        return text

    raise RuntimeError(f"未能解析百炼 ASR 转写结果: {result_data}")


def transcribe_audio(audio_path: str) -> str:
    """
    Transcribe audio by uploading it to OSS and calling Alibaba Bailian ASR.
    """
    model_name = _normalize_model_name(Config.ALIYUN_BAILIAN_ASR_MODEL)
    use_filetrans = _is_filetrans_model(model_name) or model_name == FILETRANS_MODEL
    use_sync = _is_sync_model(model_name)
    if not use_filetrans and not use_sync:
        logger.warning("未识别的百炼 ASR 模型 %s，默认使用 %s", model_name, FILETRANS_MODEL)
        model_name = FILETRANS_MODEL
        use_filetrans = True

    api_key = _require(Config.DASHSCOPE_API_KEY, "DASHSCOPE_API_KEY")

    object_key = ""
    try:
        object_key, signed_url = upload_audio_to_oss(audio_path)
        if use_sync:
            logger.info("调用百炼同步 ASR: model=%s", model_name)
            dashscope.api_key = api_key
            dashscope.base_http_api_url = Config.DASHSCOPE_ASR_BASE_URL.rstrip("/")
            response = dashscope.MultiModalConversation.call(
                api_key=api_key,
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": signed_url,
                                },
                            }
                        ],
                    }
                ],
                result_format="message",
                asr_options={
                    "language": "zh",
                    "enable_itn": bool(Config.ALIYUN_BAILIAN_ASR_ENABLE_ITN),
                },
            )
            if getattr(response, "status_code", HTTPStatus.OK) not in (HTTPStatus.OK, 200):
                raise RuntimeError(f"百炼同步 ASR 调用失败: {response}")

            text = _extract_sync_response_text(response)
            if not text:
                raise RuntimeError(f"百炼同步 ASR 未返回文本: {response}")
            logger.info("百炼同步 ASR 完成，文本长度 %d", len(text))
            return text.strip()

        submit_url = f"{Config.DASHSCOPE_ASR_BASE_URL.rstrip('/')}/services/audio/asr/transcription"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        payload = {
            "model": model_name,
            "input": {
                "file_url": signed_url,
            },
            "parameters": {
                "channel_id": [int(Config.ALIYUN_BAILIAN_ASR_CHANNEL_ID or 0)],
                "enable_itn": bool(Config.ALIYUN_BAILIAN_ASR_ENABLE_ITN),
                "enable_words": bool(Config.ALIYUN_BAILIAN_ASR_ENABLE_WORDS),
            },
        }

        logger.info("提交百炼 ASR 任务: model=%s", model_name)
        submit_data = _request_json("POST", submit_url, headers, payload)
        output = submit_data.get("output") if isinstance(submit_data, dict) else None
        if not isinstance(output, dict) or not output.get("task_id"):
            raise RuntimeError(f"提交百炼 ASR 任务失败: {submit_data}")

        task_id = str(output["task_id"])
        logger.info("百炼 ASR 任务已提交: %s", task_id)

        result_data = _poll_filetrans_result(task_id, headers)
        output = result_data.get("output") if isinstance(result_data, dict) else None
        if isinstance(output, dict):
            status = str(output.get("task_status", "")).upper()
            if status != "SUCCEEDED":
                raise RuntimeError(f"百炼 ASR 任务未成功: {status} | {result_data}")

        text = _fetch_transcription_text(result_data)
        logger.info("百炼 ASR 完成，文本长度 %d", len(text))
        return text.strip()
    finally:
        if object_key and Config.ALIYUN_OSS_CLEANUP:
            try:
                bucket = _build_bucket()
                bucket.delete_object(object_key)
                logger.info("已清理 OSS 对象: %s", object_key)
            except Exception as exc:
                logger.warning("清理 OSS 对象失败: %s", exc)
