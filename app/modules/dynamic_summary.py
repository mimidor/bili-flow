from __future__ import annotations

from pathlib import Path

from app.modules.processor import process_text
from app.utils.runtime_home import get_install_root


def _load_dynamic_prompt() -> str:
    prompt_path = get_install_root() / "docs" / "prompt_dynamic.md"
    try:
        return prompt_path.read_text(encoding="utf-8")
    except Exception:  # pragma: no cover - fallback path
        return (
            "You are a Bilibili dynamic analysis assistant. "
            "Return a strict JSON object with keys: summary, details, key_points, stocks, insights."
        )


DEFAULT_DYNAMIC_PROCESS_PROMPT = _load_dynamic_prompt()


def process_dynamic_text(
    raw_text: str,
    uploader_name: str = "",
    pub_time: str = "",
    dynamic_url: str = "",
    custom_prompt: str | None = None,
) -> dict:
    """Summarize a Bilibili text dynamic with the shared LLM pipeline."""
    metadata = []
    if uploader_name:
        metadata.append(f"作者：{uploader_name}")
    if pub_time:
        metadata.append(f"发布时间：{pub_time}")
    if dynamic_url:
        metadata.append(f"原动态链接：{dynamic_url}")

    enriched_text = "\n".join(metadata + ["", "动态正文：", (raw_text or "").strip()]).strip()
    title = f"{uploader_name} 的动态" if uploader_name else "B站文字动态"

    return process_text(
        raw_text=enriched_text,
        video_title=title,
        duration=0,
        custom_prompt=custom_prompt or DEFAULT_DYNAMIC_PROCESS_PROMPT,
        content_type="dynamic",
        content_id=dynamic_url.rsplit("/", 1)[-1] if dynamic_url else "",
        uploader_name=uploader_name,
    )
