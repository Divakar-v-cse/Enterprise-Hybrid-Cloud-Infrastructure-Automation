"""Authentication endpoints: login, refresh, logout, profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import get_app_settings, get_current_user, get_store
from app.core.config import Settings
from app.core.errors import AuthenticationError, RateLimited
from app.core.middleware import get_client_ip
from app.core.rbac import Permission, permissions_for
from app.core.security import (
    decode_token,
    encode_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.db.store import Store
from app.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    TokenPair,
    User,
    UserPublic,
    utcnow,
)
from app.services import audit

router = APIRouter(prefix="/auth", tags=["auth"])


def _public_user(user: User) -> UserPublic:
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


def _issue_tokens(user: User, settings: Settings) -> TokenPair:
    return TokenPair(
        access_token=encode_token(
            subject=user.id,
            email=user.email,
            role=str(user.role),
            token_type="access",
            settings=settings,
        ),
        refresh_token=encode_token(
            subject=user.id,
            email=user.email,
            role=str(user.role),
            token_type="refresh",
            settings=settings,
        ),
        expires_in=settings.access_token_ttl_minutes * 60,
    )


@router.post("/login", response_model=LoginResponse, summary="Exchange credentials for tokens")
def login(
    payload: LoginRequest,
    request: Request,
    store: Store = Depends(get_store),
    settings: Settings = Depends(get_app_settings),
) -> LoginResponse:
    client_ip = get_client_ip(request)
    throttle_key = f"{payload.email.lower()}|{client_ip}"
    if store.login_locked(throttle_key):
        audit.record(
            store,
            actor=None,
            action="auth.login",
            target="control-plane",
            outcome="blocked",
            source_ip=client_ip,
            details={"email": payload.email, "reason": "too_many_attempts"},
        )
        raise RateLimited(
            "Too many failed sign-in attempts. Try again later.",
            headers={"Retry-After": str(settings.login_lockout_seconds)},
        )

    user = store.get_user_by_email(payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        store.register_failed_login(throttle_key)
        audit.record(
            store,
            actor=None,
            action="auth.login",
            target="control-plane",
            outcome="failure",
            source_ip=client_ip,
            details={"email": payload.email, "reason": "invalid_credentials"},
        )
        raise AuthenticationError("Invalid email or password.")

    if not user.is_active:
        audit.record(
            store,
            actor=user,
            action="auth.login",
            target="control-plane",
            outcome="failure",
            source_ip=client_ip,
            details={"reason": "inactive_account"},
        )
        raise AuthenticationError("This account is disabled.")

    if password_needs_rehash(user.password_hash):
        store.add_user(user.model_copy(update={"password_hash": hash_password(payload.password)}))

    store.clear_login_attempts(throttle_key)
    store.touch_login(user.id)
    tokens = _issue_tokens(user, settings)
    audit.record(
        store,
        actor=user,
        action="auth.login",
        target="control-plane",
        source_ip=client_ip,
        details={"role": str(user.role)},
    )
    refreshed = store.get_user(user.id) or user
    return LoginResponse(**tokens.model_dump(), user=_public_user(refreshed))


@router.post("/refresh", response_model=TokenPair, summary="Rotate an expiring session")
def refresh(
    payload: RefreshRequest,
    request: Request,
    store: Store = Depends(get_store),
    settings: Settings = Depends(get_app_settings),
) -> TokenPair:
    claims = decode_token(payload.refresh_token, settings=settings, expected_type="refresh")
    if store.is_revoked(claims.token_id):
        raise AuthenticationError("Refresh token has already been used.")

    user = store.get_user(claims.subject)
    if user is None or not user.is_active or user.role != claims.role:
        raise AuthenticationError("Account is no longer eligible for refresh.")

    # Rotation: the presented refresh token is single-use.
    store.revoke_token(claims.token_id, float(claims.expires_at))
    tokens = _issue_tokens(user, settings)
    audit.record(
        store,
        actor=user,
        action="auth.refresh",
        target="control-plane",
        source_ip=get_client_ip(request),
    )
    return tokens


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Revoke current session",
)
def logout(
    request: Request,
    user: User = Depends(get_current_user),
    store: Store = Depends(get_store),
    settings: Settings = Depends(get_app_settings),
):
    authorization = request.headers.get("authorization", "")
    token = authorization.split(" ", 1)[1] if " " in authorization else ""
    if token:
        claims = decode_token(token, settings=settings, expected_type="access")
        store.revoke_token(claims.token_id, float(claims.expires_at))
    audit.record(
        store,
        actor=user,
        action="auth.logout",
        target="control-plane",
        source_ip=get_client_ip(request),
    )


@router.get("/me", response_model=UserPublic, summary="Current identity and permissions")
def me(user: User = Depends(get_current_user)) -> UserPublic:
    return _public_user(user)


@router.get(
    "/permissions",
    response_model=list[str],
    summary="Permission catalogue for the current role",
)
def my_permissions(
    user: User = Depends(get_current_user),
) -> list[str]:
    _ = Permission.INFRA_READ  # keep the import meaningful for docs tooling
    return sorted(p.value for p in permissions_for(user.role))


__all__ = ["router", "utcnow"]
