from __future__ import annotations

import os
import signal
import time
import sys
from threading import Event, Thread

from app.utils.logger import get_logger
from app.utils.process_lock import acquire_singleton_lock
from config import Config


def _enable_utf8_io() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


_enable_utf8_io()


def _run_timed_step(logger, label: str, func):
    start = time.perf_counter()
    logger.info("[启动] 开始: %s", label)
    result = func()
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info("[启动] 完成: %s (%.0f ms)", label, elapsed_ms)
    return result


def main():
    lock = acquire_singleton_lock("scheduler")
    logger = get_logger("main")
    logger.info("=" * 50)
    logger.info("系统启动")
    logger.info("=" * 50)

    from app.models.migrations import ensure_schema
    from app.runtime_queue_worker import start_queue_worker
    from app.runtime_scheduler import start_scheduler
    from app.utils.init import graceful_shutdown, reset_stuck_tasks
    from app.utils.init_data import ensure_seed_data
    from app.utils.task_runtime import ensure_runtime_states

    stop_event = Event()

    def request_shutdown(signum: int | None = None, frame: object | None = None) -> None:
        _ = signum, frame
        if not stop_event.is_set():
            logger.info("收到停止信号，准备退出...")
            stop_event.set()
            graceful_shutdown()

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)

    _run_timed_step(logger, "ensure_schema", ensure_schema)
    _run_timed_step(logger, "ensure_runtime_states", ensure_runtime_states)
    _run_timed_step(logger, "ensure_seed_data", ensure_seed_data)
    _run_timed_step(logger, "reset_stuck_tasks", reset_stuck_tasks)

    def refresh_cookie_background() -> None:
        try:
            from app.scheduler import check_and_refresh_cookie

            logger.info("[启动] 后台检查 Cookie 状态")
            start = time.perf_counter()
            new_cookie = check_and_refresh_cookie()
            elapsed_ms = (time.perf_counter() - start) * 1000
            if new_cookie:
                logger.info("[启动] Cookie 已刷新 (%.0f ms)", elapsed_ms)
            else:
                logger.info("[启动] Cookie 无需刷新或刷新失败 (%.0f ms)", elapsed_ms)
        except Exception as exc:
            logger.warning("Cookie 检查失败: %s", exc)

    if Config.BILIBILI_COOKIE:
        Thread(target=refresh_cookie_background, daemon=True, name="cookie-refresh").start()
    else:
        logger.info("[启动] 未配置 BILIBILI_COOKIE，跳过 Cookie 检查")

    scheduler_thread = Thread(
        target=start_scheduler,
        kwargs={"stop_event": stop_event},
        daemon=True,
        name="scheduler-runtime",
    )
    scheduler_thread.start()

    queue_thread = Thread(
        target=start_queue_worker,
        kwargs={"stop_event": stop_event},
        daemon=False,
        name="queue-runtime",
    )
    queue_thread.start()

    logger.info("[启动] 调度线程和队列线程已启动")

    try:
        while queue_thread.is_alive():
            queue_thread.join(timeout=1)
    except KeyboardInterrupt:
        request_shutdown()
    finally:
        stop_event.set()
        scheduler_thread.join(timeout=10)
        queue_thread.join(timeout=10)
        lock.release()


if __name__ == "__main__":
    main()
