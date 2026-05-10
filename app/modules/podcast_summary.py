from __future__ import annotations

from pathlib import Path

from app.modules.processor import process_text
from app.utils.runtime_home import get_install_root


def _load_podcast_prompt() -> str:
    prompt_path = get_install_root() / "docs" / "prompt_podcast.md"
    try:
        return prompt_path.read_text(encoding="utf-8")
    except Exception:  # pragma: no cover - fallback path
        return (
            "You are a podcast analysis assistant. "
            "Return a strict JSON object with keys: summary, details, key_points, stocks, insights."
        )


DEFAULT_PODCAST_PROCESS_PROMPT = _load_podcast_prompt()


def process_podcast_text(
    raw_text: str,
    uploader_name: str = "",
    pub_time: str = "",
    episode_url: str = "",
    custom_prompt: str | None = None,
) -> dict:
    metadata = []
    if uploader_name:
        metadata.append(f"作者：{uploader_name}")
    if pub_time:
        metadata.append(f"发布时间：{pub_time}")
    if episode_url:
        metadata.append(f"原链接：{episode_url}")

    enriched_text = "\n".join(metadata + ["", "节目正文：", (raw_text or "").strip()]).strip()
    title = f"{uploader_name} 的小宇宙节目" if uploader_name else "小宇宙节目"

    return process_text(
        raw_text=enriched_text,
        video_title=title,
        duration=0,
        custom_prompt=custom_prompt or DEFAULT_PODCAST_PROCESS_PROMPT,
        content_type="podcast",
        content_id=episode_url.rsplit("/", 1)[-1] if episode_url else "",
        uploader_name=uploader_name,
    )
