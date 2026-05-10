from __future__ import annotations

import base64
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import hmac
import json
from threading import Lock
from time import monotonic
from typing import Any, Callable

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status

from admin_backend.crud import serialize_admin_user
from admin_backend.rbac import (
    ALL_PERMISSION_KEYS,
    build_menu_keys,
    generate_session_nonce,
    is_read_method,
    verify_password,
)
from admin_backend.schemas import AuthLoginRequest, AuthUserResponse
from app.models.database import AdminUser, create_session
from config import Config

AUTH_COOKIE_NAME = "bili_admin_auth"
AUTH_MAX_AGE_SECONDS = 60 * 60 * 24 * 365 * 100
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 5 * 60
LOGIN_RATE_LIMIT_MAX_FAILURES = 5
LOGIN_RATE_LIMIT_BLOCK_SECONDS = 15 * 60


@dataclass(slots=True)
class _ThrottleState:
    failures: deque[float] = field(default_factory=deque)
    blocked_until: float = 0.0


@dataclass(slots=True)
class AdminPrincipal:
    id: int
    username: str
    display_name: str | None
    is_super_admin: bool
    session_nonce: str
    roles: list[dict[str, Any]]
    permissions: tuple[str, ...]
    menu_keys: tuple[str, ...]
    last_login_at: datetime | None = None

    def has_permission(self, permission_key: str) -> bool:
        return self.is_super_admin or permission_key in self.permissions


_LOGIN_THROTTLE_LOCK = Lock()
_LOGIN_THROTTLE: dict[str, _ThrottleState] = {}

public_router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_secret() -> str:
    return str(getattr(Config, "ADMIN_AUTH_SECRET", "") or "").strip()


def _ensure_auth_configured() -> None:
    if not _auth_secret():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Admin auth is not configured")


def _cookie_secure(request: Request | None) -> bool:
    if request is None:
        return False
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    if forwarded_proto:
        return forwarded_proto == "https"
    return request.url.scheme == "https"


def _client_identifier(request: Request | None) -> str:
    if request is None or request.client is None:
        return "unknown"
    host = request.client.host or "unknown"
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return f"{host}|{forwarded}"
    return host


def _throttle_keys(request: Request | None, username: str) -> tuple[str, str, str]:
    client = _client_identifier(request)
    normalized_user = username.strip().lower() or "unknown"
    return client, normalized_user, f"{client}|{normalized_user}"


def _get_throttle_state(key: str) -> _ThrottleState:
    state = _LOGIN_THROTTLE.get(key)
    if state is None:
        state = _ThrottleState()
        _LOGIN_THROTTLE[key] = state
    return state


def _prune_throttle_state(state: _ThrottleState, now: float) -> None:
    while state.failures and now - state.failures[0] > LOGIN_RATE_LIMIT_WINDOW_SECONDS:
        state.failures.popleft()
    if state.blocked_until and state.blocked_until <= now and not state.failures:
        state.blocked_until = 0.0


def _check_login_throttle(request: Request | None, username: str) -> None:
    now = monotonic()
    keys = _throttle_keys(request, username)
    with _LOGIN_THROTTLE_LOCK:
        for key in keys:
            state = _get_throttle_state(key)
            _prune_throttle_state(state, now)
            if state.blocked_until > now:
                retry_after = max(1, int(state.blocked_until - now))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many login attempts. Try again later.",
                    headers={"Retry-After": str(retry_after)},
                )


def _record_login_failure(request: Request | None, username: str) -> None:
    now = monotonic()
    keys = _throttle_keys(request, username)
    with _LOGIN_THROTTLE_LOCK:
        for key in keys:
            state = _get_throttle_state(key)
            _prune_throttle_state(state, now)
            state.failures.append(now)
            if len(state.failures) >= LOGIN_RATE_LIMIT_MAX_FAILURES:
                state.blocked_until = now + LOGIN_RATE_LIMIT_BLOCK_SECONDS


def _clear_login_throttle(request: Request | None, username: str) -> None:
    keys = _throttle_keys(request, username)
    with _LOGIN_THROTTLE_LOCK:
        for key in keys:
            _LOGIN_THROTTLE.pop(key, None)


