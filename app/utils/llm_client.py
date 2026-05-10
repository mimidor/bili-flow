from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit
import time
from types import SimpleNamespace
from typing import Any, Iterator

from openai import OpenAI

from app.models.database import LLMModelProfile, PromptTemplate, SessionLocal
from app.utils.logger import get_logger

logger = get_logger("llm_client")

WEB_SEARCH_RESPONSES_PREFIXES = (
    "qwen3.6-plus",
    "qwen3.6-flash",
    "qwen3.5-plus",
    "qwen3.5-flash",
    "qwen3-max",
)
WEB_SEARCH_CHAT_PREFIXES = (
    "qwen-plus",
    "qwen-flash",
    "qwen3-coder-plus",
    "qwen3-coder-flash",
)


class LLMServiceException(Exception):
    pass


@dataclass
class LLMCallResult:
    response: Any
    web_search_enabled: bool = False
    web_search_mode: str = "disabled"
    web_search_used: bool = False
    web_search_fallback_reason: str | None = None


def get_llm_profiles(use_case_key: str) -> tuple[PromptTemplate | None, list[LLMModelProfile]]:
    db = SessionLocal()
    try:
        prompt = db.query(PromptTemplate).filter_by(key=use_case_key).first()
        if prompt and not prompt.is_active:
            prompt = None

        profiles: list[LLMModelProfile] = []
        if prompt and prompt.model_profile_id:
            profile = db.query(LLMModelProfile).filter_by(id=prompt.model_profile_id, is_active=True).first()
            if profile:
                profiles = [profile]

        if not profiles:
            profiles = (
                db.query(LLMModelProfile)
                .filter_by(is_default=True, is_active=True)
                .order_by(LLMModelProfile.id.asc())
                .all()
            )

        if not profiles:
            fallback = db.query(LLMModelProfile).filter_by(is_active=True).order_by(LLMModelProfile.id.asc()).first()
            if fallback:
                profiles = [fallback]

        return prompt, profiles
    finally:
        db.close()


def get_llm_config(use_case_key: str) -> tuple[PromptTemplate | None, LLMModelProfile | None]:
    prompt, profiles = get_llm_profiles(use_case_key)
    return prompt, (profiles[0] if profiles else None)


def resolve_prompt_text(use_case_key: str, default_text: str = "") -> str:
    prompt, _ = get_llm_config(use_case_key)
    if prompt and prompt.is_active:
        return prompt.prompt_text
    return default_text


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def _is_kimi_profile(profile: LLMModelProfile | Any) -> bool:
    provider = _normalize(getattr(profile, "provider", ""))
    model = _normalize(getattr(profile, "model_name", ""))
    base_url = _normalize(getattr(profile, "base_url", ""))
    return (
        provider in {"kimi", "moonshot"}
        or model.startswith("kimi")
        or "moonshot.cn" in base_url
    )


def resolve_web_search_mode(profile: LLMModelProfile | None) -> str:
    if not profile or not getattr(profile, "enable_web_search", False):
        return "disabled"

    provider = _normalize(getattr(profile, "provider", ""))
    base_url = _normalize(getattr(profile, "base_url", ""))
    model = _normalize(getattr(profile, "model_name", ""))

    ali_support = provider in {"aliyun_bailian", "openai-compatible"} or "dashscope" in base_url
    if not ali_support:
        return "unsupported"

    if any(model.startswith(prefix) for prefix in WEB_SEARCH_RESPONSES_PREFIXES):
        return "responses"
    if any(model.startswith(prefix) for prefix in WEB_SEARCH_CHAT_PREFIXES):
        return "chat_completions"
    if model.startswith("qwen"):
        return "chat_completions"
    return "unsupported"


def resolve_temperature(profile: LLMModelProfile | Any, temperature: float) -> float:
    if _is_kimi_profile(profile):
        if temperature != 1:
            logger.info(
                "Kimi model requires temperature=1; overriding requested temperature=%s",
                temperature,
            )
        return 1.0
    return temperature


