"""Authentication, token lifecycle and throttling."""

from __future__ import annotations

from conftest import DEMO_PASSWORDS

from app.core.security import encode_token


def test_login_returns_tokens_and_profile(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@hccp.io", "password": DEMO_PASSWORDS["admin@hccp.io"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    assert body["access_token"] != body["refresh_token"]
    assert body["user"]["email"] == "admin@hccp.io"
    assert body["user"]["role"] == "admin"
    assert "infrastructure:read" in body["user"]["permissions"]
    assert "user:manage" in body["user"]["permissions"]
    assert "password_hash" not in body["user"]


def test_login_rejects_wrong_password(client):
    response = client.post(
        "/api/v1/auth/login", json={"email": "admin@hccp.io", "password": "definitely-wrong"}
    )
    assert response.status_code == 401
    error = response.json()["error"]
    assert error["code"] == "authentication_failed"
    assert error["request_id"]
    assert "request_id" not in error["details"]


def test_login_rejects_unknown_account(client):
    response = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "Whatever#123"}
    )
    assert response.status_code == 401


def test_missing_bearer_token_is_401(client):
    response = client.get("/api/v1/resources")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_failed"


def test_tampered_token_is_rejected(client):
    session = client.post(
        "/api/v1/auth/login",
        json={"email": "viewer@hccp.io", "password": DEMO_PASSWORDS["viewer@hccp.io"]},
    ).json()
    token = session["access_token"]
    header, payload, signature = token.split(".")
    forged = f"{header}.{payload}.{signature[:-4]}aaaa"
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_expired_access_token_is_rejected(client, settings):
    expired = encode_token(
        subject="usr-does-not-matter",
        email="viewer@hccp.io",
        role="viewer",
        token_type="access",
        settings=settings,
        ttl_seconds=-30,
    )
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401
    assert "expired" in response.json()["error"]["message"].lower()


def test_refresh_token_rotation(client):
    session = client.post(
        "/api/v1/auth/login",
        json={"email": "operator@hccp.io", "password": DEMO_PASSWORDS["operator@hccp.io"]},
    ).json()
    refresh_token = session["refresh_token"]

    first = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert first.status_code == 200
    rotated = first.json()
    assert rotated["access_token"] != session["access_token"]

    # Refresh tokens are single use.
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert replay.status_code == 401
    assert "already been used" in replay.json()["error"]["message"]


def test_access_token_cannot_be_used_as_refresh_token(client):
    session = client.post(
        "/api/v1/auth/login",
        json={"email": "viewer@hccp.io", "password": DEMO_PASSWORDS["viewer@hccp.io"]},
    ).json()
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": session["access_token"]})
    assert response.status_code == 401
    assert "refresh token" in response.json()["error"]["message"].lower()


def test_logout_revokes_access_token(client):
    session = client.post(
        "/api/v1/auth/login",
        json={"email": "approver@hccp.io", "password": DEMO_PASSWORDS["approver@hccp.io"]},
    ).json()
    headers = {"Authorization": f"Bearer {session['access_token']}"}

    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204

    after = client.get("/api/v1/auth/me", headers=headers)
    assert after.status_code == 401
    assert "revoked" in after.json()["error"]["message"].lower()


def test_me_exposes_role_permissions(client, viewer_headers):
    response = client.get("/api/v1/auth/me", headers=viewer_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "viewer"
    assert "deployment:create" not in body["permissions"]
    assert "infrastructure:read" in body["permissions"]


def test_brute_force_protection_locks_account(client):
    email = "intruder@example.com"
    for _ in range(5):
        response = client.post("/api/v1/auth/login", json={"email": email, "password": "nope"})
        assert response.status_code == 401

    blocked = client.post("/api/v1/auth/login", json={"email": email, "password": "nope"})
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert "retry-after" in {key.lower() for key in blocked.headers}
