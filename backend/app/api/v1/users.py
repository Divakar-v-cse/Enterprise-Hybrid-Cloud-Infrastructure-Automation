"""User and role administration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import get_store, require_permissions
from app.core.errors import ConflictError, NotFoundError, PermissionDenied
from app.core.rbac import Permission, Role, permissions_for
from app.core.security import hash_password, validate_password_strength
from app.db.store import Store, new_id
from app.schemas import RoleUpdateRequest, User, UserCreateRequest, UserPublic

router = APIRouter(prefix="/users", tags=["users"])


def _public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        mfa_enabled=user.mfa_enabled,
        last_login_at=user.last_login_at,
        permissions=sorted(p.value for p in permissions_for(user.role)),
    )


def _active_admins(store: Store) -> list[User]:
    return [u for u in store.list_users() if u.role == Role.ADMIN and u.is_active]


@router.get("", response_model=list[UserPublic], summary="List accounts")
def list_users(
    _: User = Depends(require_permissions(Permission.USER_READ)),
    store: Store = Depends(get_store),
) -> list[UserPublic]:
    return [_public(user) for user in store.list_users()]


@router.post(
    "",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Provision an account",
)
def create_user(
    payload: UserCreateRequest,
    actor: User = Depends(require_permissions(Permission.USER_MANAGE)),
    store: Store = Depends(get_store),
) -> UserPublic:
    if store.get_user_by_email(payload.email) is not None:
        raise ConflictError("An account with that email already exists.")
    if payload.role == Role.ADMIN and actor.role != Role.ADMIN:
        raise PermissionDenied("Only an administrator can grant the admin role.")
    validate_password_strength(payload.password)
    user = User(
        id=new_id("usr"),
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role,
        password_hash=hash_password(payload.password),
        mfa_enabled=payload.mfa_enabled,
    )
    store.add_user(user)
    return _public(user)


@router.patch("/{user_id}/role", response_model=UserPublic, summary="Change a role")
def update_role(
    user_id: str,
    payload: RoleUpdateRequest,
    actor: User = Depends(require_permissions(Permission.USER_MANAGE)),
    store: Store = Depends(get_store),
) -> UserPublic:
    target = store.get_user(user_id)
    if target is None:
        raise NotFoundError("User not found.")
    if actor.id == user_id and payload.role != target.role:
        raise PermissionDenied("You cannot change your own role.")

    if target.role == Role.ADMIN and payload.role != Role.ADMIN:
        if len(_active_admins(store)) <= 1:
            raise ConflictError("At least one active administrator must remain.")

    updated = store.update_role(user_id, payload.role)
    if updated is None:
        raise NotFoundError("User not found.")
    return _public(updated)


@router.post("/{user_id}/deactivate", response_model=UserPublic, summary="Disable an account")
def deactivate_user(
    user_id: str,
    actor: User = Depends(require_permissions(Permission.USER_MANAGE)),
    store: Store = Depends(get_store),
) -> UserPublic:
    target = store.get_user(user_id)
    if target is None:
        raise NotFoundError("User not found.")
    if target.id == actor.id:
        raise PermissionDenied("You cannot deactivate your own account.")
    if target.role == Role.ADMIN and len(_active_admins(store)) <= 1:
        raise ConflictError("At least one active administrator must remain.")
    updated = store.add_user(target.model_copy(update={"is_active": False}))
    return _public(updated)
