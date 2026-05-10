from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from admin_backend.auth import AdminPrincipal, get_current_admin
from admin_backend.crud import serialize_admin_permission, serialize_admin_role, serialize_admin_user
from admin_backend.deps import get_session
from admin_backend.rbac import ALL_PERMISSION_KEYS, generate_session_nonce, hash_password
from admin_backend.schemas import (
    AdminRoleCreateRequest,
    AdminRoleUpdateRequest,
    AdminUserCreateRequest,
    AdminUserResetPasswordRequest,
    AdminUserUpdateRequest,
)
from app.models.database import AdminPermission, AdminRole, AdminUser

router = APIRouter(prefix="/rbac", tags=["rbac"])


def _normalize_permission_keys(keys: list[str]) -> list[str]:
    normalized: list[str] = []
    allowed = set(ALL_PERMISSION_KEYS)
    for key in keys:
        value = str(key or "").strip()
        if not value:
            continue
        if value not in allowed:
            raise HTTPException(status_code=400, detail=f"Unknown permission: {value}")
        if value not in normalized:
            normalized.append(value)
    return normalized


def _load_permissions(db: Session, permission_keys: list[str]) -> list[AdminPermission]:
    if not permission_keys:
        return []
    rows = db.query(AdminPermission).filter(AdminPermission.key.in_(permission_keys)).all()
    found = {row.key for row in rows}
    missing = [key for key in permission_keys if key not in found]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing permissions: {', '.join(missing)}")
    order = {key: index for index, key in enumerate(permission_keys)}
    return sorted(rows, key=lambda row: order[row.key])


def _load_roles(db: Session, role_ids: list[int]) -> list[AdminRole]:
    if not role_ids:
        return []
    rows = (
        db.query(AdminRole)
        .options(joinedload(AdminRole.permissions), joinedload(AdminRole.users))
        .filter(AdminRole.id.in_(role_ids))
        .all()
    )
    found = {row.id for row in rows}
    missing = [str(role_id) for role_id in role_ids if role_id not in found]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing roles: {', '.join(missing)}")
    order = {role_id: index for index, role_id in enumerate(role_ids)}
    return sorted(rows, key=lambda row: order[row.id])


def _count_other_active_super_admins(db: Session, user_id: int) -> int:
    return (
        db.query(AdminUser)
        .filter(AdminUser.id != user_id, AdminUser.is_super_admin.is_(True), AdminUser.is_active.is_(True))
        .count()
    )


def _resolve_super_admin_flag(role_ids: list[int], roles: list[AdminRole], explicit_flag: bool | None, current_flag: bool) -> bool:
    has_super_admin_role = any(role.code == "super_admin" for role in roles)
    if explicit_flag is None:
        return current_flag or has_super_admin_role
    return bool(explicit_flag or has_super_admin_role)


@router.get("/permissions")
def list_permissions(db: Session = Depends(get_session)):
    rows = db.query(AdminPermission).order_by(AdminPermission.kind.asc(), AdminPermission.group_name.asc(), AdminPermission.key.asc()).all()
    return [serialize_admin_permission(row) for row in rows]


@router.get("/roles")
def list_roles(db: Session = Depends(get_session)):
    rows = (
        db.query(AdminRole)
        .options(joinedload(AdminRole.permissions), joinedload(AdminRole.users))
        .order_by(AdminRole.is_system.desc(), AdminRole.code.asc())
        .all()
    )
    return [serialize_admin_role(row) for row in rows]


@router.post("/roles")
def create_role(payload: AdminRoleCreateRequest, db: Session = Depends(get_session)):
    code = payload.code.strip().lower()
    if not code:
        raise HTTPException(status_code=400, detail="Role code is required")
    existing = db.query(AdminRole).filter(AdminRole.code == code).first()
    if existing:
        raise HTTPException(status_code=409, detail="Role code already exists")

    permission_keys = _normalize_permission_keys(payload.permission_keys)
    role = AdminRole(
        code=code,
        name=payload.name.strip() or code,
        description=(payload.description or "").strip() or None,
        is_active=payload.is_active,
        is_system=False,
    )
    role.permissions = _load_permissions(db, permission_keys)
    db.add(role)
    db.commit()
    db.refresh(role)
    return serialize_admin_role(role)


