"""Audit trail behaviour."""

from __future__ import annotations

from conftest import DEMO_PASSWORDS


def test_login_is_audited(client, admin_headers):
    client.post(
        "/api/v1/auth/login",
        json={"email": "viewer@hccp.io", "password": DEMO_PASSWORDS["viewer@hccp.io"]},
    )
    response = client.get("/api/v1/audit?action=auth.login&limit=50", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert any(item["action"] == "auth.login" for item in body["items"])


def test_failed_login_is_audited_with_source_ip(client, admin_headers):
    client.post("/api/v1/auth/login", json={"email": "audit-probe@example.com", "password": "bad"})
    response = client.get("/api/v1/audit?action=auth.login&limit=100", headers=admin_headers)
    assert response.status_code == 200
    failures = [item for item in response.json()["items"] if item["outcome"] == "failure"]
    assert failures
    assert failures[0]["source_ip"] == "testclient"


def test_deployment_actions_are_audited(client, operator_headers, admin_headers):
    created = client.post(
        "/api/v1/deployments",
        json={
            "environment": "dev",
            "component": "configuration",
            "version": "v9.0.0-audit",
            "change_summary": "Audit trail verification deployment",
        },
        headers=operator_headers,
    ).json()

    response = client.get("/api/v1/audit?action=deployment&limit=100", headers=admin_headers)
    assert response.status_code == 200
    targets = {item["target"] for item in response.json()["items"]}
    assert created["id"] in targets


def test_audit_pagination(client, viewer_headers):
    first = client.get("/api/v1/audit?limit=2&offset=0", headers=viewer_headers).json()
    second = client.get("/api/v1/audit?limit=2&offset=2", headers=viewer_headers).json()
    assert first["limit"] == 2
    assert first["total"] == second["total"]
    if first["total"] > 2:
        assert first["items"][0]["id"] != second["items"][0]["id"]


def test_audit_requires_authentication(client):
    assert client.get("/api/v1/audit").status_code == 401
