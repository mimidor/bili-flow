from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import re
import time
from pathlib import Path
from typing import Any

from app.services.telemetry import record_llm_usage
from app.utils.logger import get_logger
from app.utils.runtime_home import get_install_root
from config import Config

logger = get_logger("processor")

try:
    from openai import APIError
except ImportError:
    logger.warning("openai package is not installed.")

from app.utils.llm_client import (
    build_model_prompt_suffix,
    call_llm as client_call_llm,
    get_llm_config,
    get_llm_profiles,
    resolve_prompt_text,
    resolve_web_search_mode,
)


def _load_process_prompt() -> str:
    """Load the default video processing prompt."""
    prompt_path = get_install_root() / "docs" / "prompt.md"
    try:
        return prompt_path.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover - fallback path
        logger.warning("Failed to load prompt.md: %s", exc)
        return (
            "You are a content processing assistant. "
            "Return a single JSON object with keys: summary, details, key_points, stocks, insights."
        )


DEFAULT_PROCESS_PROMPT = _load_process_prompt()
LLM_MAX_CONTINUATIONS = 2
LLM_CONTINUE_PROMPT = (
    "Please continue the incomplete JSON output. "
    "Do not repeat already emitted content. "
    "Do not explain. Output only the missing continuation."
)
LLM_REPAIR_PROMPT = (
    "The previous answer is not valid JSON. "
    "Rewrite it as a single complete JSON object only. "
    "Do not add markdown, code fences, comments, or any extra text. "
    "Preserve the original content as much as possible."
)


def _call_llm(
    profile,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.3,
    max_tokens: int = 8192,
    timeout: int = 1200,
):
    """Call the configured LLM client once."""
    if not profile:
        raise RuntimeError("LLM profile is not available")
    return client_call_llm(
        profile=profile,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )


def _unwrap_response(response_or_result: Any) -> Any:
    return getattr(response_or_result, "response", response_or_result)


def _response_text(response_or_result) -> str:
    response = _unwrap_response(response_or_result)
    if response is None:
        return ""
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    content = response.choices[0].message.content if getattr(response, "choices", None) else ""
    return (content or "").strip()


def _response_finish_reason(response) -> str:
    response = _unwrap_response(response)
    if not getattr(response, "choices", None):
        return ""
    return (response.choices[0].finish_reason or "").strip()


def _extract_json_object(text: str) -> str | None:
    text = text or ""
    start = None
    depth = 0
    in_string = False
    escape = False

    for idx, char in enumerate(text):
        if start is None:
            if char == "{":
                start = idx
                depth = 1
            continue

        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]

    return None


def _parse_json_payload(text: str) -> dict[str, Any] | None:
    json_text = _extract_json_object(text)
    if not json_text:
        return None
    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _build_llm_messages(system_prompt: str, user_prompt: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _build_continue_messages(
    system_prompt: str,
    user_prompt: str,
    partial_text: str,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
        {"role": "assistant", "content": partial_text},
        {"role": "user", "content": LLM_CONTINUE_PROMPT},
    ]


def _build_repair_messages(
    system_prompt: str,
    user_prompt: str,
    partial_text: str,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
        {"role": "assistant", "content": partial_text},
        {"role": "user", "content": LLM_REPAIR_PROMPT},
    ]


def _candidate_texts_for_continuation(accumulated_text: str, continuation_text: str) -> list[str]:
    accumulated_text = accumulated_text or ""
    continuation_text = continuation_text or ""

    stripped_continuation = continuation_text.lstrip()
    if stripped_continuation.startswith("{"):
        return [
            continuation_text.strip(),
            f"{accumulated_text}{continuation_text}".strip(),
        ]

    return [
        f"{accumulated_text}{continuation_text}".strip(),
        continuation_text.strip(),
    ]


def _web_search_prompt_suffix(profile) -> str:
    return build_model_prompt_suffix(profile)


def _llm_search_usage_fields(profile, llm_result: Any | None = None) -> dict[str, Any]:
    if not profile:
        return {
            "web_search_enabled": False,
            "web_search_mode": "disabled",
            "web_search_used": False,
            "web_search_fallback_reason": None,
        }
    mode = resolve_web_search_mode(profile)
    return {
        "web_search_enabled": bool(getattr(profile, "enable_web_search", False)),
        "web_search_mode": getattr(llm_result, "web_search_mode", None) or mode,
        "web_search_used": bool(getattr(llm_result, "web_search_used", False)),
        "web_search_fallback_reason": getattr(llm_result, "web_search_fallback_reason", None),
    }


def _call_llm_with_continuation(
    profile,
    system_prompt: str,
    user_prompt: str,
) -> tuple[str, str, Any]:
    llm_result = _call_llm(profile, _build_llm_messages(system_prompt, user_prompt))
    response = _unwrap_response(llm_result)
    accumulated_text = _response_text(response)
    finish_reason = _response_finish_reason(response)
    continuation_count = 0
    parsed = _parse_json_payload(accumulated_text)

    while (finish_reason == "length" or parsed is None) and continuation_count < LLM_MAX_CONTINUATIONS:
        continuation_count += 1
        if finish_reason == "length":
            logger.warning("LLM response truncated, requesting continuation %d", continuation_count)
            next_messages = _build_continue_messages(system_prompt, user_prompt, accumulated_text)
        else:
            logger.warning("LLM response was not valid JSON, requesting repair %d", continuation_count)
            next_messages = _build_repair_messages(system_prompt, user_prompt, accumulated_text)

        continue_result = _call_llm(profile, next_messages)
        continuation_text = _response_text(continue_result)

        candidate_texts = _candidate_texts_for_continuation(accumulated_text, continuation_text)
        selected_text = None
        for candidate in candidate_texts:
            if _parse_json_payload(candidate) is not None:
                selected_text = candidate
                break

        if selected_text is None:
            selected_text = candidate_texts[0]

        accumulated_text = selected_text
        llm_result = continue_result
        response = _unwrap_response(llm_result)
        finish_reason = _response_finish_reason(response)
        parsed = _parse_json_payload(accumulated_text)

    return accumulated_text, finish_reason, llm_result


def _extract_usage(response: Any) -> tuple[int | None, int | None, int | None]:
    usage = getattr(response, "usage", None)
    if not usage:
        return None, None, None

    return (
        getattr(usage, "prompt_tokens", None),
        getattr(usage, "completion_tokens", None),
        getattr(usage, "total_tokens", None),
    )


def _normalize_list_value(value: Any, limit: int) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]
    normalized: list[str] = []
    for item in value[:limit]:
        text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


