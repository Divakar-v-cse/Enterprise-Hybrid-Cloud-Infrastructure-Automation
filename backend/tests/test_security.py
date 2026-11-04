"""Security primitives, configuration hardening and error contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import INSECURE_DEFAULT_SECRET, Settings
from app.core.errors import AuthenticationError
from app.core.errors import ValidationError as AppValidationError
from app.core.security import (
    decode_token,
    encode_token,
    hash_password,
    password_needs_rehash,
    validate_password_strength,
    verify_password,
)


def test_password_hash_roundtrip_and_salting():
    first = hash_password("Str0ng#Passw0rd", iterations=1_000)
    second = hash_password("Str0ng#Passw0rd", iterations=1_000)
    assert first != second, "each hash must use a unique salt"
    assert first.startswith("pbkdf2_sha256$")
    assert verify_password("Str0ng#Passw0rd", first) is True
    assert verify_password("wrong", first) is False


def test_corrupt_hash_is_rejected_not_crashing():
    assert verify_password("anything", "not-a-valid-hash") is False


def test_password_rehash_detection():
    weak = hash_password("Str0ng#Passw0rd", iterations=1_000)
    assert password_needs_rehash(weak) is True
    assert password_needs_rehash("bcrypt$12$whatever") is True
    assert password_needs_rehash(hash_password("Str0ng#Passw0rd")) is False


@pytest.mark.parametrize("password", ["short", "alllowercase", "NOLOWERCASE1!", "NoDigits!!", "NoSymbols12"])
def test_weak_passwords_rejected(password):
    with pytest.raises(AppValidationError):
        validate_password_strength(password)


def test_strong_password_accepted():
    validate_password_strength("Str0ng#Passw0rd")


def test_token_roundtrip(settings):
    token = encode_token(
        subject="usr-1", email="a@b.io", role="viewer", token_type="access", settings=settings
    )
    claims = decode_token(token, settings=settings, expected_type="access")
    assert claims.subject == "usr-1"
    assert claims.role == "viewer"
    assert claims.is_expired is False
    assert claims.token_id


def test_token_rejected_for_wrong_type(settings):
    token = encode_token(
        subject="usr-1", email="a@b.io", role="viewer", token_type="access", settings=settings
    )
    with pytest.raises(AuthenticationError):
        decode_token(token, settings=settings, expected_type="refresh")


def test_token_signed_with_other_key_is_rejected(settings):
    other = settings.model_copy(update={"secret_key": "a-completely-different-secret-key-1234"})
    token = encode_token(subject="usr-1", email="a@b.io", role="viewer", token_type="access", settings=other)
    with pytest.raises(AuthenticationError):
        decode_token(token, settings=settings, expected_type="access")


def test_malformed_token_is_rejected(settings):
    with pytest.raises(AuthenticationError):
        decode_token("not.a.jwt", settings=settings)


def test_production_requires_hardened_settings():
    with pytest.raises(ValidationError):
        Settings(environment="prod", secret_key=INSECURE_DEFAULT_SECRET, seed_demo_data=False)
    with pytest.raises(ValidationError):
        Settings(environment="prod", secret_key="x" * 40, seed_demo_data=True)

    hardened = Settings(
        environment="prod", secret_key="x" * 40, seed_demo_data=False, cors_origins=["https://hccp.example.com"]
    )
    assert hardened.is_production is True


def test_cors_origins_accept_comma_separated_list():
    config = Settings(cors_origins="https://a.example.com,https://b.example.com")
    assert config.cors_origins == ["https://a.example.com", "https://b.example.com"]


def test_validation_error_envelope(client, operator_headers):
    response = client.post(
        "/api/v1/deployments", json={"environment": "dev"}, headers=operator_headers
    )
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert body["request_id"]
    assert isinstance(body["details"]["fields"], list)
    assert body["details"]["fields"]


def test_unknown_route_uses_error_envelope(client):
    response = client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_cors_preflight_allows_configured_origin(client):
    response = client.options(
        "/api/v1/resources",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_disallowed_origin_gets_no_cors_header(client):
    response = client.get("/healthz", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in response.headers
