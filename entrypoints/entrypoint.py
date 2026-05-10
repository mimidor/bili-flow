from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ENTRYPOINT_DIR = Path(__file__).resolve().parent
ROOT = ENTRYPOINT_DIR.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _enable_utf8_io() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


_enable_utf8_io()

SERVICE_WRAPPERS = {
    "backend": ENTRYPOINT_DIR / "entrypoint-backend.py",
    "scheduler": ENTRYPOINT_DIR / "entrypoint-scheduler.py",
}

SERVICE_NAMES = tuple(SERVICE_WRAPPERS.keys())


def get_service_command(name: str) -> tuple[list[str], Path | None]:
    wrapper = SERVICE_WRAPPERS.get(name)
    if wrapper is None:
        raise SystemExit(f"Unsupported service: {name}")
    if not wrapper.exists():
        raise SystemExit(f"Service wrapper is missing: {wrapper.name}")
    return [sys.executable, str(wrapper)], ROOT


def spawn(command: list[str], name: str, *, cwd: Path | None = None) -> subprocess.Popen[str]:
    print(f"Starting {name}: {' '.join(command)}", flush=True)
    return subprocess.Popen(
        command,
        cwd=str(cwd or ROOT),
        env=os.environ.copy(),
        shell=False,
    )


def terminate(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                capture_output=True,
                text=True,
            )
        else:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except Exception:
        try:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except Exception:
            pass


def run_single(service: str) -> int:
    command, cwd = get_service_command(service)
    return subprocess.call(command, cwd=str(cwd or ROOT), env=os.environ.copy())


def parse_service_list() -> list[str]:
    raw_services = os.getenv("APP_SERVICES", "").strip()
    if raw_services:
        services = [service.strip().lower() for service in raw_services.split(",") if service.strip()]
        invalid = [service for service in services if service not in SERVICE_NAMES]
        if invalid:
            raise SystemExit(f"Unsupported APP_SERVICES value(s): {', '.join(invalid)}")
        return services

    mode = os.getenv("APP_MODE", "all").strip().lower()
    if mode in {"backend", "scheduler"}:
        return [mode]
    if mode == "all":
        return ["backend", "scheduler"]
    raise SystemExit(f"Unsupported APP_MODE: {mode}")


def run_many(services: list[str]) -> int:
    processes: dict[str, subprocess.Popen[str]] = {}
    for service in services:
        command, cwd = get_service_command(service)
        processes[service] = spawn(command, service, cwd=cwd)

    shutting_down = False

    def shutdown(*_: object) -> None:
        nonlocal shutting_down
        if shutting_down:
            return
        shutting_down = True
        for process in processes.values():
            terminate(process)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            for name, process in processes.items():
                code = process.poll()
                if code is not None:
                    print(f"{name} exited, stopping the remaining services.", flush=True)
                    shutdown()
                    return int(code)
            time.sleep(1)
    finally:
        shutdown()


def main() -> None:
    services = parse_service_list()
    if len(services) == 1:
        raise SystemExit(run_single(services[0]))
    raise SystemExit(run_many(services))


if __name__ == "__main__":
    main()
