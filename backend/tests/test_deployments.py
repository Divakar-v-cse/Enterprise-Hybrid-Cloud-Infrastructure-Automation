"""Deployment state machine, approval gate and rollback."""

from __future__ import annotations


def _payload(environment: str, version: str, component: str = "application") -> dict:
    return {
        "environment": environment,
        "component": component,
        "version": version,
        "change_summary": f"Automated rollout of {version} to {environment}",
        "risk_level": "low",
    }


def test_dev_deployment_runs_immediately(client, operator_headers):
    response = client.post("/api/v1/deployments", json=_payload("dev", "v4.0.0-dev"), headers=operator_headers)
    assert response.status_code == 201
    deployment = response.json()
    assert deployment["status"] == "succeeded"
    assert deployment["approved_by"] is None
    assert deployment["completed_at"] is not None
    assert any("pipeline completed" in line for line in deployment["logs"])


def test_prod_deployment_requires_approval(client, operator_headers):
    response = client.post(
        "/api/v1/deployments", json=_payload("prod", "v4.1.0-prod"), headers=operator_headers
    )
    assert response.status_code == 201
    deployment = response.json()
    assert deployment["status"] == "pending_approval"
    assert deployment["approved_by"] is None
    assert deployment["risk_level"] == "medium"  # risk is escalated for prod automatically
    assert deployment["started_at"] is None


def test_approver_can_approve_and_run(client, operator_headers, approver_headers):
    created = client.post(
        "/api/v1/deployments", json=_payload("prod", "v4.2.0-prod"), headers=operator_headers
    ).json()

    response = client.post(
        f"/api/v1/deployments/{created['id']}/approve",
        json={"reason": "Change request CHG-1042 approved"},
        headers=approver_headers,
    )
    assert response.status_code == 200
    deployment = response.json()
    assert deployment["status"] == "succeeded"
    assert deployment["approved_by"] == "approver@hccp.io"
    assert deployment["completed_at"] is not None


def test_requester_cannot_self_approve(client, approver_headers):
    # An approver also holds deployment:create; separation of duties still applies.
    created = client.post(
        "/api/v1/deployments", json=_payload("prod", "v4.3.0-prod"), headers=approver_headers
    ).json()
    response = client.post(
        f"/api/v1/deployments/{created['id']}/approve", json={"reason": "self"}, headers=approver_headers
    )
    assert response.status_code == 403
    assert "separation of duties" in response.json()["error"]["message"].lower()


def test_reject_marks_deployment_terminal(client, operator_headers, approver_headers):
    created = client.post(
        "/api/v1/deployments", json=_payload("prod", "v4.4.0-prod"), headers=operator_headers
    ).json()
    response = client.post(
        f"/api/v1/deployments/{created['id']}/reject",
        json={"reason": "Missing rollback plan"},
        headers=approver_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_failed_pipeline_is_recorded(client, operator_headers):
    response = client.post(
        "/api/v1/deployments",
        json=_payload("dev", "v4.5.0-fail", component="compute"),
        headers=operator_headers,
    )
    deployment = response.json()
    assert deployment["status"] == "failed"
    assert any("health check failed" in line for line in deployment["logs"])


def test_invalid_transition_is_conflict(client, operator_headers, approver_headers):
    created = client.post(
        "/api/v1/deployments", json=_payload("prod", "v4.6.0-prod"), headers=operator_headers
    ).json()
    client.post(
        f"/api/v1/deployments/{created['id']}/approve", json={"reason": "ok"}, headers=approver_headers
    )
    again = client.post(
        f"/api/v1/deployments/{created['id']}/approve", json={"reason": "again"}, headers=approver_headers
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "conflict"


def test_rollback_creates_new_deployment(client, operator_headers, approver_headers):
    created = client.post(
        "/api/v1/deployments", json=_payload("prod", "v4.7.0-prod"), headers=operator_headers
    ).json()
    client.post(
        f"/api/v1/deployments/{created['id']}/approve", json={"reason": "ok"}, headers=approver_headers
    )
    response = client.post(
        f"/api/v1/deployments/{created['id']}/rollback",
        json={"reason": "Elevated 5xx rate"},
        headers=approver_headers,
    )
    assert response.status_code == 200
    rollback = response.json()
    assert rollback["rollback_of"] == created["id"]
    assert rollback["version"].startswith("rollback-")
    assert rollback["status"] == "succeeded"

    original = client.get(f"/api/v1/deployments/{created['id']}", headers=approver_headers).json()
    assert original["status"] == "rolled_back"


def test_rollback_requires_succeeded_state(client, approver_headers):
    pending = client.post(
        "/api/v1/deployments", json=_payload("prod", "v4.8.0-prod"), headers=approver_headers
    ).json()
    response = client.post(
        f"/api/v1/deployments/{pending['id']}/rollback", json={"reason": "x"}, headers=approver_headers
    )
    assert response.status_code == 409


def test_version_validation(client, operator_headers):
    bad = client.post(
        "/api/v1/deployments",
        json={
            "environment": "dev",
            "component": "application",
            "version": "bad version with spaces",
            "change_summary": "should fail validation",
        },
        headers=operator_headers,
    )
    assert bad.status_code == 422
    assert bad.json()["error"]["details"]["fields"]


def test_deployment_list_and_metrics(client, viewer_headers):
    listing = client.get("/api/v1/deployments?limit=5", headers=viewer_headers)
    assert listing.status_code == 200
    assert listing.json()["items"]

    metrics = client.get("/api/v1/dashboard/deployment-metrics", headers=viewer_headers)
    assert metrics.status_code == 200
    body = metrics.json()
    assert body["total"] >= 1
    assert 0 <= body["success_rate"] <= 100
    assert body["average_duration_minutes"] >= 0


def test_deployment_filter_by_environment(client, viewer_headers):
    dev = client.get("/api/v1/deployments?environment=dev&limit=100", headers=viewer_headers).json()
    assert dev["total"] >= 1
    assert all(item["environment"] == "dev" for item in dev["items"])
