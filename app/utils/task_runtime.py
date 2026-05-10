from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from sqlalchemy.exc import OperationalError

from app.models.database import TaskRuntimeState, get_db

SCHEDULER_COMPONENT = "scheduler"
QUEUE_WORKER_COMPONENT = "queue_worker"

_RUNTIME_TOUCH_MIN_INTERVAL_SECONDS = 60.0
_LAST_RUNTIME_TOUCH: dict[str, tuple[float, str | None]] = {}

COMPONENT_LABELS = {
    SCHEDULER_COMPONENT: "调度器",
    QUEUE_WORKER_COMPONENT: "队列线程",
}


def _now() -> datetime:
    return datetime.utcnow()


def _commit_with_retry(db, *, retries: int = 5, base_delay: float = 0.2) -> None:
    for attempt in range(retries):
        try:
            db.commit()
            return
        except OperationalError as exc:
            db.rollback()
            if "database is locked" not in str(exc).lower() or attempt >= retries - 1:
                raise
            time.sleep(base_delay * (attempt + 1))


def _should_throttle_runtime_touch(component: str, status: str | None, heartbeat: bool, activity: bool) -> bool:
    if not (heartbeat or activity):
        return False
    if status is None:
        return False
    last = _LAST_RUNTIME_TOUCH.get(component)
    if not last:
        return False
    last_at, last_status = last
    if last_status != status:
        return False
    return (time.monotonic() - last_at) < _RUNTIME_TOUCH_MIN_INTERVAL_SECONDS


def ensure_runtime_states() -> None:
    """Ensure the runtime control rows exist."""
    db = get_db()
    try:
        for component in (SCHEDULER_COMPONENT, QUEUE_WORKER_COMPONENT):
            get_or_create_runtime_state(db, component)
        _commit_with_retry(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_or_create_runtime_state(db, component: str) -> TaskRuntimeState:
    row = db.query(TaskRuntimeState).filter(TaskRuntimeState.component == component).first()
    if row:
        return row

    row = TaskRuntimeState(
        component=component,
        is_paused=False,
        status="running",
        last_message="等待心跳",
    )
    db.add(row)
    db.flush()
    return row


def serialize_runtime_state(row: TaskRuntimeState) -> dict[str, Any]:
    return {
        "component": row.component,
        "label": COMPONENT_LABELS.get(row.component, row.component),
        "is_paused": bool(row.is_paused),
        "status": row.status,
        "last_heartbeat_at": row.last_heartbeat_at.isoformat() if row.last_heartbeat_at else None,
        "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
        "last_message": row.last_message,
        "last_error": row.last_error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def touch_runtime_state(
    db,
    component: str,
    *,
    message: str | None = None,
    error: str | None = None,
    status: str | None = None,
    heartbeat: bool = True,
    activity: bool = False,
) -> TaskRuntimeState:
    row = get_or_create_runtime_state(db, component)
    now = _now()

    resolved_status = status if status is not None else ("paused" if row.is_paused else "running")
    if _should_throttle_runtime_touch(component, resolved_status, heartbeat, activity):
        return row

    if heartbeat:
        row.last_heartbeat_at = now
    if activity:
        row.last_run_at = now
    row.status = resolved_status

    if message is not None:
        row.last_message = message
    if error is not None:
        row.last_error = error
    elif resolved_status in {"running", "paused"}:
        row.last_error = None

    _commit_with_retry(db)
    _LAST_RUNTIME_TOUCH[component] = (time.monotonic(), row.status)
    return row


def set_runtime_pause(db, component: str, paused: bool, message: str | None = None) -> TaskRuntimeState:
    row = get_or_create_runtime_state(db, component)
    row.is_paused = paused
    row.status = "paused" if paused else "running"
    row.last_message = message or ("已暂停" if paused else "已恢复")
    row.last_heartbeat_at = _now()
    _commit_with_retry(db)
    _LAST_RUNTIME_TOUCH[component] = (time.monotonic(), row.status)
    return row
