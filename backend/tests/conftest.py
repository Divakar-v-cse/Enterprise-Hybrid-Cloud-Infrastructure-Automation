"""Shared pytest fixtures.

The app is built once per test session with an isolated in-memory store.
Individual tests must not depend on the mutations made by other tests: they
create their own deployments / users, or query by stable identifiers.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

DEMO_PASSWORDS = {
    "admin@hccp.io": "Admin#2026",
    "operator@hccp.io": "Operator#2026",
    "approver@hccp.io": "Approver#2026",
    "viewer@hccp.io": "Viewer#2026",
}


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(
        environment="local",
        secret_key="unit-test-secret-key-0123456789abcdef",
        access_token_ttl_minutes=60,
        login_max_attempts=5,
        login_lockout_seconds=60,
        drift_interval_seconds=0,
        seed_demo_data=True,
        provider="mock",
    )


@pytest.fixture(scope="session")
def app(settings):
    return create_app(settings)


@pytest.fixture(scope="session")
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def store(app):
    return app.state.store


def login(client: TestClient, email: str) -> tuple[str, dict]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": DEMO_PASSWORDS[email]})
    assert response.status_code == 200, response.text
    payload = response.json()
    return payload["access_token"], payload


def auth_headers(client: TestClient, email: str) -> dict[str, str]:
    token, _ = login(client, email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def admin_headers(client) -> dict[str, str]:
    return auth_headers(client, "admin@hccp.io")


@pytest.fixture(scope="session")
def operator_headers(client) -> dict[str, str]:
    return auth_headers(client, "operator@hccp.io")


@pytest.fixture(scope="session")
def approver_headers(client) -> dict[str, str]:
    return auth_headers(client, "approver@hccp.io")


@pytest.fixture(scope="session")
def viewer_headers(client) -> dict[str, str]:
    return auth_headers(client, "viewer@hccp.io")