def build_model_prompt_suffix(profile: LLMModelProfile | None) -> str:
    if not profile:
        return ""

    pieces: list[str] = []

    if getattr(profile, "enable_web_search", False):
        mode = resolve_web_search_mode(profile)
        if mode == "unsupported":
            pieces.append(
                "\n\n【联网增强提示】"
                "当前模型配置已开启联网搜索，但该供应商/模型组合不支持联网调用，本次将退回普通问答。"
                "请仍优先修正音译、缩写、公司名、股票名和产品名，并保持输出 JSON 结构不变。"
            )
        else:
            pieces.append(
                "\n\n【联网增强提示】"
                "如涉及音译、缩写、公司名、股票名、产品名、地名或其他容易猜错的实体，"
                "请优先结合联网检索结果核实后再输出；不要改变既有 JSON schema。"
            )

    if getattr(profile, "enable_reasoning", False):
        pieces.append(
            "\n\n【推理增强提示】"
            "请先进行充分推理和交叉验证，再给出结论；遇到模糊标的、时间线、因果关系或多实体比较时，"
            "优先保证判断严谨，不要为了简短而牺牲准确性。"
        )

    if getattr(profile, "enable_image", False):
        pieces.append(
            "\n\n【图片能力提示】"
            "如果本次输入包含图片、截图或图像线索，请优先识别图中文字、关键物体、表格、图表和界面信息；"
            "如果没有图片输入，可以忽略这条提示。"
        )

    if getattr(profile, "enable_tools", False):
        pieces.append(
            "\n\n【工具使用提示】"
            "如果当前调用链提供了可用工具，请在有助于核实关键事实时优先合理使用工具，再输出最终结果。"
        )

    return "".join(pieces)


def build_openai_client(profile: LLMModelProfile) -> OpenAI | None:
    if not profile or not profile.api_key:
        return None
    try:
        kwargs: dict[str, Any] = {"api_key": profile.api_key}
        normalized_base_url = _normalize_openai_base_url(profile.base_url)
        if normalized_base_url:
            kwargs["base_url"] = normalized_base_url
        return OpenAI(**kwargs)
    except Exception as exc:
        logger.warning("Failed to build OpenAI client: %s", exc)
        return None


def _normalize_openai_base_url(base_url: str | None) -> str | None:
    if not base_url:
        return None

    raw = str(base_url).strip()
    if not raw:
        return None

    parsed = urlsplit(raw)
    path = parsed.path.rstrip("/")
    removed_suffix = None
    suffixes = (
        "/chat/completions",
        "/responses",
    )
    for suffix in suffixes:
        if path.endswith(suffix):
            path = path[: -len(suffix)]
            removed_suffix = suffix
            break

    if not path:
        path = "/"

    if not path.endswith("/"):
        path = path.rstrip("/")

    normalized = urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))
    if normalized != raw and removed_suffix:
        logger.warning(
            "Normalized OpenAI base_url from %s to %s because the configured URL ended with %s",
            raw,
            normalized,
            removed_suffix,
        )
    return normalized


