from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.utils.process_lock import acquire_singleton_lock


def _enable_utf8_io() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


_enable_utf8_io()


def main() -> None:
    lock = acquire_singleton_lock("backend")
    host = os.getenv("ADMIN_BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("ADMIN_BACKEND_PORT", "8000"))
    reload_flag = os.getenv("ADMIN_BACKEND_RELOAD", "false").strip().lower() in {"1", "true", "yes", "on"}
    try:
        uvicorn.run(
            "admin_backend.main:app",
            host=host,
            port=port,
            reload=reload_flag,
        )
    finally:
        lock.release()


if __name__ == "__main__":
    main()
