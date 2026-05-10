from __future__ import annotations

import ctypes
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from app.utils.runtime_home import get_lock_dir


def _lock_dir() -> Path:
    lock_dir = get_lock_dir()
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False

    if os.name == "nt":
        SYNCHRONIZE = 0x00100000
        WAIT_TIMEOUT = 0x00000102
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if not handle:
            return False
        try:
            result = kernel32.WaitForSingleObject(handle, 0)
            return result == WAIT_TIMEOUT
        finally:
            kernel32.CloseHandle(handle)

    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _read_lock_info(lock_path: Path) -> dict[str, object] | None:
    try:
        raw = lock_path.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        return None


@dataclass
class SingletonLock:
    name: str
    path: Path

    def release(self) -> None:
        try:
            if self.path.exists():
                self.path.unlink()
        except Exception:
            pass

    def __enter__(self) -> "SingletonLock":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


def acquire_singleton_lock(name: str) -> SingletonLock:
    lock_path = _lock_dir() / f"{name}.lock"
    info = {
        "name": name,
        "pid": os.getpid(),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "argv": sys.argv,
    }

    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            existing = _read_lock_info(lock_path)
            existing_pid = int(existing.get("pid") or 0) if existing else 0
            if existing_pid and _is_pid_alive(existing_pid):
                raise SystemExit(
                    f"{name} is already running (pid={existing_pid}). "
                    f"Lock file: {lock_path}"
                )
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
            continue

        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(info, handle, ensure_ascii=False, indent=2)
        return SingletonLock(name=name, path=lock_path)
