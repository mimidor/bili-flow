from __future__ import annotations

from typing import Any

from sqlalchemy.exc import OperationalError

from app.models.database import RuntimeConfig, SessionLocal, create_session

_RUNTIME_CONFIG_OVERRIDES_LOADED = False


def _stringify_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _commit_with_retry(db) -> None:
    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise


def project_database_url_from_env() -> None:
    """Project the active DATABASE_URL from source-specific settings in env."""
    import os

    source = (os.getenv("DATABASE_SOURCE") or "").strip().lower()
    sqlite_url = (os.getenv("SQLITE_DATABASE_URL") or "").strip()
    postgres_url = (os.getenv("POSTGRESQL_DATABASE_URL") or "").strip()
    active_url = (os.getenv("DATABASE_URL") or "").strip()

    if source == "postgresql":
        projected = postgres_url or active_url or sqlite_url
    elif source == "sqlite":
        projected = sqlite_url or active_url or postgres_url
    else:
        projected = active_url or sqlite_url or postgres_url

    if projected:
        os.environ["DATABASE_URL"] = projected


def load_runtime_config_overrides() -> None:
    """Load runtime config table values into process environment."""
    global _RUNTIME_CONFIG_OVERRIDES_LOADED
    db = SessionLocal()
    try:
        rows = db.query(RuntimeConfig).all()
        for row in rows:
            if row.key:
                # Table values win over .env and existing process env.
                import os

                os.environ[row.key] = row.value or ""
        project_database_url_from_env()
        _RUNTIME_CONFIG_OVERRIDES_LOADED = True
    except Exception:
        db.rollback()
        _RUNTIME_CONFIG_OVERRIDES_LOADED = False
    finally:
        db.close()


def seed_runtime_config_rows(defaults: dict[str, Any], *, database_url: str | None = None) -> None:
    """Backfill missing runtime config rows from .env-derived defaults."""
    if not defaults:
        return

    db = create_session(database_url) if database_url else SessionLocal()
    try:
        existing_keys = {
            row[0]
            for row in db.query(RuntimeConfig.key).filter(RuntimeConfig.key.in_(list(defaults.keys()))).all()
        }
        changed = False
        for key, value in defaults.items():
            if key in existing_keys:
                continue
            db.add(RuntimeConfig(key=key, value=_stringify_value(value)))
            changed = True
        if changed:
            _commit_with_retry(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def upsert_runtime_config_values(updates: dict[str, Any], *, database_url: str | None = None) -> None:
    if not updates:
        return

    db = create_session(database_url) if database_url else SessionLocal()
    try:
        for key, value in updates.items():
            row = db.query(RuntimeConfig).filter(RuntimeConfig.key == key).first()
            rendered = _stringify_value(value)
            if row:
                row.value = rendered
            else:
                db.add(RuntimeConfig(key=key, value=rendered))
        _commit_with_retry(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def runtime_config_overrides_loaded() -> bool:
    return _RUNTIME_CONFIG_OVERRIDES_LOADED
