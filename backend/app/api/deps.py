"""Shared FastAPI dependencies: auth, RBAC, store and provider access."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings
from app.core.errors import AuthenticationError, PermissionDenied
from app.core.logging import user_var
from app.core.rbac import Permission, permissions_for
from app.core.security import decode_token
from app.db.store import Store
from app.providers.base import CloudProvider
from app.schemas import User

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="JWT access token issued by POST /api/v1/auth/login",
)


def get_store(request: Request) -> Store:
    return request.app.state.store


def get_provider(request: Request) -> CloudProvider:
    return request.app.state.provider


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_app_settings),
    store: Store = Depends(get_store),
) -> User:
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Missing bearer token.")

    claims = decode_token(credentials.credentials, settings=settings, expected_type="access")
    if store.is_revoked(claims.token_id):
        raise AuthenticationError("Token has been revoked.")

    user = store.get_user(claims.subject)
    if user is None or not user.is_active:
        raise AuthenticationError("Account is inactive or no longer exists.")
    if user.role != claims.role:
        # A role change invalidates outstanding tokens immediately.
        raise AuthenticationError("Token claims are stale; sign in again.")

    request.state.user_id = user.id
    request.state.user_email = user.email
    user_var.set(user.email)
    return user


def require_permissions(*required: Permission) -> Callable[..., User]:
    """Dependency factory enforcing that the caller holds every permission."""

    def _dependency(user: User = Depends(get_current_user)) -> User:
        granted = permissions_for(user.role)
        missing = [permission.value for permission in required if permission not in granted]
        if missing:
            raise PermissionDenied(
                "You do not have permission to perform this action.",
                details={"missing_permissions": missing, "role": str(user.role)},
            )
        return user

    return _dependency
