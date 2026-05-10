import logging
import logging.handlers
import os
import sys

from config import Config
from app.utils.runtime_home import get_logs_dir

_FILE_HANDLERS: dict[str, logging.Handler] = {}
_CONSOLE_HANDLER: logging.Handler | None = None


def _enable_windows_ansi_support() -> None:
    if os.name != "nt":
        return

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        if handle == 0 or handle == -1:
            return

        mode = ctypes.c_uint()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return

        enable_processed_output = 0x0001
        enable_virtual_terminal = 0x0004
        new_mode = mode.value | enable_processed_output | enable_virtual_terminal
        kernel32.SetConsoleMode(handle, new_mode)
    except Exception:
        pass


class ColorFormatter(logging.Formatter):
    """Console formatter with ANSI colors by level."""

    COLORS = {
        logging.DEBUG: "\033[36m",     # cyan
        logging.INFO: "\033[32m",      # green
        logging.WARNING: "\033[33m",   # yellow
        logging.ERROR: "\033[31m",     # red
        logging.CRITICAL: "\033[35m",  # magenta
    }
    RESET = "\033[0m"

    def __init__(self, fmt: str, use_color: bool = True):
        super().__init__(fmt)
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        if not self.use_color:
            return super().format(record)

        level_color = self.COLORS.get(record.levelno, "")
        if not level_color:
            return super().format(record)

        original_levelname = record.levelname
        try:
            record.levelname = f"{level_color}{original_levelname}{self.RESET}"
            formatted = super().format(record)
        finally:
            record.levelname = original_levelname
        return formatted


def _should_colorize_console() -> bool:
    env_value = os.getenv("LOG_COLORS", "").strip().lower()
    if env_value in {"1", "true", "yes", "on"}:
        return True
    if env_value in {"0", "false", "no", "off"}:
        return False
    return sys.stdout.isatty()


def _detect_log_filename() -> str:
    configured = os.getenv("APP_LOG_FILE", "").strip()
    if configured:
        return configured

    argv = " ".join(sys.argv).lower()
    if "entrypoint-backend.py" in argv or "uvicorn" in argv:
        return "backend.log"
    if "entrypoint-scheduler.py" in argv or "\\main.py" in argv or "/main.py" in argv:
        return "scheduler.log"
    return "bili.log"


class SafeTimedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """TimedRotatingFileHandler that tolerates Windows rename collisions."""

    def doRollover(self) -> None:
        try:
            super().doRollover()
        except PermissionError as exc:
            try:
                if self.stream:
                    self.stream.close()
                self.stream = self._open()
            except Exception:
                pass
            sys.stderr.write(f"[logger] rollover skipped because file is in use: {exc}\n")
            sys.stderr.flush()


def get_logger(name: str = "bili") -> logging.Logger:
    _enable_windows_ansi_support()

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO))
    logger.propagate = False

    log_dir = get_logs_dir()
    log_dir.mkdir(parents=True, exist_ok=True)

    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_path = str(log_dir / _detect_log_filename())

    handler = _FILE_HANDLERS.get(log_path)
    if handler is None:
        handler = SafeTimedRotatingFileHandler(
            log_path,
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
            utc=False,
            delay=True,
        )
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter(format_str))
        _FILE_HANDLERS[log_path] = handler

    global _CONSOLE_HANDLER
    if _CONSOLE_HANDLER is None:
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console.setFormatter(ColorFormatter(format_str, use_color=_should_colorize_console()))
        _CONSOLE_HANDLER = console

    logger.addHandler(handler)
    logger.addHandler(_CONSOLE_HANDLER)

    return logger
