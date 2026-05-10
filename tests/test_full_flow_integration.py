from __future__ import annotations

import importlib
import os
import time
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

import pytest
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class VideoSample:
    uploader_dir: Path
    video_dir: Path
    media_path: Path
    bvid: str
    title: str
    uploader_name: str
    uploader_mid: str
    pub_time: int | None


@dataclass(frozen=True)
class DynamicSample:
    dynamic_id: str
    text: str
    mid: str
    uploader_name: str
    pub_time: str
    image_urls: list[str]
    dynamic_type: str


def _parse_uploader_dir_name(name: str) -> tuple[str, str]:
    if "_" not in name:
        return name, ""
    uploader_name, uploader_mid = name.rsplit("_", 1)
    return uploader_name, uploader_mid


def _lookup_video_pub_time(bvid: str) -> int | None:
    from app.models.database import Video, get_db

    db = get_db()
    try:
        row = db.query(Video).filter_by(bvid=bvid).first()
        if not row:
            return None
        return row.pub_time
    finally:
        db.close()


def _discover_first_video_sample() -> VideoSample | None:
    uploaders_root = PROJECT_ROOT / "data" / "uploaders"
    if not uploaders_root.exists():
        return None

    uploader_dirs = sorted(
        (path for path in uploaders_root.iterdir() if path.is_dir()),
        key=lambda path: path.name,
    )

    for uploader_dir in uploader_dirs:
        videos_dir = uploader_dir / "videos"
        if not videos_dir.exists():
            continue

        uploader_name, uploader_mid = _parse_uploader_dir_name(uploader_dir.name)
        video_dirs = sorted(
            (path for path in videos_dir.iterdir() if path.is_dir()),
            key=lambda path: path.name,
        )

        for video_dir in video_dirs:
            audio_path = video_dir / "audio.m4a"
            video_path = video_dir / "video.mp4"
            media_path = audio_path if audio_path.is_file() else video_path if video_path.is_file() else None
            if not media_path:
                continue

            parts = video_dir.name.split("_", 2)
            bvid = parts[1] if len(parts) >= 2 else ""
            title = parts[2] if len(parts) >= 3 else video_dir.name
            pub_time = _lookup_video_pub_time(bvid)

            return VideoSample(
                uploader_dir=uploader_dir,
                video_dir=video_dir,
                media_path=media_path,
                bvid=bvid,
                title=title,
                uploader_name=uploader_name,
                uploader_mid=uploader_mid,
                pub_time=pub_time,
            )

    return None


def _first_active_subscription_mid() -> tuple[str, str] | None:
    from app.models.database import Subscription, get_db

    db = get_db()
    try:
        sub = (
            db.query(Subscription)
            .filter(Subscription.is_active == True)  # noqa: E712
            .order_by(Subscription.created_at.asc())
            .first()
        )
        if not sub:
            return None
        return sub.mid, sub.name
    finally:
        db.close()


def _discover_first_text_dynamic_sample() -> DynamicSample | None:
    from app.modules.dynamic import DynamicFetcher, is_dynamic_recent

    subscription = _first_active_subscription_mid()
    if not subscription:
        return None

    mid, uploader_name = subscription
    with DynamicFetcher() as fetcher:
        dynamics = fetcher.fetch_dynamic(mid)

    for item in dynamics:
        text = (item.get("text") or "").strip()
        image_urls = [url for url in (item.get("image_urls") or []) if url]
        dynamic_type = item.get("type", "")
        if not text:
            continue
        if image_urls:
            continue
        if not dynamic_type:
            continue
        if not is_dynamic_recent(item.get("pub_time")):
            continue

        return DynamicSample(
            dynamic_id=item.get("dynamic_id", ""),
            text=text,
            mid=item.get("mid", mid),
            uploader_name=uploader_name,
            pub_time=str(item.get("pub_time") or ""),
            image_urls=image_urls,
            dynamic_type=dynamic_type,
        )

    return None


def _reload_runtime_modules():
    load_dotenv(PROJECT_ROOT / ".env", override=True)

    import config as config_module
    import app.modules.dynamic as dynamic_module
    import app.modules.feishu_docs as feishu_docs_module
    import app.modules.whisper_ai as whisper_module
    import app.modules.processor as processor_module
    import app.modules.push_channels.feishu as feishu_module
    import app.modules.push_channels as push_channels_module
    import app.modules.push as push_module

    importlib.reload(config_module)
    dynamic_module = importlib.reload(dynamic_module)
    feishu_docs_module = importlib.reload(feishu_docs_module)
    importlib.reload(feishu_module)
    importlib.reload(push_channels_module)
    importlib.reload(push_module)
    whisper_module = importlib.reload(whisper_module)
    processor_module = importlib.reload(processor_module)
    return whisper_module, processor_module, push_module, feishu_docs_module, dynamic_module


