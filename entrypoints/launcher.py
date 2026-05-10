from __future__ import annotations

import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.utils.process_lock import acquire_singleton_lock
from app.utils.runtime_home import get_runtime_home


BACKEND_FOLDER_NAME = "bili-flow-backend"
SCHEDULER_FOLDER_NAME = "bili-flow-scheduler"
LAUNCHER_FOLDER_NAME = "bili-flow-launcher"
BACKEND_EXE_NAME = "bili-flow-backend.exe"
SCHEDULER_EXE_NAME = "bili-flow-scheduler.exe"


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _current_root() -> Path:
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


def _release_root() -> Path:
    root = _current_root()
    if _is_frozen():
        if root.name.lower() == LAUNCHER_FOLDER_NAME:
            return root.parent
        return root
    return root


def _backend_executable() -> Path:
    if _is_frozen():
        return _release_root() / BACKEND_FOLDER_NAME / BACKEND_EXE_NAME
    return _release_root() / "entrypoints" / "entrypoint-backend.py"


def _scheduler_executable() -> Path:
    if _is_frozen():
        return _release_root() / SCHEDULER_FOLDER_NAME / SCHEDULER_EXE_NAME
    return _release_root() / "entrypoints" / "entrypoint-scheduler.py"


def _build_env() -> dict[str, str]:
    env = os.environ.copy()
    runtime_home = Path(env.get("BILI_FLOW_HOME") or env.get("BILI_AUTO_HOME") or get_runtime_home())
    runtime_home.mkdir(parents=True, exist_ok=True)
    (runtime_home / "data").mkdir(parents=True, exist_ok=True)
    (runtime_home / "logs").mkdir(parents=True, exist_ok=True)
    (runtime_home / "models").mkdir(parents=True, exist_ok=True)
    (runtime_home / ".runtime" / "locks").mkdir(parents=True, exist_ok=True)
    env["BILI_FLOW_HOME"] = str(runtime_home)
    env["BILI_AUTO_HOME"] = str(runtime_home)

    venv_scripts = PROJECT_ROOT / ".venv" / "Scripts"
    path_parts: list[str] = []
    if venv_scripts.exists():
        path_parts.append(str(venv_scripts))

    tools_dir = _release_root() / "tools"
    if tools_dir.exists():
        path_parts.append(str(tools_dir))
    current_path = env.get("PATH", "")
    if current_path:
        path_parts.append(current_path)
    if path_parts:
        env["PATH"] = os.pathsep.join(path_parts)
    return env


def _ensure_runtime_env_file(env: dict[str, str]) -> None:
    runtime_home = Path(env["BILI_AUTO_HOME"])
    env_path = runtime_home / ".env"
    if env_path.exists():
        return

    example_path = _release_root() / ".env.example"
    if example_path.exists():
        env_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
        return

    env_path.write_text("", encoding="utf-8")


def _spawn(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.Popen[str]:
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        shell=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def _wait_for_health(url: str, timeout_seconds: int = 120) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                if 200 <= response.status < 300:
                    return True
        except URLError:
            pass
        except Exception:
            pass
        time.sleep(1)
    return False


def _service_command(executable: Path) -> list[str]:
    if _is_frozen():
        return [str(executable)]
    return [sys.executable, str(executable)]


def main() -> None:
    lock = acquire_singleton_lock("launcher")
    try:
        env = _build_env()
        _ensure_runtime_env_file(env)
        release_root = _release_root()
        backend_cwd = release_root / BACKEND_FOLDER_NAME if _is_frozen() else release_root
        scheduler_cwd = release_root / SCHEDULER_FOLDER_NAME if _is_frozen() else release_root

        backend_executable = _backend_executable()
        scheduler_executable = _scheduler_executable()
        if not backend_executable.exists():
            raise SystemExit(f"Backend executable not found: {backend_executable}")
        if not scheduler_executable.exists():
            raise SystemExit(f"Scheduler executable not found: {scheduler_executable}")

        _spawn(_service_command(backend_executable), backend_cwd, env)
        _spawn(_service_command(scheduler_executable), scheduler_cwd, env)

        host = env.get("ADMIN_BACKEND_HOST", "127.0.0.1")
        port = env.get("ADMIN_BACKEND_PORT", "8000")
        health_url = f"http://{host}:{port}/healthz"
        if not _wait_for_health(health_url):
            raise SystemExit("Backend failed to become healthy")

        webbrowser.open(f"http://{host}:{port}/")
    finally:
        lock.release()


if __name__ == "__main__":
    main()
