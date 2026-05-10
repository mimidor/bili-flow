from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import ctypes
from ctypes import wintypes
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
            reconfigure(encoding="utf-8", errors="replace")


_enable_utf8_io()

WEB_DIR = ROOT / "web"
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


if os.name == "nt":
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JobObjectExtendedLimitInformation = 9
    CREATE_NEW_PROCESS_GROUP = 0x00000200

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]


class WindowsJob:
    def __init__(self) -> None:
        self.handle: int | None = None
        if os.name != "nt":
            return
        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = kernel32.SetInformationJobObject(
            handle,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not ok:
            error = ctypes.get_last_error()
            kernel32.CloseHandle(handle)
            raise OSError(error, "SetInformationJobObject failed")
        self.handle = handle

    def assign(self, process: subprocess.Popen[str]) -> None:
        if os.name != "nt" or self.handle is None:
            return
        ok = kernel32.AssignProcessToJobObject(self.handle, wintypes.HANDLE(process._handle))
        if not ok:
            raise OSError(ctypes.get_last_error(), f"AssignProcessToJobObject failed for pid={process.pid}")

    def close(self) -> None:
        if os.name != "nt" or self.handle is None:
            return
        kernel32.CloseHandle(self.handle)
        self.handle = None


class ManagedProcess:
    def __init__(self, name: str, command: list[str], cwd: Path) -> None:
        self.name = name
        self.command = command
        self.cwd = cwd
        self.process: subprocess.Popen[str] | None = None
        self.reader_thread: threading.Thread | None = None

    def start(self, env: dict[str, str]) -> None:
        creationflags = CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        self.process = subprocess.Popen(
            self.command,
            cwd=str(self.cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            shell=False,
            creationflags=creationflags,
        )
        self.reader_thread = threading.Thread(target=self._forward_output, daemon=True)
        self.reader_thread.start()

    def _forward_output(self) -> None:
        if not self.process or not self.process.stdout:
            return
        prefix = f"[{self.name}] "
        try:
            for line in self.process.stdout:
                text = line.rstrip("\r\n")
                if text:
                    print(prefix + text, flush=True)
                else:
                    print(prefix, flush=True)
        finally:
            try:
                self.process.stdout.close()
            except Exception:
                pass

    def poll(self) -> int | None:
        if not self.process:
            return None
        return self.process.poll()

    def terminate_tree(self) -> None:
        if not self.process or self.poll() is not None:
            return
        try:
            subprocess.run(
                ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except Exception:
            pass

    @property
    def pid(self) -> int | None:
        return self.process.pid if self.process else None


def _resolve_npm() -> str:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise SystemExit("npm not found. Install Node.js and ensure npm is on PATH.")
    return npm


def _build_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def _check_prerequisites() -> tuple[str, dict[str, str]]:
    if not VENV_PYTHON.exists():
        raise SystemExit(f"Virtual environment interpreter not found: {VENV_PYTHON}")
    npm = _resolve_npm()
    env = _build_env()
    return npm, env


def _build_processes(npm: str) -> list[ManagedProcess]:
    return [
        ManagedProcess("frontend", [npm, "run", "dev"], WEB_DIR),
        ManagedProcess("backend", [str(VENV_PYTHON), str(ENTRYPOINT_DIR / "entrypoint-backend.py")], ROOT),
        ManagedProcess("scheduler", [str(VENV_PYTHON), str(ENTRYPOINT_DIR / "entrypoint-scheduler.py")], ROOT),
    ]


def _print_banner(processes: list[ManagedProcess]) -> None:
    print("Development stack started:", flush=True)
    print("  frontend : http://127.0.0.1:5173", flush=True)
    print("  backend  : http://127.0.0.1:8000", flush=True)
    print("  scheduler: entrypoints/entrypoint-scheduler.py", flush=True)
    for proc in processes:
        print(f"  {proc.name} pid={proc.pid}", flush=True)


def main() -> int:
    npm, env = _check_prerequisites()
    managed = _build_processes(npm)
    job = WindowsJob()
    shutdown_started = False

    def shutdown() -> None:
        nonlocal shutdown_started
        if shutdown_started:
            return
        shutdown_started = True
        for proc in reversed(managed):
            proc.terminate_tree()

    def handle_signal(_signum: int, _frame: object) -> None:
        print("[dev-stack] shutdown requested", flush=True)
        shutdown()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        for proc in managed:
            print(f"[dev-stack] starting {proc.name}: {' '.join(proc.command)}", flush=True)
            proc.start(env)
            try:
                job.assign(proc.process)
            except Exception as exc:
                print(f"[dev-stack] warning: failed to attach {proc.name} to job object: {exc}", flush=True)

        _print_banner(managed)

        exit_code = 0
        failing_name = ""

        while True:
            if shutdown_started:
                exit_code = 0
                break

            for proc in managed:
                code = proc.poll()
                if code is not None:
                    exit_code = int(code)
                    failing_name = proc.name
                    print(
                        f"[dev-stack] {proc.name} exited with code {exit_code}, stopping remaining services.",
                        flush=True,
                    )
                    shutdown()
                    break

            if shutdown_started:
                if failing_name and exit_code == 0:
                    # Even a clean exit is unexpected in the long-running dev stack.
                    exit_code = 1
                break

            time.sleep(0.5)

        return exit_code
    except KeyboardInterrupt:
        print("[dev-stack] keyboard interrupt received", flush=True)
        shutdown()
        return 0
    finally:
        shutdown()
        for proc in managed:
            thread = proc.reader_thread
            if thread and thread.is_alive():
                thread.join(timeout=1.0)
        job.close()


if __name__ == "__main__":
    raise SystemExit(main())