def _require_full_flow_env() -> None:
    required = [
        "OPENAI_API_KEY",
        "FEISHU_APP_ID",
        "FEISHU_APP_SECRET",
        "FEISHU_RECEIVE_ID",
        "FEISHU_RECEIVE_ID_TYPE",
    ]
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        pytest.skip(f"Missing full-flow config: {', '.join(missing)}")

    if not os.getenv("FEISHU_DOCS_ENABLED", "").strip().lower() == "true":
        pytest.skip("Missing FEISHU_DOCS_ENABLED=true for full flow doc upload")

    provider = os.getenv("ASR_PROVIDER", "").strip().lower()
    if provider in {"aliyun_bailian", "bailian", "aliyun"}:
        bailian_required = [
            "DASHSCOPE_API_KEY",
            "ALIYUN_OSS_ENDPOINT",
            "ALIYUN_OSS_BUCKET",
            "ALIYUN_OSS_ACCESS_KEY_ID",
            "ALIYUN_OSS_ACCESS_KEY_SECRET",
        ]
        bailian_missing = [name for name in bailian_required if not os.getenv(name, "").strip()]
        if bailian_missing:
            pytest.skip(f"Missing Bailian ASR config: {', '.join(bailian_missing)}")


def _require_dynamic_flow_env() -> None:
    required = [
        "OPENAI_API_KEY",
        "FEISHU_APP_ID",
        "FEISHU_APP_SECRET",
        "FEISHU_RECEIVE_ID",
        "FEISHU_RECEIVE_ID_TYPE",
        "FEISHU_DOCS_ENABLED",
        "BILIBILI_COOKIE",
    ]
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        pytest.skip(f"Missing dynamic flow config: {', '.join(missing)}")

    if os.getenv("FEISHU_DOCS_ENABLED", "").strip().lower() != "true":
        pytest.skip("Missing FEISHU_DOCS_ENABLED=true for dynamic doc upload")


@pytest.mark.integration
def test_full_video_pipeline_for_first_uploader_video():
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    _require_full_flow_env()

    sample = _discover_first_video_sample()
    if not sample:
        pytest.skip("No video sample found under data/uploaders")

    whisper_module, processor_module, push_module, feishu_docs_module, _dynamic_module = _reload_runtime_modules()

    start = time.perf_counter()
    transcript = whisper_module.transcribe_audio(str(sample.media_path))
    asr_elapsed = time.perf_counter() - start

    assert isinstance(transcript, str)
    assert transcript.strip()

    llm_start = time.perf_counter()
    summary_result = processor_module.process_text(
        raw_text=transcript,
        video_title=sample.title,
        duration=0,
    )
    llm_elapsed = time.perf_counter() - llm_start

    assert isinstance(summary_result, dict)
    assert summary_result.get("success") is True
    assert summary_result.get("summary", "").strip() or summary_result.get("details", "").strip()

    video_pub_time_str = datetime.fromtimestamp(sample.pub_time).strftime("%Y-%m-%d %H:%M:%S") if sample.pub_time else ""

    md_content = f"""# {sample.title}

**URL**: https://www.bilibili.com/video/{sample.bvid}

**UP主**: {sample.uploader_name}

**发布时间**: {video_pub_time_str or '未知'}

---

{summary_result.get("details", "")}
"""

    doc_start = time.perf_counter()
    doc_result = feishu_docs_module.push_video_summary_to_doc(
        title=sample.title,
        markdown_content=md_content,
        bvid=sample.bvid,
        uploader_name=sample.uploader_name,
    )
    doc_elapsed = time.perf_counter() - doc_start

    assert doc_result is not None, "Feishu doc upload failed"
    assert doc_result.get("url", "").strip()

    push_payload = {
        "type": "video",
        "title": sample.title,
        "summary": summary_result.get("summary", ""),
        "details": summary_result.get("details", ""),
        "key_points": summary_result.get("key_points", []),
        "tags": summary_result.get("tags", []),
        "stocks": summary_result.get("stocks", []),
        "insights": summary_result.get("insights", ""),
        "url": f"https://www.bilibili.com/video/{sample.bvid}",
        "doc_url": doc_result.get("url", ""),
        "pub_time": video_pub_time_str,
        "duration_minutes": 0,
        "timestamp": sample.pub_time,
    }

    push_start = time.perf_counter()
    push_result = push_module.push_content(push_payload, ["feishu"])
    push_elapsed = time.perf_counter() - push_start

    print("\n=== Full flow integration ===")
    print(f"Uploader: {sample.uploader_name} ({sample.uploader_mid})")
    print(f"Video dir: {sample.video_dir}")
    print(f"Media: {sample.media_path}")
    print(f"ASR time: {asr_elapsed:.2f}s")
    print(f"LLM time: {llm_elapsed:.2f}s")
    print(f"Doc time: {doc_elapsed:.2f}s")
    print(f"Doc URL: {doc_result.get('url', '')}")
    print(f"Push time: {push_elapsed:.2f}s")
    print(f"Push success: {push_result}")
    print(f"Summary: {summary_result.get('summary', '')[:300]}")

    assert push_result is True


