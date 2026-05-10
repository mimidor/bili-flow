#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backfill video transcript text into the videos table.

This script is idempotent:
- If transcript_text already exists in the database, it keeps it and can restore
  the modern transcript.txt file if missing.
- If transcript_text is missing, it tries the modern transcript.txt first and
  then the legacy data/text/{bvid}.txt file.
"""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.database import Subscription, Video, get_db  # noqa: E402
from app.utils.paths import get_path_manager  # noqa: E402


def _normalize_text(value: str | None) -> str:
    return (value or "").strip()


def main() -> int:
    db = get_db()
    pm = get_path_manager()
    project_root = Path(__file__).resolve().parent.parent

    updated = 0
    restored_files = 0
    missing = 0

    try:
        rows = (
            db.query(Video, Subscription.name.label("uploader_name"))
            .outerjoin(Subscription, Subscription.mid == Video.mid)
            .order_by(Video.id.asc())
            .all()
        )

        for video, uploader_name in rows:
            uploader = uploader_name or f"UP主_{video.mid}"
            paths = pm.get_video_paths(uploader, video.bvid, video.title, video.pub_time, video.mid)

            transcript_text = _normalize_text(video.transcript_text)
            source_text = ""

            if transcript_text:
                changed = False
                if not video.has_subtitle:
                    video.has_subtitle = True
                    changed = True
                if not paths["transcript"].exists():
                    paths["transcript"].write_text(transcript_text, encoding="utf-8")
                    restored_files += 1
                if changed:
                    updated += 1
                    db.commit()
                continue

            if paths["transcript"].exists():
                source_text = _normalize_text(paths["transcript"].read_text(encoding="utf-8"))
            else:
                legacy_path = project_root / "data" / "text" / f"{video.bvid}.txt"
                if legacy_path.exists():
                    source_text = _normalize_text(legacy_path.read_text(encoding="utf-8"))
                    if source_text and not paths["transcript"].exists():
                        paths["transcript"].write_text(source_text, encoding="utf-8")
                        restored_files += 1

            if not source_text:
                missing += 1
                continue

            video.transcript_text = source_text
            video.has_subtitle = True
            updated += 1
            db.commit()

        db.commit()
        print(
            f"done: updated={updated}, restored_files={restored_files}, missing={missing}"
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
