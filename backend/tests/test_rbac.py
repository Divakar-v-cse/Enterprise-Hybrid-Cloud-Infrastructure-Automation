"""Role based access control enforcement."""

from __future__ import annotations

from app.core.rbac import Permission, Role, permissions_for, role_has_permission


def _deployment_payload(version: str = "v3.1.0-rbac") -> dict:
    return {
        "environment": "dev",
        "component": "application",
        "version": version,
        "change_summary": "RBAC matrix verification deployment",
        "risk_level": "low",
    }


def test_permission_matrix_is_monotonic():
    viewer = permissions_for(Role.VIEWER)
    operator = permissions_for(Role.OPERATOR)
    approver = permissions_for(Role.APPROVER)
    admin = permissions_for(Role.ADMIN)

    assert viewer < operator < approver < admin
    assert Permission.DEPLOYMENT_CREATE not in viewer
    assert Permission.DEPLOYMENT_APPROVE not in operator
    assert Permission.DEPLOYMENT_APPROVE in approver
    assert Permission.USER_MANAGE in admin


def test_unknown_role_has_no_permissions():
    assert permissions_for("superuser") == frozenset()
    assert role_has_permission("nobody", Permission.INFRA_READ) is False


def test_viewer_can_read_but_not_deploy(client, viewer_headers):
    assert client.get("/api/v1/resources", headers=viewer_headers).status_code == 200
    assert client.get("/api/v1/compliance/findings", headers=viewer_headers).status_code == 200

    response = client.post("/api/v1/deployments", json=_deployment_payload(), headers=viewer_headers)
    assert response.status_code == 403
    error = response.json()["error"]
    assert error["code"] == "permission_denied"
    assert "deployment:create" in error["details"]["missing_permissions"]


def test_operator_can_deploy_dev(client, operator_headers):
    response = client.post(
        "/api/v1/deployments",
        json=_deployment_payload("v3.2.0-operator"),
        headers=operator_headers,
    )
    assert response.status_code == 201
    assert response.json()["status"] == "succeeded"


def test_operator_cannot_approve(client, operator_headers):
    response = client.post(
        "/api/v1/deployments/does-not-exist/approve", json={"reason": "nope"}, headers=operator_headers
    )
    assert response.status_code == 403


def test_approver_cannot_manage_users(client, approver_headers):
    assert client.get("/api/v1/users", headers=approver_headers).status_code == 403


def test_admin_can_list_users(client, admin_headers):
    response = client.get("/api/v1/users", headers=admin_headers)
    assert response.status_code == 200
    emails = {user["email"] for user in response.json()}
    assert {"admin@hccp.io", "operator@hccp.io", "approver@hccp.io", "viewer@hccp.io"} <= emails


def test_admin_cannot_demote_self(client, admin_headers):
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    response = client.patch(
        f"/api/v1/users/{me['id']}/role", json={"role": "viewer"}, headers=admin_headers
    )
    assert response.status_code == 403


def test_operator_cannot_provision_users(client, operator_headers):
    response = client.post(
        "/api/v1/users",
        json={
            "email": "ghost@hccp.io",
            "full_name": "Ghost User",
            "role": "viewer",
            "password": "Str0ng#Passw0rd",
        },
        headers=operator_headers,
    )
    assert response.status_code == 403


def test_admin_can_provision_user_with_strong_password(client, admin_headers):
    created = client.post(
        "/api/v1/users",
        json={
            "email": "sre@hccp.io",
            "full_name": "Site Reliability Engineer",
            "role": "operator",
            "password": "Str0ng#Passw0rd",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201
    assert created.json()["role"] == "operator"
    assert "deployment:create" in created.json()["permissions"]

    weak = client.post(
        "/api/v1/users",
        json={
            "email": "weak@hccp.io",
            "full_name": "Weak Password",
            "role": "viewer",
            "password": "alllowercase",
        },
        headers=admin_headers,
    )
    assert weak.status_code == 422


def test_duplicate_email_is_conflict(client, admin_headers):
    response = client.post(
        "/api/v1/users",
        json={
            "email": "viewer@hccp.io",
            "full_name": "Duplicate",
            "role": "viewer",
            "password": "Str0ng#Passw0rd",
        },
        headers=admin_headers,
    )
    assert response.status_code == 409