PUSH_RELEVANCE_PROMPT = (
    "你是一个推送前内容审核器，只负责判断是否需要推送。"
    "你的目标是找出那些与投资、宏观经济、金融市场、公司经营、行业变化、政策新闻、社会公共事件、"
    "商业资讯完全无关的内容，例如纯个人情感、家庭琐事、日常流水账、旅行、吃喝玩乐、游戏、穿搭、美妆、"
    "纯娱乐吐槽等。"
    "只有在内容几乎完全不涉及上述主题时，才 should_push=false。"
    "只要内容和投资、宏观、社会、新闻、商业、公共事件有任何合理关联，哪怕是间接讨论，也应该 should_push=true。"
    "如果不确定，默认 should_push=true。"
    "输出必须是严格 JSON，不要输出任何多余解释。"
    "JSON 字段固定为：should_push(boolean), reason(string), confidence(number, 0到1之间), matched_topics(array of strings), signals(array of strings)。"
)


def _stringify_relevance_piece(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        pieces = [str(item).strip() for item in value if str(item).strip()]
        return "\n".join(pieces)
    if isinstance(value, dict):
        try:
            return json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            return str(value).strip()
    return str(value).strip()


def _build_relevance_context(content_data: dict[str, Any]) -> str:
    ordered_keys = [
        "title",
        "summary",
        "details",
        "text",
        "insights",
        "key_points",
        "tags",
        "stocks",
        "uploader_name",
        "pub_time",
        "url",
        "doc_url",
    ]
    lines: list[str] = []
    for key in ordered_keys:
        value = _stringify_relevance_piece(content_data.get(key))
        if value:
            lines.append(f"{key}: {value}")
    if not lines:
        return ""
    return "\n".join(lines)[:12000]


def _local_relevance_fallback(content_data: dict[str, Any]) -> dict[str, Any]:
    text_parts = [
        _stringify_relevance_piece(content_data.get("title")),
        _stringify_relevance_piece(content_data.get("summary")),
        _stringify_relevance_piece(content_data.get("details")),
        _stringify_relevance_piece(content_data.get("text")),
        _stringify_relevance_piece(content_data.get("insights")),
    ]
    text = "\n".join(part for part in text_parts if part).strip()
    lowered = text.lower()

    relevant_keywords = [
        "投资",
        "宏观",
        "金融",
        "经济",
        "市场",
        "股市",
        "股票",
        "基金",
        "债券",
        "利率",
        "通胀",
        "降息",
        "政策",
        "行业",
        "公司",
        "财报",
        "商业",
        "社会",
        "新闻",
        "事件",
        "舆论",
        "消费",
        "科技",
        "ai",
        "人工智能",
        "就业",
        "房价",
    ]
    irrelevant_keywords = [
        "儿女情长",
        "恋爱",
        "分手",
        "失恋",
        "表白",
        "老婆",
        "老公",
        "女友",
        "男友",
        "家庭",
        "孩子",
        "日常",
        "旅游",
        "旅行",
        "吃喝",
        "健身",
        "游戏",
        "穿搭",
        "美妆",
        "vlog",
        "情感",
        "吐槽",
    ]

    if any(keyword in text for keyword in relevant_keywords):
        return {
            "should_push": True,
            "reason": "本地兜底判断为相关或至少不完全无关",
            "confidence": 0.55,
            "matched_topics": ["本地兜底"],
            "signals": ["found relevant keyword"],
            "success": False,
        }

    if any(keyword in lowered for keyword in irrelevant_keywords) and len(text) < 1200:
        return {
            "should_push": False,
            "reason": "本地兜底判断为纯个人/日常内容",
            "confidence": 0.7,
            "matched_topics": ["个人生活", "日常"],
            "signals": ["found irrelevant keyword"],
            "success": False,
        }

    return {
        "should_push": True,
        "reason": "本地兜底默认放行",
        "confidence": 0.5,
        "matched_topics": [],
        "signals": [],
        "success": False,
    }


def _normalize_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.5
    if confidence < 0:
        return 0.0
    if confidence > 1:
        return 1.0
    return confidence


def _normalize_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y", "是", "可以", "推送"}:
            return True
        if lowered in {"false", "0", "no", "n", "否", "不", "不推送"}:
            return False
    return default


def _parse_relevance_payload(parsed: dict[str, Any]) -> dict[str, Any]:
    should_push = _normalize_bool(parsed.get("should_push", True))
    reason = str(parsed.get("reason", "")).strip()[:300]
    confidence = _normalize_confidence(parsed.get("confidence", 0.5))
    matched_topics = _normalize_list_value(parsed.get("matched_topics", []), 8)
    signals = _normalize_list_value(parsed.get("signals", []), 8)
    return {
        "should_push": should_push,
        "reason": reason or ("内容与投资/宏观/社会相关" if should_push else "内容与投资/宏观/社会完全无关"),
        "confidence": confidence,
        "matched_topics": matched_topics,
        "signals": signals,
        "success": True,
    }


def classify_push_relevance(
    content_data: dict[str, Any],
    *,
    content_type: str | None = None,
    content_id: str | None = None,
    content_title: str | None = None,
    uploader_name: str | None = None,
) -> dict[str, Any]:
    content_data = content_data or {}
    started_at = time.perf_counter()
    
    prompt_template, profile = get_llm_config("push_relevance")
    model_name = profile.model_name if profile else (Config.OPENAI_MODEL or "gpt-3.5-turbo")
    provider_name = getattr(profile, "provider", "openai") if profile else "openai"

    inferred_content_type = content_type or str(content_data.get("type") or "unknown")
    inferred_content_id = content_id or str(
        content_data.get("content_id")
        or content_data.get("url")
        or content_data.get("dynamic_id")
        or content_data.get("bvid")
        or ""
    )
    inferred_title = (content_title or content_data.get("title") or content_data.get("text") or "").strip()
    inferred_uploader = (uploader_name or content_data.get("uploader_name") or "").strip()
    context = _build_relevance_context(content_data)

    if not context:
        result = {
            "should_push": True,
            "reason": "内容为空，默认放行",
            "confidence": 0.5,
            "matched_topics": [],
            "signals": [],
            "success": False,
        }
        record_llm_usage(
            content_type="push_filter",
            content_id=inferred_content_id,
            content_title=inferred_title,
            uploader_name=inferred_uploader,
            provider=provider_name,
            model=model_name,
            web_search_enabled=_llm_search_usage_fields(profile)["web_search_enabled"],
            web_search_mode=resolve_web_search_mode(profile),
            web_search_used=False,
            web_search_fallback_reason=None,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            duration_ms=int((time.perf_counter() - started_at) * 1000),
            success=False,
            error_message="empty content context",
            raw_response=result,
        )
        return result

    system_prompt = (prompt_template.prompt_text if prompt_template else PUSH_RELEVANCE_PROMPT) + _web_search_prompt_suffix(profile)
    user_prompt = (
        f"内容类型: {inferred_content_type}\n"
        f"标题: {inferred_title or '未提供'}\n"
        f"作者: {inferred_uploader or '未提供'}\n"
        f"内容上下文:\n{context}"
    )

    if not profile or not profile.api_key:
        result = _local_relevance_fallback(content_data)
        record_llm_usage(
            content_type="push_filter",
            content_id=inferred_content_id,
            content_title=inferred_title,
            uploader_name=inferred_uploader,
            provider=provider_name,
            model=model_name,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            duration_ms=int((time.perf_counter() - started_at) * 1000),
            success=False,
            error_message="LLM API not configured",
            raw_response=result,
            **_llm_search_usage_fields(profile),
        )
        return result

    try:
        llm_result = _call_llm(
            profile,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=512,
            timeout=120,
        )
        response = _unwrap_response(llm_result)
        response_text = _response_text(response)
        prompt_tokens, completion_tokens, total_tokens = _extract_usage(response)
        parsed = _parse_json_payload(response_text)

        if not parsed:
            logger.warning("Push relevance classifier returned unparsable JSON, using local fallback")
            result = _local_relevance_fallback(content_data)
            record_llm_usage(
                content_type="push_filter",
                content_id=inferred_content_id,
                content_title=inferred_title,
                uploader_name=inferred_uploader,
                provider=provider_name,
                model=getattr(response, "model", None) or model_name,
                web_search_enabled=_llm_search_usage_fields(profile, llm_result)["web_search_enabled"],
                web_search_mode=_llm_search_usage_fields(profile, llm_result)["web_search_mode"],
                web_search_used=_llm_search_usage_fields(profile, llm_result)["web_search_used"],
                web_search_fallback_reason=_llm_search_usage_fields(profile, llm_result)["web_search_fallback_reason"],
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                duration_ms=int((time.perf_counter() - started_at) * 1000),
                success=False,
                error_message="LLM returned unparsable JSON",
                raw_response=response_text,
            )
            return result

        result = _parse_relevance_payload(parsed)
        record_llm_usage(
            content_type="push_filter",
            content_id=inferred_content_id,
            content_title=inferred_title,
            uploader_name=inferred_uploader,
            provider=provider_name,
            model=getattr(response, "model", None) or model_name,
            web_search_enabled=_llm_search_usage_fields(profile, llm_result)["web_search_enabled"],
            web_search_mode=_llm_search_usage_fields(profile, llm_result)["web_search_mode"],
            web_search_used=_llm_search_usage_fields(profile, llm_result)["web_search_used"],
            web_search_fallback_reason=_llm_search_usage_fields(profile, llm_result)["web_search_fallback_reason"],
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            duration_ms=int((time.perf_counter() - started_at) * 1000),
            success=True,
            raw_response=response_text,
        )
        return result
    except APIError as exc:
        logger.warning("Push relevance classifier API call failed, using local fallback: %s", exc)
        result = _local_relevance_fallback(content_data)
        record_llm_usage(
            content_type="push_filter",
            content_id=inferred_content_id,
            content_title=inferred_title,
            uploader_name=inferred_uploader,
            provider=provider_name,
            model=model_name,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            duration_ms=int((time.perf_counter() - started_at) * 1000),
            success=False,
            error_message=str(exc),
            raw_response={"error": str(exc)},
            **_llm_search_usage_fields(profile),
        )
        return result
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Push relevance classifier failed: %s", exc, exc_info=True)
        result = _local_relevance_fallback(content_data)
        record_llm_usage(
            content_type="push_filter",
            content_id=inferred_content_id,
            content_title=inferred_title,
            uploader_name=inferred_uploader,
            provider=provider_name,
            model=model_name,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            duration_ms=int((time.perf_counter() - started_at) * 1000),
            success=False,
            error_message=str(exc),
            raw_response={"error": str(exc)},
            **_llm_search_usage_fields(profile),
        )
        return result


def _parse_process_response(text: str, raw_text: str) -> dict[str, Any]:
    parsed = _parse_json_payload(text) or {}
    corrected_text = raw_text

    summary = str(parsed.get("summary", "")).strip()[:200]
    details = str(parsed.get("details", "")).strip()
    key_points = _normalize_list_value(parsed.get("key_points", []), 5)
    stocks = _normalize_list_value(parsed.get("stocks", []), 10)

    insights_value = parsed.get("insights", "")
    if isinstance(insights_value, list):
        insights = "\n".join(str(item) for item in insights_value).strip()[:500]
    else:
        insights = str(insights_value).strip()[:500]

    tags_value = parsed.get("tags", [])
    tags = _normalize_list_value(tags_value, 5)

    return {
        "corrected_text": corrected_text,
        "summary": summary,
        "details": details,
        "key_points": key_points,
        "stocks": stocks,
        "tags": tags,
        "insights": insights,
    }


def _process_local(raw_text: str, video_title: str, duration: int) -> dict[str, Any]:
    lines = [line.strip() for line in raw_text.replace("。", ".").replace("！", "!").replace("？", "?").splitlines()]
    lines = [line for line in lines if line]

    summary = "。".join(lines[:3]) if lines else raw_text[:120]
    summary = summary[:200]

    key_points = [line[:80] for line in lines[:5] if len(line) > 10]

    keyword_map = {
        "AI": ["AI", "人工智能", "机器学习", "深度学习", "神经网络"],
        "技术": ["技术", "开发", "代码", "算法", "编程"],
        "创业": ["创业", "融资", "投资", "公司", "产品"],
        "产品": ["产品", "功能", "用户", "体验", "设计"],
        "观点": ["观点", "分析", "看法", "思考", "评论"],
    }
    tags = []
    text_lower = raw_text.lower()
    for tag, keywords in keyword_map.items():
        if any(keyword.lower() in text_lower for keyword in keywords):
            tags.append(tag)
    if not tags:
        tags = ["其他"]

    logger.info(
        "Local processing done: summary=%d chars, key_points=%d, tags=%d",
        len(summary),
        len(key_points),
        len(tags),
    )

    return {
        "corrected_text": raw_text,
        "summary": summary,
        "details": "",
        "key_points": key_points[:5],
        "stocks": [],
        "tags": tags[:5],
        "insights": "This summary was generated locally because the configured LLM is unavailable.",
        "success": False,
    }


def _normalize_text_lines(raw_text: str) -> list[str]:
    text = (raw_text or "").replace("\u3000", " ").strip()
    if not text:
        return []

    lines: list[str] = []
    for line in text.splitlines():
        cleaned = re.sub(r"\s+", " ", line).strip(" \t-•*●·")
        if cleaned:
            lines.append(cleaned)

    deduped: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if line in seen:
            continue
        seen.add(line)
        deduped.append(line)
    return deduped


def _extract_keyword_tags(text: str) -> list[str]:
    keyword_groups = [
        ("宏观", ["宏观", "经济", "通胀", "利率", "降息", "加息", "就业", "数据", "政策"]),
        ("金融", ["金融", "市场", "券商", "基金", "债券", "A股", "美股", "港股", "指数", "行情"]),
        ("公司", ["公司", "财报", "业绩", "营收", "利润", "估值", "市值", "融资", "并购"]),
        ("行业", ["行业", "赛道", "产业链", "板块", "概念", "供应链"]),
        ("科技", ["科技", "AI", "人工智能", "芯片", "模型", "算法", "算力", "软件", "硬件"]),
        ("社会", ["社会", "新闻", "热点", "公共事件", "舆论", "民生", "消费", "房地产"]),
        ("生活", ["日常", "恋爱", "分手", "家庭", "孩子", "旅游", "吃喝", "游戏", "穿搭", "美妆", "vlog"]),
    ]

    lowered = text.lower()
    tags: list[str] = []
    for label, keywords in keyword_groups:
        if any(keyword.lower() in lowered for keyword in keywords):
            tags.append(label)
    if not tags:
        tags.append("其他")
    return tags[:5]


def _extract_reference_terms(text: str) -> list[str]:
    reference_terms = [
        "A股",
        "美股",
        "港股",
        "基金",
        "债券",
        "指数",
        "上证指数",
        "深证成指",
        "创业板",
        "科创板",
        "沪深300",
        "纳指",
        "标普500",
        "美联储",
        "英伟达",
        "苹果",
        "特斯拉",
        "微软",
        "谷歌",
        "亚马逊",
        "比亚迪",
        "宁德时代",
        "茅台",
        "腾讯",
        "阿里巴巴",
        "京东",
        "小米",
    ]

    lowered = text.lower()
    found: list[str] = []
    for term in reference_terms:
        if term.lower() in lowered and term not in found:
            found.append(term)

    ticker_candidates = re.findall(r"\b[A-Z]{2,6}\b", text)
    for ticker in ticker_candidates:
        if ticker not in found and ticker not in {"AI"}:
            found.append(ticker)

    return found[:10]


def _build_local_details_markdown(
    *,
    video_title: str,
    raw_text: str,
    summary: str,
    key_points: list[str],
    tags: list[str],
    stocks: list[str],
    duration: int,
) -> str:
    lines = _normalize_text_lines(raw_text)
    excerpt_lines = lines[:8]
    excerpt = "\n".join(f"- {line}" for line in excerpt_lines) if excerpt_lines else "- 无可用原文摘录"
    key_points_md = "\n".join(f"- {point}" for point in (key_points[:5] or [])) or "- 未能自动提炼出明确要点"
    tags_md = "、".join(tags[:5]) if tags else "其他"
    stocks_md = "、".join(stocks[:10]) if stocks else "未提取到明确标的"
    summary_md = summary or "未生成摘要"

    return (
        "## 本地兜底摘要\n"
        f"- 标题：{video_title or '未提供'}\n"
        f"- 时长：{duration or 0}\n"
        "- 说明：LLM 未返回可用 JSON，以下内容由本地规则生成\n\n"
        "## 概览\n"
        f"{summary_md}\n\n"
        "## 关键点\n"
        f"{key_points_md}\n\n"
        "## 主题标签\n"
        f"- {tags_md}\n\n"
        "## 相关标的\n"
        f"- {stocks_md}\n\n"
        "## 原文摘录\n"
        f"{excerpt}\n"
    )


def _process_local_rich(raw_text: str, video_title: str, duration: int) -> dict[str, Any]:
    lines = _normalize_text_lines(raw_text)
    summary = "。".join(lines[:2]) if lines else raw_text[:120]
    summary = re.sub(r"\s+", " ", summary).strip()[:220]

    key_points = [line[:120] for line in lines[:6] if len(line) > 8]
    if not key_points and raw_text:
        key_points = [raw_text[:120].strip()]

    tags = _extract_keyword_tags(raw_text)
    stocks = _extract_reference_terms(raw_text)
    details = _build_local_details_markdown(
        video_title=video_title,
        raw_text=raw_text,
        summary=summary,
        key_points=key_points,
        tags=tags,
        stocks=stocks,
        duration=duration,
    )

    logger.info(
        "Local processing done: summary=%d chars, key_points=%d, tags=%d, stocks=%d",
        len(summary),
        len(key_points),
        len(tags),
        len(stocks),
    )

    return {
        "corrected_text": raw_text,
        "summary": summary,
        "details": details,
        "key_points": key_points[:5],
        "stocks": stocks[:10],
        "tags": tags[:5],
        "insights": "本地兜底摘要已生成，原因通常是 LLM 不可用、返回 JSON 非法或修复失败。",
        "success": False,
    }


def _resolve_process_use_case_key(content_type: str) -> str:
    if content_type == "dynamic":
        return "dynamic_summary"
    if content_type == "podcast":
        return "podcast_summary"
    return "video_summary"


def _resolve_process_prompt_text(
    *,
    content_type: str,
    custom_prompt: str | None,
    prompt_template,
) -> str:
    fallback_prompt = DEFAULT_PROCESS_PROMPT
    if content_type == "dynamic":
        fallback_prompt = resolve_prompt_text("dynamic_summary", fallback_prompt)
    elif content_type == "podcast":
        fallback_prompt = resolve_prompt_text("podcast_summary", fallback_prompt)
    return custom_prompt or (prompt_template.prompt_text if prompt_template else fallback_prompt)


def _profile_label(profile: Any | None) -> str:
    if not profile:
        return "Local Fallback"

    name = str(getattr(profile, "name", "") or "").strip()
    model_name = str(getattr(profile, "model_name", "") or "").strip()
    if name and model_name and name != model_name:
        return f"{name} ({model_name})"
    return model_name or name or "Unnamed Model"


def _render_model_result_body(result: dict[str, Any]) -> str:
    details = str(result.get("details") or "").strip()
    if details:
        return details

    parts: list[str] = []
    summary = str(result.get("summary") or "").strip()
    if summary:
        parts.append(f"**Summary**\n\n{summary}")

    key_points = [str(item).strip() for item in result.get("key_points", []) if str(item).strip()]
    if key_points:
        parts.append("**Key Points**\n\n" + "\n".join(f"- {item}" for item in key_points[:5]))

    stocks = [str(item).strip() for item in result.get("stocks", []) if str(item).strip()]
    if stocks:
        parts.append("**Referenced Targets**\n\n" + "、".join(stocks[:10]))

    insights = str(result.get("insights") or "").strip()
    if insights:
        parts.append(f"**Insights**\n\n{insights}")

    return "\n\n".join(parts).strip()


def _merge_unique_texts(values: list[Any], limit: int) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in value or []:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            merged.append(text)
            if len(merged) >= limit:
                return merged
    return merged


def _merge_multi_model_results(raw_text: str, model_runs: list[dict[str, Any]]) -> dict[str, Any]:
    successful_runs = [run for run in model_runs if run["result"].get("success")]
    primary_run = successful_runs[0] if successful_runs else model_runs[0]

    summary_parts: list[str] = []
    for run in successful_runs:
        summary_text = str(run["result"].get("summary") or "").strip()
        if summary_text:
            summary_parts.append(f"{_profile_label(run.get('profile'))}: {summary_text}")
    summary = " | ".join(summary_parts)[:200] if summary_parts else str(primary_run["result"].get("summary") or "")[:200]

    details_sections: list[str] = []
    insights_sections: list[str] = []
    for run in model_runs:
        profile = run.get("profile")
        provider_name = str(run.get("provider_name") or getattr(profile, "provider", "") or "openai")
        model_name = str(run.get("model_name") or getattr(profile, "model_name", "") or "")
        result = run["result"]
        body = _render_model_result_body(result)
        status_text = "Success" if result.get("success") else f"Failed: {run.get('error_message') or 'fallback used'}"
        meta_lines = [
            f"**Provider**: {provider_name}",
            f"**Model**: {model_name or _profile_label(profile)}",
            f"**Status**: {status_text}",
        ]
        details_sections.append(
            "\n\n".join(
                [
                    f"## {_profile_label(profile)}",
                    "\n".join(meta_lines),
                    body or "No structured content was returned.",
                ]
            ).strip()
        )

        insights_text = str(result.get("insights") or "").strip()
        if insights_text:
            insights_sections.append(f"{_profile_label(profile)}: {insights_text}")

    merged_runs = successful_runs or model_runs
    return {
        "corrected_text": str(primary_run["result"].get("corrected_text") or raw_text),
        "summary": summary,
        "details": "\n\n---\n\n".join(details_sections).strip(),
        "key_points": _merge_unique_texts([run["result"].get("key_points", []) for run in merged_runs], 10),
        "stocks": _merge_unique_texts([run["result"].get("stocks", []) for run in merged_runs], 20),
        "tags": _merge_unique_texts([run["result"].get("tags", []) for run in merged_runs], 10),
        "insights": "\n\n".join(insights_sections)[:1000],
        "success": any(run["result"].get("success") for run in model_runs),
        "model_outputs": [
            {
                "profile_id": getattr(run.get("profile"), "id", None),
                "name": getattr(run.get("profile"), "name", None),
                "provider": run.get("provider_name"),
                "model_name": run.get("model_name"),
                "success": bool(run["result"].get("success")),
                "summary": run["result"].get("summary"),
                "details": run["result"].get("details"),
                "key_points": run["result"].get("key_points", []),
                "stocks": run["result"].get("stocks", []),
                "tags": run["result"].get("tags", []),
                "insights": run["result"].get("insights"),
                "error_message": run.get("error_message"),
            }
            for run in model_runs
        ],
        "active_models": [run.get("model_name") for run in model_runs if run.get("model_name")],
    }


def _process_text_with_profile(
    *,
    profile,
    prompt_text: str,
    raw_text: str,
    video_title: str,
    duration: int,
    content_type: str,
    content_id: str,
    uploader_name: str,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    model_name = profile.model_name if profile else (Config.OPENAI_MODEL or "gpt-3.5-turbo")
    provider_name = getattr(profile, "provider", "openai") if profile else "openai"

    if not profile or not profile.api_key:
        logger.info("LLM API not configured, using local fallback")
        result = _process_local_rich(raw_text, video_title, duration)
        record_llm_usage(
            content_type=content_type,
            content_id=content_id,
            content_title=video_title,
            uploader_name=uploader_name,
            provider=provider_name,
            model=model_name,
            web_search_enabled=_llm_search_usage_fields(profile)["web_search_enabled"],
            web_search_mode=resolve_web_search_mode(profile),
            web_search_used=False,
            web_search_fallback_reason=None,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            duration_ms=int((time.perf_counter() - started_at) * 1000),
            success=False,
            error_message="OpenAI API not configured",
            raw_response=result,
        )
        return {
            "profile": profile,
            "provider_name": provider_name,
            "model_name": model_name,
            "result": result,
            "error_message": "OpenAI API not configured",
        }

    try:
        logger.info("Start LLM processing with model=%s, raw text length=%d", model_name, len(raw_text))
        system_prompt = prompt_text + _web_search_prompt_suffix(profile)
        user_prompt = f"[Title]\n{video_title or 'N/A'}\n\n[Transcript]\n{raw_text}"

        response_text, finish_reason, llm_result = _call_llm_with_continuation(profile, system_prompt, user_prompt)
        response = _unwrap_response(llm_result)
        prompt_tokens, completion_tokens, total_tokens = _extract_usage(response)

        if _parse_json_payload(response_text) is None:
            logger.warning("LLM returned unparsable JSON (finish_reason=%s), using local fallback", finish_reason or "unknown")
            result = _process_local_rich(raw_text, video_title, duration)
            error_message = "LLM returned unparsable JSON"
            record_llm_usage(
                content_type=content_type,
                content_id=content_id,
                content_title=video_title,
                uploader_name=uploader_name,
                provider=provider_name,
                model=getattr(response, "model", None) or model_name,
                **_llm_search_usage_fields(profile, llm_result),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                duration_ms=int((time.perf_counter() - started_at) * 1000),
                success=False,
                error_message=error_message,
                raw_response=response_text,
            )
            return {
                "profile": profile,
                "provider_name": provider_name,
                "model_name": getattr(response, "model", None) or model_name,
                "result": result,
                "error_message": error_message,
            }

        result = _parse_process_response(response_text, raw_text)
        result["success"] = True
        record_llm_usage(
            content_type=content_type,
            content_id=content_id,
            content_title=video_title,
            uploader_name=uploader_name,
            provider=provider_name,
            model=getattr(response, "model", None) or model_name,
            **_llm_search_usage_fields(profile, llm_result),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            duration_ms=int((time.perf_counter() - started_at) * 1000),
            success=True,
            raw_response=response_text,
        )
        return {
            "profile": profile,
            "provider_name": provider_name,
            "model_name": getattr(response, "model", None) or model_name,
            "result": result,
            "error_message": None,
        }
    except APIError as exc:
        logger.warning("OpenAI API call failed, using local fallback: %s", exc)
        result = _process_local_rich(raw_text, video_title, duration)
        record_llm_usage(
            content_type=content_type,
            content_id=content_id,
            content_title=video_title,
            uploader_name=uploader_name,
            provider=provider_name,
            model=model_name,
            web_search_enabled=_llm_search_usage_fields(profile)["web_search_enabled"],
            web_search_mode=resolve_web_search_mode(profile),
            web_search_used=False,
            web_search_fallback_reason=None,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            duration_ms=int((time.perf_counter() - started_at) * 1000),
            success=False,
            error_message=str(exc),
            raw_response={"error": str(exc)},
        )
        return {
            "profile": profile,
            "provider_name": provider_name,
            "model_name": model_name,
            "result": result,
            "error_message": str(exc),
        }
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("LLM processing failed: %s", exc, exc_info=True)
        result = _process_local_rich(raw_text, video_title, duration)
        record_llm_usage(
            content_type=content_type,
            content_id=content_id,
            content_title=video_title,
            uploader_name=uploader_name,
            provider=provider_name,
            model=model_name,
            web_search_enabled=_llm_search_usage_fields(profile)["web_search_enabled"],
            web_search_mode=resolve_web_search_mode(profile),
            web_search_used=False,
            web_search_fallback_reason=None,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            duration_ms=int((time.perf_counter() - started_at) * 1000),
            success=False,
            error_message=str(exc),
            raw_response={"error": str(exc)},
        )
        return {
            "profile": profile,
            "provider_name": provider_name,
            "model_name": model_name,
            "result": result,
            "error_message": str(exc),
        }

def process_text(
    raw_text: str,
    video_title: str = "",
    duration: int = 0,
    custom_prompt: str | None = None,
    content_type: str = "video",
    content_id: str = "",
    uploader_name: str = "",
) -> dict[str, Any]:
    raw_text = (raw_text or "").strip()
    if not raw_text:
        logger.warning("Raw text is empty")
        return {
            "corrected_text": "",
            "summary": "",
            "details": "",
            "key_points": [],
            "stocks": [],
            "insights": "",
            "success": False,
        }

    started_at = time.perf_counter()
    
    use_case_key = "video_summary"
    if content_type == "dynamic":
        use_case_key = "dynamic_summary"
    elif content_type == "podcast":
        use_case_key = "podcast_summary"
        
    prompt_template, profile = get_llm_config(use_case_key)
    model_name = profile.model_name if profile else (Config.OPENAI_MODEL or "gpt-3.5-turbo")
    provider_name = getattr(profile, "provider", "openai") if profile else "openai"

    if not profile or not profile.api_key:
        logger.info("LLM API not configured, using local fallback")
        result = _process_local_rich(raw_text, video_title, duration)
        record_llm_usage(
            content_type=content_type,
            content_id=content_id,
            content_title=video_title,
            uploader_name=uploader_name,
            provider=provider_name,
            model=model_name,
            web_search_enabled=_llm_search_usage_fields(profile)["web_search_enabled"],
            web_search_mode=resolve_web_search_mode(profile),
            web_search_used=False,
            web_search_fallback_reason=None,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            duration_ms=int((time.perf_counter() - started_at) * 1000),
            success=False,
            error_message="OpenAI API not configured",
            raw_response=result,
        )
        return result

    try:
        logger.info("Start LLM processing, raw text length=%d", len(raw_text))
        
        fallback_prompt = DEFAULT_PROCESS_PROMPT
        if content_type == "dynamic": fallback_prompt = resolve_prompt_text("dynamic_summary", fallback_prompt)
        if content_type == "podcast": fallback_prompt = resolve_prompt_text("podcast_summary", fallback_prompt)
        
        system_prompt = (custom_prompt or (prompt_template.prompt_text if prompt_template else fallback_prompt)) + _web_search_prompt_suffix(profile)
        user_prompt = (
            f"【视频标题】\n{video_title or '未提供'}\n\n"
            f"【语音识别原始文本】\n{raw_text}"
        )

        response_text, finish_reason, llm_result = _call_llm_with_continuation(profile, system_prompt, user_prompt)
        response = _unwrap_response(llm_result)
        prompt_tokens, completion_tokens, total_tokens = _extract_usage(response)

        if _parse_json_payload(response_text) is None:
            logger.warning("LLM returned unparsable JSON (finish_reason=%s), using local fallback", finish_reason or "unknown")
            result = _process_local_rich(raw_text, video_title, duration)
            record_llm_usage(
                content_type=content_type,
                content_id=content_id,
                content_title=video_title,
                uploader_name=uploader_name,
                provider=provider_name,
                model=getattr(response, "model", None) or model_name,
                **_llm_search_usage_fields(profile, llm_result),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                duration_ms=int((time.perf_counter() - started_at) * 1000),
                success=False,
                error_message="LLM returned unparsable JSON",
                raw_response=response_text,
            )
            return result

        result = _parse_process_response(response_text, raw_text)
        result["success"] = True
        record_llm_usage(
            content_type=content_type,
            content_id=content_id,
            content_title=video_title,
            uploader_name=uploader_name,
            provider=provider_name,
            model=getattr(response, "model", None) or model_name,
            **_llm_search_usage_fields(profile, llm_result),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            duration_ms=int((time.perf_counter() - started_at) * 1000),
            success=True,
            raw_response=response_text,
        )
        return result
    except APIError as exc:
        logger.warning("OpenAI API call failed, using local fallback: %s", exc)
        result = _process_local_rich(raw_text, video_title, duration)
        record_llm_usage(
            content_type=content_type,
            content_id=content_id,
            content_title=video_title,
            uploader_name=uploader_name,
            provider=provider_name,
            model=model_name,
            web_search_enabled=_llm_search_usage_fields(profile)["web_search_enabled"],
            web_search_mode=resolve_web_search_mode(profile),
            web_search_used=False,
            web_search_fallback_reason=None,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            duration_ms=int((time.perf_counter() - started_at) * 1000),
            success=False,
            error_message=str(exc),
            raw_response={"error": str(exc)},
        )
        return result


def process_text(
    raw_text: str,
    video_title: str = "",
    duration: int = 0,
    custom_prompt: str | None = None,
    content_type: str = "video",
    content_id: str = "",
    uploader_name: str = "",
) -> dict[str, Any]:
    raw_text = (raw_text or "").strip()
    if not raw_text:
        logger.warning("Raw text is empty")
        return {
            "corrected_text": "",
            "summary": "",
            "details": "",
            "key_points": [],
            "stocks": [],
            "insights": "",
            "success": False,
        }

    use_case_key = _resolve_process_use_case_key(content_type)
    prompt_template, profiles = get_llm_profiles(use_case_key)
    prompt_text = _resolve_process_prompt_text(
        content_type=content_type,
        custom_prompt=custom_prompt,
        prompt_template=prompt_template,
    )

    profile_list = list(profiles or [None])
    if len(profile_list) == 1:
        model_runs = [
            _process_text_with_profile(
                profile=profile_list[0],
                prompt_text=prompt_text,
                raw_text=raw_text,
                video_title=video_title,
                duration=duration,
                content_type=content_type,
                content_id=content_id,
                uploader_name=uploader_name,
            )
        ]
    else:
        with ThreadPoolExecutor(max_workers=len(profile_list)) as executor:
            futures = [
                executor.submit(
                    _process_text_with_profile,
                    profile=profile,
                    prompt_text=prompt_text,
                    raw_text=raw_text,
                    video_title=video_title,
                    duration=duration,
                    content_type=content_type,
                    content_id=content_id,
                    uploader_name=uploader_name,
                )
                for profile in profile_list
            ]
            model_runs = [future.result() for future in futures]

    if len(model_runs) == 1:
        return model_runs[0]["result"]
    return _merge_multi_model_results(raw_text, model_runs)