@pytest.mark.integration
def test_full_dynamic_pipeline_for_first_text_dynamic():
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    _require_dynamic_flow_env()

    sample = _discover_first_text_dynamic_sample()
    if not sample:
        pytest.skip("No text dynamic sample found from the first active subscription")

    _whisper_module, _processor_module, push_module, feishu_docs_module, dynamic_module = _reload_runtime_modules()

    dynamic_payload = {
        "type": "dynamic",
        "uploader_name": sample.uploader_name,
        "text": sample.text,
        "image_urls": sample.image_urls,
        "images": [],
        "pub_time": sample.pub_time,
        "url": f"https://www.bilibili.com/opus/{sample.dynamic_id}",
    }

    assert dynamic_module.should_push_dynamic(dynamic_payload) is True

    llm_start = time.perf_counter()
    summary_result = dynamic_module.process_dynamic_text(
        raw_text=sample.text,
        uploader_name=sample.uploader_name,
        pub_time=sample.pub_time,
        dynamic_url=f"https://www.bilibili.com/opus/{sample.dynamic_id}",
    )
    llm_elapsed = time.perf_counter() - llm_start

    assert isinstance(summary_result, dict)
    assert summary_result.get("summary", "").strip() or summary_result.get("details", "").strip()

    dynamic_title = summary_result.get("summary", "") or sample.text[:40] or sample.dynamic_id
    md_content = f"""# {dynamic_title}

**作者**: {sample.uploader_name}

**发布时间**: {sample.pub_time or '未知'}

**原动态链接**: https://www.bilibili.com/opus/{sample.dynamic_id}

---

## 原始动态

{sample.text}

---

{summary_result.get("details", "")}
"""

    doc_start = time.perf_counter()
    doc_result = feishu_docs_module.push_dynamic_summary_to_doc(
        title=dynamic_title,
        markdown_content=md_content,
        dynamic_id=sample.dynamic_id,
        uploader_name=sample.uploader_name,
    )
    doc_elapsed = time.perf_counter() - doc_start

    assert doc_result is not None, "Dynamic Feishu doc upload failed"
    assert doc_result.get("url", "").strip()

    dynamic_payload.update(
        {
            "summary": summary_result.get("summary", ""),
            "details": summary_result.get("details", ""),
            "key_points": summary_result.get("key_points", []),
            "tags": summary_result.get("tags", []),
            "stocks": summary_result.get("stocks", []),
            "insights": summary_result.get("insights", ""),
            "doc_url": doc_result.get("url", ""),
        }
    )

    push_start = time.perf_counter()
    push_result = push_module.push_content(dynamic_payload, ["feishu"])
    push_elapsed = time.perf_counter() - push_start

    print("\n=== Dynamic integration ===")
    print(f"Dynamic ID: {sample.dynamic_id}")
    print(f"Mid: {sample.mid}")
    print(f"Uploader: {sample.uploader_name}")
    print(f"Type: {sample.dynamic_type}")
    print(f"Text: {sample.text[:300]}")
    print(f"LLM time: {llm_elapsed:.2f}s")
    print(f"Doc time: {doc_elapsed:.2f}s")
    print(f"Doc URL: {doc_result.get('url', '')}")
    print(f"Push time: {push_elapsed:.2f}s")
    print(f"Push success: {push_result}")
    print(f"Summary: {summary_result.get('summary', '')[:300]}")

    assert push_result is True