@router.put("/roles/{role_id}")
def update_role(role_id: int, payload: AdminRoleUpdateRequest, db: Session = Depends(get_session)):
    role = (
        db.query(AdminRole)
        .options(joinedload(AdminRole.permissions), joinedload(AdminRole.users))
        .filter(AdminRole.id == role_id)
        .first()
    )
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.code == "super_admin" and payload.is_active is False:
        raise HTTPException(status_code=400, detail="super_admin role cannot be disabled")

    if payload.name is not None:
        role.name = payload.name.strip() or role.name
    if payload.description is not None:
        role.description = payload.description.strip() or None
    if payload.is_active is not None:
        role.is_active = bool(payload.is_active)
    if payload.permission_keys is not None:
        permission_keys = _normalize_permission_keys(payload.permission_keys)
        role.permissions = _load_permissions(db, permission_keys)

    db.commit()
    db.refresh(role)
    return serialize_admin_role(role)


@router.get("/users")
def list_users(db: Session = Depends(get_session)):
    rows = (
        db.query(AdminUser)
        .options(joinedload(AdminUser.roles).joinedload(AdminRole.permissions))
        .order_by(AdminUser.created_at.desc(), AdminUser.id.desc())
        .all()
    )
    return [serialize_admin_user(row) for row in rows]


@router.post("/users")
def create_user(payload: AdminUserCreateRequest, db: Session = Depends(get_session)):
    username = payload.username.strip()
    password = payload.password.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    if not password:
        raise HTTPException(status_code=400, detail="Password is required")
    if db.query(AdminUser).filter(AdminUser.username == username).first():
        raise HTTPException(status_code=409, detail="Username already exists")

    roles = _load_roles(db, payload.role_ids)
    user = AdminUser(
        username=username,
        password_hash=hash_password(password),
        display_name=(payload.display_name or "").strip() or None,
        is_active=payload.is_active,
        is_super_admin=_resolve_super_admin_flag(payload.role_ids, roles, payload.is_super_admin, False),
    )
    user.session_nonce = generate_session_nonce()
    user.roles = roles
    db.add(user)
    db.commit()
    db.refresh(user)
    return serialize_admin_user(user)


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    principal: AdminPrincipal = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    user = (
        db.query(AdminUser)
        .options(joinedload(AdminUser.roles).joinedload(AdminRole.permissions))
        .filter(AdminUser.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    roles = user.roles
    if payload.role_ids is not None:
        roles = _load_roles(db, payload.role_ids)
    new_is_super_admin = _resolve_super_admin_flag(payload.role_ids or [role.id for role in roles], roles, payload.is_super_admin, user.is_super_admin)
    new_is_active = user.is_active if payload.is_active is None else bool(payload.is_active)

    if user.is_super_admin and (not new_is_active or not new_is_super_admin):
        if _count_other_active_super_admins(db, user.id) == 0:
            raise HTTPException(status_code=400, detail="Cannot disable or demote the last active super admin")

    if payload.display_name is not None:
        user.display_name = payload.display_name.strip() or None
    if payload.is_active is not None:
        user.is_active = new_is_active
    user.is_super_admin = new_is_super_admin
    if payload.role_ids is not None:
        user.roles = roles
    if principal.id == user.id and not user.is_active:
        raise HTTPException(status_code=400, detail="You cannot disable the current account")

    db.commit()
    db.refresh(user)
    return serialize_admin_user(user)


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    payload: AdminUserResetPasswordRequest,
    db: Session = Depends(get_session),
):
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    password = payload.password.strip()
    if not password:
        raise HTTPException(status_code=400, detail="Password is required")
    user.password_hash = hash_password(password)
    user.session_nonce = generate_session_nonce()
    db.commit()
    db.refresh(user)
    return {"success": True}