def _serialize_token_payload(principal: AdminPrincipal) -> str:
    payload = {
        "user_id": principal.id,
        "username": principal.username,
        "issued_at": int(datetime.utcnow().timestamp()),
        "session_nonce": principal.session_nonce,
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def _sign_token(principal: AdminPrincipal) -> str:
    secret = _auth_secret()
    if not secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Admin auth is not configured")
    payload = _serialize_token_payload(principal)
    signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    encoded_payload = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{encoded_payload}.{signature}"


def _verify_token(token: str) -> dict[str, Any] | None:
    try:
        encoded_payload, signature = token.split(".", 1)
    except ValueError:
        return None

    secret = _auth_secret()
    if not secret:
        return None

    try:
        padding = "=" * (-len(encoded_payload) % 4)
        payload = base64.urlsafe_b64decode((encoded_payload + padding).encode("ascii")).decode("utf-8")
    except Exception:
        return None

    expected_signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        data = json.loads(payload)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _extract_token(auth_cookie: str | None, authorization: str | None) -> str | None:
    if auth_cookie:
        return auth_cookie
    if authorization:
        prefix = "Bearer "
        if authorization.startswith(prefix):
            return authorization[len(prefix):].strip() or None
    return None


def _build_principal(user: AdminUser) -> AdminPrincipal:
    serialized = serialize_admin_user(user)
    permission_keys = set(serialized["permissions"])
    if user.is_super_admin:
        permission_keys = set(ALL_PERMISSION_KEYS)
    menu_keys = build_menu_keys(permission_keys)
    return AdminPrincipal(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        is_super_admin=bool(user.is_super_admin),
        session_nonce=user.session_nonce or "",
        roles=serialized["roles"],
        permissions=tuple(sorted(permission_keys)),
        menu_keys=tuple(menu_keys),
        last_login_at=user.last_login_at,
    )


def _load_principal_by_identity(user_id: int, username: str) -> AdminPrincipal:
    db = create_session()
    try:
        user = db.query(AdminUser).filter(AdminUser.id == user_id, AdminUser.username == username).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
        principal = _build_principal(user)
    finally:
        db.close()
    return principal


def _auth_response(principal: AdminPrincipal, token: str | None = None) -> AuthUserResponse:
    return AuthUserResponse(
        id=principal.id,
        username=principal.username,
        display_name=principal.display_name,
        is_super_admin=principal.is_super_admin,
        roles=principal.roles,
        permissions=list(principal.permissions),
        menu_keys=list(principal.menu_keys),
        token=token,
    )


def get_current_admin(
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> AdminPrincipal:
    _ensure_auth_configured()
    token = _extract_token(auth_cookie, authorization)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token_payload = _verify_token(token)
    if not token_payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    try:
        user_id = int(token_payload.get("user_id"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from None
    username = str(token_payload.get("username") or "").strip()
    session_nonce = str(token_payload.get("session_nonce") or "").strip()
    if not username or not session_nonce:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    principal = _load_principal_by_identity(user_id, username)
    if principal.session_nonce != session_nonce:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    return principal


def get_current_username(principal: AdminPrincipal = Depends(get_current_admin)) -> str:
    return principal.username


def require_admin_auth(_: AdminPrincipal = Depends(get_current_admin)) -> None:
    return None


def require_permission(permission_key: str) -> Callable[..., None]:
    def dependency(principal: AdminPrincipal = Depends(get_current_admin)) -> None:
        if not principal.has_permission(permission_key):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    return dependency


def _permission_for_group(group_key: str, method: str) -> str:
    action = "read" if is_read_method(method) else "write"
    return f"{group_key}.{action}"


def require_api_group(group_key: str) -> Callable[..., None]:
    def dependency(request: Request, principal: AdminPrincipal = Depends(get_current_admin)) -> None:
        permission_key = _permission_for_group(group_key, request.method)
        if not principal.has_permission(permission_key):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    return dependency


def _resolve_main_api_permission(path: str, method: str) -> str | None:
    normalized = path.rstrip("/") or "/"
    if normalized in {
        "/api/health",
        "/api/overview",
        "/api/tasks/overview",
        "/api/stats/tokens/daily",
        "/api/stats/tokens/models",
        "/api/stats/summary",
        "/api/monitor/overview",
        "/api/content-audit/overview",
    } or normalized.startswith("/api/stats/"):
        return "api.analytics.read"
    if normalized.startswith("/api/logs"):
        return "api.logs.read"
    if normalized.startswith("/api/tasks") or normalized.startswith("/api/manual-push"):
        return _permission_for_group("api.tasks", method)
    if normalized.startswith("/api/videos"):
        return _permission_for_group("api.videos", method)
    if normalized.startswith("/api/dynamics"):
        return _permission_for_group("api.dynamics", method)
    if normalized.startswith("/api/push-history"):
        return "api.push_history.read"
    if normalized.startswith("/api/push-targets"):
        return _permission_for_group("api.push_targets", method)
    if normalized.startswith("/api/subscriptions"):
        return _permission_for_group("api.subscriptions", method)
    if normalized.startswith("/api/podcast-subscriptions") or normalized.startswith("/api/podcast-episodes"):
        return _permission_for_group("api.podcasts", method)
    if normalized.startswith("/api/wewe-rss"):
        return _permission_for_group("api.wewe_rss", method)
    if normalized.startswith("/api/classification-rules"):
        return _permission_for_group("api.rules", method)
    if normalized.startswith("/api/folder-mappings"):
        return _permission_for_group("api.folder_mappings", method)
    if normalized.startswith("/api/configs/env"):
        return _permission_for_group("api.config", method)
    if normalized.startswith("/api/llm") or normalized.startswith("/api/llm-usage"):
        return _permission_for_group("api.llm", method)
    return None


def require_main_api_access(request: Request, principal: AdminPrincipal = Depends(get_current_admin)) -> None:
    permission_key = _resolve_main_api_permission(request.url.path, request.method)
    if permission_key is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission rule configured for endpoint")
    if not principal.has_permission(permission_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


@public_router.get("/me", response_model=AuthUserResponse)
def get_me(principal: AdminPrincipal = Depends(get_current_admin)) -> AuthUserResponse:
    return _auth_response(principal)


@public_router.post("/login", response_model=AuthUserResponse)
def login(payload: AuthLoginRequest, response: Response, request: Request) -> AuthUserResponse:
    _ensure_auth_configured()
    normalized_username = payload.username.strip()
    _check_login_throttle(request, normalized_username)

    db = create_session()
    try:
        user = db.query(AdminUser).filter(AdminUser.username == normalized_username).first()
        if not user or not verify_password(payload.password, user.password_hash):
            _record_login_failure(request, normalized_username)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
        if not user.is_active:
            _record_login_failure(request, normalized_username)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
        if not user.session_nonce:
            user.session_nonce = generate_session_nonce()
        user.last_login_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        principal = _build_principal(user)
    finally:
        db.close()

    _clear_login_throttle(request, normalized_username)
    token = _sign_token(principal)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=AUTH_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(request),
        path="/",
    )
    return _auth_response(principal, token=token)


@public_router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    return {"success": True}
