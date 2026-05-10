from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.utils.runtime_home import get_data_dir


def _sanitize_dirname(name: str, max_length: int = 50) -> str:
    name = re.sub(r'[<>:"|?*]', "", name)
    name = re.sub(r"[\\/]", "-", name)
    name = re.sub(r"\s+", "_", name)
    name = name.strip("._")
    if len(name) > max_length:
        name = name[:max_length].rsplit("_", 1)[0]
    return name


def _sanitize_filename(title: str, max_length: int = 50) -> str:
    return _sanitize_dirname(title, max_length)


class PathManager:
    """Manage runtime storage paths."""

    def __init__(self, data_root: str | Path | None = None):
        if data_root is None:
            data_root = get_data_dir()

        self.data_root = Path(data_root)
        self.uploaders_dir = self.data_root / "uploaders"
        self.uploaders_dir.mkdir(parents=True, exist_ok=True)

    def get_uploader_dir(self, uploader_name: str, uploader_mid: str | None = None) -> Path:
        clean_name = _sanitize_dirname(uploader_name)
        dir_name = f"{clean_name}_{uploader_mid}" if uploader_mid else clean_name
        uploader_dir = self.uploaders_dir / dir_name
        uploader_dir.mkdir(parents=True, exist_ok=True)
        return uploader_dir

    def get_video_dir(
        self,
        uploader_name: str,
        bvid: str,
        title: str,
        pub_time: int | None = None,
        uploader_mid: str | None = None,
    ) -> Path:
        uploader_dir = self.get_uploader_dir(uploader_name, uploader_mid)
        videos_dir = uploader_dir / "videos"
        videos_dir.mkdir(parents=True, exist_ok=True)

        if pub_time:
            date_str = datetime.fromtimestamp(pub_time).strftime("%Y%m%d")
        else:
            date_str = "unknown"

        clean_title = _sanitize_filename(title, max_length=40)
        video_dir = videos_dir / f"{date_str}_{bvid}_{clean_title}"
        video_dir.mkdir(parents=True, exist_ok=True)
        return video_dir

    def get_video_paths(
        self,
        uploader_name: str,
        bvid: str,
        title: str,
        pub_time: int | None = None,
        uploader_mid: str | None = None,
    ) -> dict[str, Path]:
        video_dir = self.get_video_dir(uploader_name, bvid, title, pub_time, uploader_mid)
        return {
            "dir": video_dir,
            "video": video_dir / "video.mp4",
            "audio": video_dir / "audio.m4a",
            "transcript": video_dir / "transcript.txt",
            "summary": video_dir / "summary.md",
        }

    def get_dynamic_dir(
        self,
        uploader_name: str,
        dynamic_id: str,
        uploader_mid: str | None = None,
    ) -> Path:
        uploader_dir = self.get_uploader_dir(uploader_name, uploader_mid)
        dynamics_dir = uploader_dir / "dynamics"
        dynamics_dir.mkdir(parents=True, exist_ok=True)
        dynamic_dir = dynamics_dir / dynamic_id
        dynamic_dir.mkdir(parents=True, exist_ok=True)
        return dynamic_dir

    def get_dynamic_paths(
        self,
        uploader_name: str,
        dynamic_id: str,
        uploader_mid: str | None = None,
    ) -> dict[str, Path]:
        dynamic_dir = self.get_dynamic_dir(uploader_name, dynamic_id, uploader_mid)
        images_dir = dynamic_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        return {
            "dir": dynamic_dir,
            "text": dynamic_dir / "text.txt",
            "summary": dynamic_dir / "summary.md",
            "images": images_dir,
        }

    def get_podcast_episode_dir(
        self,
        podcast_name: str,
        eid: str,
        title: str,
        pub_time: int | None = None,
        podcast_pid: str | None = None,
    ) -> Path:
        podcast_dir = self.get_uploader_dir(podcast_name, podcast_pid)
        episodes_dir = podcast_dir / "episodes"
        episodes_dir.mkdir(parents=True, exist_ok=True)

        if pub_time:
            date_str = datetime.fromtimestamp(pub_time).strftime("%Y%m%d")
        else:
            date_str = "unknown"

        clean_title = _sanitize_filename(title, max_length=40)
        episode_dir = episodes_dir / f"{date_str}_{eid}_{clean_title}"
        episode_dir.mkdir(parents=True, exist_ok=True)
        return episode_dir

    def get_podcast_episode_paths(
        self,
        podcast_name: str,
        eid: str,
        title: str,
        pub_time: int | None = None,
        podcast_pid: str | None = None,
    ) -> dict[str, Path]:
        episode_dir = self.get_podcast_episode_dir(podcast_name, eid, title, pub_time, podcast_pid)
        return {
            "dir": episode_dir,
            "audio": episode_dir / "audio.m4a",
            "transcript": episode_dir / "transcript.txt",
            "summary": episode_dir / "summary.md",
        }

    def find_video_dir_by_bvid(self, bvid: str) -> Optional[Path]:
        if not self.uploaders_dir.exists():
            return None

        for uploader_dir in self.uploaders_dir.iterdir():
            if not uploader_dir.is_dir():
                continue

            videos_dir = uploader_dir / "videos"
            if not videos_dir.exists():
                continue

            for video_dir in videos_dir.iterdir():
                if not video_dir.is_dir():
                    continue
                if f"_{bvid}_" in video_dir.name or video_dir.name.endswith(f"_{bvid}"):
                    return video_dir

        return None

    def find_uploader_dir_by_mid(self, mid: str) -> Optional[Path]:
        if not self.uploaders_dir.exists():
            return None

        for uploader_dir in self.uploaders_dir.iterdir():
            if not uploader_dir.is_dir():
                continue
            if uploader_dir.name.endswith(f"_{mid}"):
                return uploader_dir

        return None


_default_manager: Optional[PathManager] = None


def get_path_manager() -> PathManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = PathManager()
    return _default_manager

