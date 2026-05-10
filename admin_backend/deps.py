from __future__ import annotations

from collections.abc import Generator

from app.models.database import create_session

ADMIN_SQLITE_TIMEOUT_SECONDS = 3.0
ADMIN_SQLITE_BUSY_TIMEOUT_MS = 3000
ADMIN_POOL_TIMEOUT_SECONDS = 3.0


def get_session() -> Generator:
    db = create_session(
        sqlite_timeout_seconds=ADMIN_SQLITE_TIMEOUT_SECONDS,
        pool_timeout_seconds=ADMIN_POOL_TIMEOUT_SECONDS,
        sqlite_busy_timeout_ms=ADMIN_SQLITE_BUSY_TIMEOUT_MS,
    )
    try:
        yield db
    finally:
        db.close()