def _chat_completion_stream(
    client: OpenAI,
    profile: LLMModelProfile,
    messages: list[dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
    timeout: int,
    use_web_search: bool,
):
    resolved_temperature = resolve_temperature(profile, temperature)
    kwargs: dict[str, Any] = {
        "model": profile.model_name,
        "messages": messages,
        "temperature": resolved_temperature,
        "max_tokens": max_tokens,
        "timeout": timeout,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if use_web_search:
        kwargs["extra_body"] = {"enable_search": True}
    return client.chat.completions.create(**kwargs)


def _responses_completion_stream(
    client: OpenAI,
    profile: LLMModelProfile,
    messages: list[dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
    timeout: int,
):
    resolved_temperature = resolve_temperature(profile, temperature)
    return client.responses.stream(
        model=profile.model_name,
        input=messages,
        temperature=resolved_temperature,
        max_output_tokens=max_tokens,
        timeout=timeout,
        tools=[{"type": "web_search"}],
    )


def _extract_chat_chunk_usage(chunk: Any) -> tuple[int | None, int | None, int | None]:
    usage = getattr(chunk, "usage", None)
    if not usage:
        return None, None, None

    prompt_tokens = (
        getattr(usage, "prompt_tokens", None)
        or getattr(usage, "input_tokens", None)
        or getattr(usage, "inputTokens", None)
    )
    completion_tokens = (
        getattr(usage, "completion_tokens", None)
        or getattr(usage, "output_tokens", None)
        or getattr(usage, "outputTokens", None)
    )
    total_tokens = (
        getattr(usage, "total_tokens", None)
        or getattr(usage, "totalTokens", None)
        or getattr(usage, "total_tokens_count", None)
    )
    return prompt_tokens, completion_tokens, total_tokens


def _build_synthetic_chat_response(
    *,
    text: str,
    reasoning: str = "",
    finish_reason: str | None = None,
    usage: tuple[int | None, int | None, int | None] = (None, None, None),
    tool_calls: list[dict[str, Any]] | None = None,
) -> Any:
    message = SimpleNamespace(content=text or "")
    if tool_calls:
        normalized_tool_calls: list[Any] = []
        for tool_call in tool_calls:
            function = SimpleNamespace(
                name=tool_call.get("name"),
                arguments=tool_call.get("arguments"),
            )
            normalized_tool_calls.append(
                SimpleNamespace(
                    id=tool_call.get("id"),
                    index=tool_call.get("index"),
                    type="function",
                    function=function,
                )
            )
        message.tool_calls = normalized_tool_calls

    choice = SimpleNamespace(
        message=message,
        finish_reason=finish_reason or "stop",
        reasoning_content=reasoning or None,
    )
    prompt_tokens, completion_tokens, total_tokens = usage
    return SimpleNamespace(
        choices=[choice],
        output_text=text or "",
        output=[],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        ),
        model_dump=lambda: {
            "choices": [
                {
                    "message": {
                        "content": text or "",
                        "tool_calls": tool_calls or [],
                    },
                    "finish_reason": finish_reason or "stop",
                    "reasoning_content": reasoning or None,
                }
            ],
            "output_text": text or "",
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
        },
    )


def _extract_response_stream_payload(event: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "text": "",
        "reasoning": "",
        "tool_calls": [],
    }

    if event is None:
        return payload

    event_type = str(getattr(event, "type", "") or "")
    if event_type == "response.output_text.delta":
        payload["text"] = str(getattr(event, "delta", "") or "")
        return payload

    if event_type in {"response.reasoning_text.delta", "response.reasoning_summary_text.delta"}:
        payload["reasoning"] = str(getattr(event, "delta", "") or getattr(event, "text", "") or "")
        return payload

    if event_type == "response.function_call_arguments.delta":
        payload["tool_calls"] = [
            {
                "id": getattr(event, "item_id", None),
                "index": getattr(event, "output_index", None),
                "name": "tool",
                "arguments": str(getattr(event, "delta", "") or ""),
                "partial": True,
                "status": "streaming",
            }
        ]
        return payload

    if event_type == "response.text.delta":
        payload["text"] = str(getattr(event, "text", "") or "")
        return payload

    return payload


def _run_llm_stream(
    profile: LLMModelProfile,
    messages: list[dict[str, str]],
    *,
    system_prompt: str = "",
    temperature: float = 0.3,
    max_tokens: int = 8192,
    timeout: int = 120,
) -> Iterator[dict[str, Any]]:
    client = build_openai_client(profile)
    if not client:
        raise LLMServiceException("LLM client could not be initialized or disabled")

    full_messages = _build_chat_messages(messages, system_prompt=system_prompt)
    if not full_messages:
        raise LLMServiceException("messages required")

    web_search_enabled = bool(getattr(profile, "enable_web_search", False))
    web_search_mode = resolve_web_search_mode(profile)
    started = time.perf_counter()

    yield {
        "type": "meta",
        "profile_id": getattr(profile, "id", None),
        "profile_name": getattr(profile, "name", ""),
        "provider": getattr(profile, "provider", ""),
        "model_name": getattr(profile, "model_name", ""),
        "web_search_mode": web_search_mode,
        "web_search_enabled": web_search_enabled,
    }

    def finish_event(
        *,
        response: Any,
        text: str,
        reasoning: str,
        tool_calls: list[dict[str, Any]],
        fallback: bool,
        fallback_reason: str | None = None,
    ) -> dict[str, Any]:
        elapsed = round(time.perf_counter() - started, 2)
        prompt_tokens, completion_tokens, total_tokens = _extract_usage_from_response(response)
        return {
            "type": "done",
            "success": True,
            "fallback": fallback,
            "elapsed_seconds": elapsed,
            "text": text,
            "reasoning": reasoning,
            "tool_calls": tool_calls,
            "message": f"Completed in {elapsed:.2f}s" + (" (fallback)" if fallback else ""),
            "web_search_mode": web_search_mode,
            "web_search_used": bool(web_search_enabled and web_search_mode != "unsupported" and not fallback_reason),
            "web_search_fallback_reason": fallback_reason,
            "response": response,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
        }

    def run_chat_completion(*, use_web_search: bool, fallback: bool, fallback_reason: str | None = None):
        stream = _chat_completion_stream(
            client,
            profile,
            full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            use_web_search=use_web_search,
        )

        collected: list[str] = []
        collected_reasoning: list[str] = []
        seen_tool_calls: dict[str, dict[str, Any]] = {}
        last_finish_reason: str | None = None
        usage: tuple[int | None, int | None, int | None] = (None, None, None)
        for chunk in stream:
            payload = _extract_stream_chunk_payload(chunk)
            delta_text = str(payload.get("text") or "")
            reasoning_text = str(payload.get("reasoning") or "")
            tool_calls = payload.get("tool_calls") or []
            finish_reason = None
            choices = getattr(chunk, "choices", None) or []
            if choices:
                finish_reason = getattr(choices[0], "finish_reason", None)
            if finish_reason:
                last_finish_reason = str(finish_reason)
            chunk_usage = _extract_chat_chunk_usage(chunk)
            if any(value is not None for value in chunk_usage):
                usage = chunk_usage

            if reasoning_text:
                collected_reasoning.append(reasoning_text)
                yield {"type": "thinking", "text": reasoning_text, "reasoning": reasoning_text}

            if tool_calls:
                for tool_call in tool_calls:
                    call_id = str(tool_call.get("id") or "")
                    call_key = call_id or f"{tool_call.get('index')}-{tool_call.get('name', 'tool')}"
                    existing = seen_tool_calls.get(call_key, {})
                    merged = {
                        **existing,
                        **{key: value for key, value in tool_call.items() if value not in (None, "", [], {})},
                    }
                    seen_tool_calls[call_key] = merged
                    yield {"type": "tool_call", "tool_call": merged}

            if delta_text:
                collected.append(delta_text)
                yield {"type": "delta", "text": delta_text}

        final_text = "".join(collected).strip()
        final_reasoning = "".join(collected_reasoning).strip()
        response = _build_synthetic_chat_response(
            text=final_text,
            reasoning=final_reasoning,
            finish_reason=last_finish_reason or "stop",
            usage=usage,
            tool_calls=list(seen_tool_calls.values()),
        )
        yield finish_event(
            response=response,
            text=final_text,
            reasoning=final_reasoning,
            tool_calls=list(seen_tool_calls.values()),
            fallback=fallback,
            fallback_reason=fallback_reason,
        )

    def run_responses_completion(*, fallback_reason: str | None = None):
        with _responses_completion_stream(
            client,
            profile,
            full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        ) as stream:
            collected: list[str] = []
            collected_reasoning: list[str] = []
            seen_tool_calls: dict[str, dict[str, Any]] = {}
            final_response: Any | None = None
            for event in stream:
                event_type = str(getattr(event, "type", "") or "")
                if event_type == "response.completed":
                    final_response = getattr(event, "response", None)
                    continue

                payload = _extract_response_stream_payload(event)
                delta_text = str(payload.get("text") or "")
                reasoning_text = str(payload.get("reasoning") or "")
                tool_calls = payload.get("tool_calls") or []

                if reasoning_text:
                    collected_reasoning.append(reasoning_text)
                    yield {"type": "thinking", "text": reasoning_text, "reasoning": reasoning_text}

                if tool_calls:
                    for tool_call in tool_calls:
                        call_id = str(tool_call.get("id") or "")
                        call_key = call_id or f"{tool_call.get('index')}-{tool_call.get('name', 'tool')}"
                        existing = seen_tool_calls.get(call_key, {})
                        merged = {
                            **existing,
                            **{key: value for key, value in tool_call.items() if value not in (None, "", [], {})},
                        }
                        seen_tool_calls[call_key] = merged
                        yield {"type": "tool_call", "tool_call": merged}

                if delta_text:
                    collected.append(delta_text)
                    yield {"type": "delta", "text": delta_text}

            response = final_response
            if response is None:
                response = stream.get_final_response()
            final_text = _extract_text_from_response(response).strip() or "".join(collected).strip()
            final_reasoning = _extract_reasoning_from_response(response).strip() or "".join(collected_reasoning).strip()
            yield finish_event(
                response=response,
                text=final_text,
                reasoning=final_reasoning,
                tool_calls=list(seen_tool_calls.values()),
                fallback=fallback_reason is not None,
                fallback_reason=fallback_reason,
            )

    if web_search_enabled and web_search_mode == "responses":
        try:
            yield from run_responses_completion()
            return
        except Exception as exc:
            logger.warning("Responses web search stream failed, falling back to chat completions: %s", exc)
            fallback_reason = str(exc)
            yield from run_chat_completion(
                use_web_search=False,
                fallback=True,
                fallback_reason=fallback_reason,
            )
            return

    if web_search_enabled and web_search_mode == "chat_completions":
        try:
            yield from run_chat_completion(use_web_search=True, fallback=False)
            return
        except Exception as exc:
            logger.warning("Chat completion web search stream failed, falling back to normal stream: %s", exc)
            fallback_reason = str(exc)
            yield from run_chat_completion(
                use_web_search=False,
                fallback=True,
                fallback_reason=fallback_reason,
            )
            return

    if web_search_enabled and web_search_mode == "unsupported":
        logger.warning(
            "Web search is enabled but unsupported for provider=%s model=%s; using normal stream",
            getattr(profile, "provider", ""),
            getattr(profile, "model_name", ""),
        )

    yield from run_chat_completion(use_web_search=False, fallback=False)


def _sanitize_stream_event(event: dict[str, Any]) -> dict[str, Any]:
    safe_event = dict(event)
    safe_event.pop("response", None)
    return safe_event


def _build_chat_messages(
    messages: list[dict[str, str]],
    *,
    system_prompt: str = "",
) -> list[dict[str, str]]:
    full_messages: list[dict[str, str]] = []
    prompt = (system_prompt or "").strip()
    if prompt:
        full_messages.append({"role": "system", "content": prompt})

    for message in messages:
        role = _normalize(message.get("role") if isinstance(message, dict) else "")
        if role not in {"system", "user", "assistant"}:
            role = "user"
        content = str(message.get("content") if isinstance(message, dict) else "").strip()
        if not content:
            continue
        full_messages.append({"role": role, "content": content})

    return full_messages


def _extract_stream_chunk_text(chunk: Any) -> str:
    if chunk is None:
        return ""

    choices = getattr(chunk, "choices", None)
    if not choices:
        return ""

    pieces: list[str] = []
    for choice in choices:
        delta = getattr(choice, "delta", None) or getattr(choice, "message", None)
        if not delta:
            continue
        for attr in ("content", "text", "output_text", "reasoning_content"):
            value = getattr(delta, attr, None)
            if value:
                pieces.append(str(value))
                break
    return "".join(pieces).strip()


def _stringify_tool_arguments(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        return str(value)


def _extract_stream_chunk_payload(chunk: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "text": "",
        "reasoning": "",
        "tool_calls": [],
    }

    if chunk is None:
        return payload

    choices = getattr(chunk, "choices", None)
    if not choices:
        return payload

    for choice_index, choice in enumerate(choices):
        delta = getattr(choice, "delta", None) or getattr(choice, "message", None)
        if not delta:
            continue

        text = ""
        reasoning = ""
        for attr in ("content", "text", "output_text"):
            value = getattr(delta, attr, None)
            if value:
                text = str(value)
                break
        for attr in ("reasoning_content", "reasoning", "thinking"):
            value = getattr(delta, attr, None)
            if value:
                reasoning = str(value)
                break

        if text:
            payload["text"] = f"{payload['text']}{text}"
        if reasoning:
            payload["reasoning"] = f"{payload['reasoning']}{reasoning}"

        tool_calls = getattr(delta, "tool_calls", None) or []
        for tool_index, tool_call in enumerate(tool_calls):
            function = getattr(tool_call, "function", None)
            call_id = (
                getattr(tool_call, "id", None)
                or getattr(tool_call, "tool_call_id", None)
                or getattr(tool_call, "call_id", None)
            )
            name = (
                getattr(function, "name", None)
                or getattr(tool_call, "name", None)
                or getattr(tool_call, "tool_name", None)
                or "tool"
            )
            arguments = (
                getattr(function, "arguments", None)
                or getattr(tool_call, "arguments", None)
                or getattr(tool_call, "input", None)
            )
            payload["tool_calls"].append(
                {
                    "id": call_id,
                    "index": getattr(tool_call, "index", None) or tool_index or choice_index,
                    "name": str(name),
                    "arguments": _stringify_tool_arguments(arguments),
                    "partial": True,
                    "status": "streaming",
                }
            )

    return payload


def stream_llm_chat(
    profile: LLMModelProfile,
    messages: list[dict[str, str]],
    *,
    system_prompt: str = "",
    temperature: float = 0.3,
    max_tokens: int = 8192,
    timeout: int = 120,
) -> Iterator[dict[str, Any]]:
    try:
        for event in _run_llm_stream(
            profile,
            messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        ):
            yield _sanitize_stream_event(event)
    except Exception as stream_exc:
        yield {
            "type": "error",
            "success": False,
            "message": str(stream_exc),
        }


def call_llm(
    profile: LLMModelProfile,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.3,
    max_tokens: int = 8192,
    timeout: int = 120,
) -> LLMCallResult:
    last_meta: dict[str, Any] = {}
    last_done: dict[str, Any] | None = None

    try:
        for event in _run_llm_stream(
            profile,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        ):
            event_type = str(event.get("type") or "")
            if event_type == "meta":
                last_meta = event
            elif event_type == "done":
                last_done = event
    except Exception as exc:
        raise LLMServiceException(str(exc)) from exc

    if last_done and last_done.get("success"):
        return LLMCallResult(
            response=last_done.get("response"),
            web_search_enabled=bool(last_meta.get("web_search_enabled")),
            web_search_mode=str(last_meta.get("web_search_mode") or "disabled"),
            web_search_used=bool(last_done.get("web_search_used")),
            web_search_fallback_reason=last_done.get("web_search_fallback_reason"),
        )

    raise LLMServiceException("LLM call failed")


def _extract_text_from_response(response: Any) -> str:
    if response is None:
        return ""

    seen: set[int] = set()

    def collect(value: Any) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            text = value.strip()
            return [text] if text else []

        value_id = id(value)
        if value_id in seen:
            return []
        seen.add(value_id)

        if isinstance(value, (list, tuple)):
            pieces: list[str] = []
            for item in value:
                pieces.extend(collect(item))
            return pieces

        if isinstance(value, dict):
            pieces: list[str] = []
            for key in (
                "output_text",
                "text",
                "content",
                "reasoning_content",
                "message",
                "output",
            ):
                pieces.extend(collect(value.get(key)))
            return pieces

        if hasattr(value, "model_dump"):
            try:
                return collect(value.model_dump())
            except Exception:
                pass

        pieces: list[str] = []
        for attr in (
            "output_text",
            "text",
            "content",
            "reasoning_content",
            "message",
            "output",
        ):
            pieces.extend(collect(getattr(value, attr, None)))
        return pieces

    pieces = collect(getattr(response, "output_text", None))
    if not pieces:
        pieces = collect(getattr(response, "choices", None))
    if not pieces:
        pieces = collect(getattr(response, "output", None))
    if not pieces and hasattr(response, "model_dump"):
        try:
            pieces = collect(response.model_dump())
        except Exception:
            pieces = []

    text = "\n".join(piece for piece in pieces if piece).strip()
    return text


def _extract_reasoning_from_response(response: Any) -> str:
    if response is None:
        return ""

    seen: set[int] = set()

    def collect(value: Any) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            text = value.strip()
            return [text] if text else []

        value_id = id(value)
        if value_id in seen:
            return []
        seen.add(value_id)

        if isinstance(value, (list, tuple)):
            pieces: list[str] = []
            for item in value:
                pieces.extend(collect(item))
            return pieces

        if isinstance(value, dict):
            pieces: list[str] = []
            for key in (
                "reasoning_content",
                "reasoning",
                "thinking",
            ):
                pieces.extend(collect(value.get(key)))
            return pieces

        if hasattr(value, "model_dump"):
            try:
                return collect(value.model_dump())
            except Exception:
                pass

        pieces: list[str] = []
        for attr in (
            "reasoning_content",
            "reasoning",
            "thinking",
        ):
            pieces.extend(collect(getattr(value, attr, None)))
        return pieces

    pieces = collect(getattr(response, "output", None))
    if not pieces:
        pieces = collect(getattr(response, "choices", None))
    if not pieces and hasattr(response, "model_dump"):
        try:
            pieces = collect(response.model_dump())
        except Exception:
            pieces = []

    return "\n".join(piece for piece in pieces if piece).strip()


def _extract_usage_from_response(response: Any) -> tuple[int | None, int | None, int | None]:
    usage = getattr(response, "usage", None)
    if not usage:
        return None, None, None

    prompt_tokens = (
        getattr(usage, "prompt_tokens", None)
        or getattr(usage, "input_tokens", None)
        or getattr(usage, "inputTokens", None)
    )
    completion_tokens = (
        getattr(usage, "completion_tokens", None)
        or getattr(usage, "output_tokens", None)
        or getattr(usage, "outputTokens", None)
    )
    total_tokens = (
        getattr(usage, "total_tokens", None)
        or getattr(usage, "totalTokens", None)
        or getattr(usage, "total_tokens_count", None)
    )
    return prompt_tokens, completion_tokens, total_tokens


def _build_connection_probe_profile(profile: LLMModelProfile) -> Any:
    return SimpleNamespace(
        provider=getattr(profile, "provider", None),
        base_url=getattr(profile, "base_url", None),
        api_key=getattr(profile, "api_key", None),
        model_name=getattr(profile, "model_name", None),
        enable_web_search=False,
        enable_reasoning=False,
        enable_image=False,
        enable_tools=False,
    )


def _test_llm_connection_profile(profile: Any, prompt_text: str | None = None) -> dict[str, Any]:
    try:
        started = time.perf_counter()
        probe_profile = _build_connection_probe_profile(profile)
        user_prompt = (prompt_text or "").strip() or "Reply OK if the model is reachable."
        probe_messages = [
            {"role": "system", "content": "Reply with one short sentence."},
            {"role": "user", "content": user_prompt},
        ]
        result = call_llm(probe_profile, probe_messages, max_tokens=16, timeout=12)
        elapsed = time.perf_counter() - started
        prompt_text = "\n".join(
            [
                probe_messages[0]["content"],
                probe_messages[1]["content"],
            ]
        )
        text = _extract_text_from_response(result.response)
        if text:
            logger.info(
                "LLM connection test prompt (%s/%s):\n%s",
                getattr(profile, "provider", ""),
                getattr(profile, "model_name", ""),
                prompt_text,
            )
            logger.info(
                "LLM connection test response (%s/%s):\n%s",
                getattr(profile, "provider", ""),
                getattr(profile, "model_name", ""),
                text,
            )
            return {
                "success": True,
                "message": f"Connected successfully in {elapsed:.2f}s ({result.web_search_mode})",
                "elapsed_seconds": round(elapsed, 2),
                "prompt_text": prompt_text,
                "response_text": text,
                "web_search_mode": result.web_search_mode,
                "web_search_used": result.web_search_used,
            }
        return {
            "success": False,
            "message": "Invalid response format",
            "elapsed_seconds": round(elapsed, 2),
            "prompt_text": prompt_text,
            "response_text": text,
            "web_search_mode": result.web_search_mode,
            "web_search_used": result.web_search_used,
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


def test_llm_connection(profile_id: int) -> dict[str, Any]:
    db = SessionLocal()
    try:
        profile = db.query(LLMModelProfile).filter_by(id=profile_id).first()
        if not profile:
            return {"success": False, "message": "Profile not found"}
        return _test_llm_connection_profile(profile)
    finally:
        db.close()


def test_llm_connection_config(profile_data: Any) -> dict[str, Any]:
    return _test_llm_connection_profile(profile_data)


def test_llm_connection_with_prompt(profile_data: Any, prompt_text: str) -> dict[str, Any]:
    return _test_llm_connection_profile(profile_data, prompt_text=prompt_text)
