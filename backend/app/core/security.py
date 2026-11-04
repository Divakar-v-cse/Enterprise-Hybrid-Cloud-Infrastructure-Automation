"""Password hashing and JWT issuing/verification.

Deliberately implemented on the standard library only (``hashlib``/``hmac``)
so the control plane has no binary wheel dependencies and the security
primitives stay auditable. HS256 is symmetric: in production the signing key
is sourced from AWS Secrets Manager via the task definition / GitHub OIDC.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.core.errors import AuthenticationError, ValidationError

_PBKDF2_ITERATIONS = 260_000
_PBKDF2_PREFIX = "pbkdf2_sha256"
_PASSWORD_MIN_LENGTH = 10


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
def hash_password(password: str, *, iterations: int = _PBKDF2_ITERATIONS) -> str:
    """Return ``pbkdf2_sha256$iterations$salt$digest`` using a random 16-byte salt."""
    if not password:
        raise ValidationError("Password must not be empty.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "$".join(
        (
            _PBKDF2_PREFIX,
            str(iterations),
            _b64e(salt),
            _b64e(digest),
        )
    )


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time verification of a stored password hash."""
    try:
        prefix, iterations, salt_b64, digest_b64 = encoded.split("$")
        if prefix != _PBKDF2_PREFIX:
            return False
        salt = _b64d(salt_b64)
        expected = _b64d(digest_b64)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, expected)


def password_needs_rehash(encoded: str) -> bool:
    try:
        prefix, iterations, _, _ = encoded.split("$")
    except ValueError:
        return True
    return prefix != _PBKDF2_PREFIX or int(iterations) < _PBKDF2_ITERATIONS


def validate_password_strength(password: str) -> None:
    """Enforce a pragmatic password policy for locally managed accounts."""
    problems: list[str] = []
    if len(password) < _PASSWORD_MIN_LENGTH:
        problems.append(f"be at least {_PASSWORD_MIN_LENGTH} characters long")
    if not re.search(r"[A-Z]", password):
        problems.append("contain an uppercase letter")
    if not re.search(r"[a-z]", password):
        problems.append("contain a lowercase letter")
    if not re.search(r"\d", password):
        problems.append("contain a digit")
    if not re.search(r"[^A-Za-z0-9]", password):
        problems.append("contain a symbol")
    if problems:
        raise ValidationError("Password must " + ", ".join(problems) + ".")


# ---------------------------------------------------------------------------
# JWT (HS256)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TokenClaims:
    subject: str
    email: str
    role: str
    token_type: str
    issued_at: int
    expires_at: int
    token_id: str
    issuer: str
    audience: str

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= int(time.time())


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(signing_input: bytes, secret: str) -> bytes:
    return hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()


def encode_token(
    *,
    subject: str,
    email: str,
    role: str,
    token_type: str,
    settings: Settings,
    ttl_seconds: int | None = None,
) -> str:
    now = int(time.time())
    if ttl_seconds is None:
        ttl_seconds = (
            settings.access_token_ttl_minutes * 60
            if token_type == "access"
            else settings.refresh_token_ttl_days * 86_400
        )
    header = {"alg": settings.jwt_algorithm, "typ": "JWT"}
    payload: dict[str, Any] = {
        "sub": subject,
        "email": email,
        "role": role,
        "type": token_type,
        "iat": now,
        "nbf": now,
        "exp": now + ttl_seconds,
        "jti": uuid.uuid4().hex,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    segments = [
        _b64e(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
    ]
    signing_input = ".".join(segments).encode("ascii")
    segments.append(_b64e(_sign(signing_input, settings.secret_key)))
    return ".".join(segments)


def decode_token(token: str, *, settings: Settings, expected_type: str | None = None) -> TokenClaims:
    """Verify signature, claims and token type. Raises ``AuthenticationError``."""
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError as exc:
        raise AuthenticationError("Malformed token.") from exc

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    try:
        provided_signature = _b64d(signature_b64)
    except (ValueError, TypeError) as exc:
        raise AuthenticationError("Malformed token signature.") from exc

    if not hmac.compare_digest(provided_signature, _sign(signing_input, settings.secret_key)):
        raise AuthenticationError("Token signature is invalid.")

    try:
        header = json.loads(_b64d(header_b64))
        payload = json.loads(_b64d(payload_b64))
    except (ValueError, TypeError) as exc:
        raise AuthenticationError("Token payload is not valid JSON.") from exc

    if header.get("alg") != settings.jwt_algorithm:
        raise AuthenticationError("Unsupported token algorithm.")
    if payload.get("iss") != settings.jwt_issuer:
        raise AuthenticationError("Token issuer mismatch.")
    if payload.get("aud") != settings.jwt_audience:
        raise AuthenticationError("Token audience mismatch.")
    if int(payload.get("nbf", 0)) > int(time.time()) + 30:
        raise AuthenticationError("Token is not yet valid.")
    if int(payload.get("exp", 0)) <= int(time.time()):
        raise AuthenticationError("Token has expired.")
    if expected_type and payload.get("type") != expected_type:
        raise AuthenticationError(f"Expected a {expected_type} token.")

    return TokenClaims(
        subject=str(payload.get("sub", "")),
        email=str(payload.get("email", "")),
        role=str(payload.get("role", "")),
        token_type=str(payload.get("type", "")),
        issued_at=int(payload.get("iat", 0)),
        expires_at=int(payload.get("exp", 0)),
        token_id=str(payload.get("jti", "")),
        issuer=str(payload.get("iss", "")),
        audience=str(payload.get("aud", "")),
    )
