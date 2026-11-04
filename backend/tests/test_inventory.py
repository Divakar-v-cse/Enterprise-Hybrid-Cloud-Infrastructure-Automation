"""Inventory, dashboard and probe endpoints."""

from __future__ import annotations

import pytest


def test_resources_pagination_and_total(client, viewer_headers, store):
    response = client.get("/api/v1/resources?limit=5", headers=viewer_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == len(store.list_resources())
    assert len(body["items"]) == 5
    assert body["limit"] == 5

    second = client.get("/api/v1/resources?limit=5&offset=5", headers=viewer_headers).json()
    first_ids = {item["id"] for item in body["items"]}
    second_ids = {item["id"] for item in second["items"]}
    assert first_ids.isdisjoint(second_ids)


def test_resource_filters(client, viewer_headers):
    dev = client.get("/api/v1/resources?environment=dev&limit=200", headers=viewer_headers).json()
    assert dev["total"] > 0
    assert all(item["environment"] == "dev" for item in dev["items"])

    ec2 = client.get("/api/v1/resources?kind=ec2&limit=200", headers=viewer_headers).json()
    assert ec2["total"] >= 9
    assert all(item["kind"] == "ec2" for item in ec2["items"])

    search = client.get("/api/v1/resources?search=win-01&limit=200", headers=viewer_headers).json()
    assert search["total"] >= 2
    assert all("win-01" in item["name"].lower() for item in search["items"])


def test_resource_detail_and_404(client, viewer_headers):
    listing = client.get("/api/v1/resources?limit=1", headers=viewer_headers).json()
    resource_id = listing["items"][0]["id"]
    detail = client.get(f"/api/v1/resources/{resource_id}", headers=viewer_headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == resource_id

    missing = client.get("/api/v1/resources/does-not-exist", headers=viewer_headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


def test_environment_rollup(client, viewer_headers):
    response = client.get("/api/v1/environments", headers=viewer_headers)
    assert response.status_code == 200
    environments = {item["environment"]: item for item in response.json()}
    assert set(environments) == {"dev", "prod"}
    assert environments["prod"]["resources"] > 0
    assert environments["prod"]["monthly_cost_usd"] > environments["dev"]["monthly_cost_usd"]


def test_servers_endpoint_matches_inventory(client, viewer_headers, store):
    response = client.get("/api/v1/servers", headers=viewer_headers)
    assert response.status_code == 200
    servers = response.json()
    expected = [r for r in store.list_resources() if r.kind == "ec2"]
    assert len(servers) == len(expected)
    assert {s["operating_system"] for s in servers} == {"Linux", "Windows Server 2022"}
    assert all(0 <= s["health_score"] <= 100 for s in servers)

    summary = client.get("/api/v1/servers/summary", headers=viewer_headers).json()
    assert summary["total"] == len(expected)
    assert summary["by_os"]["Linux"] >= 1
    assert summary["by_os"]["Windows Server 2022"] >= 1
    assert sum(summary["by_health"].values()) == len(expected)
    assert 0 < summary["average_health_score"] <= 100


@pytest.mark.parametrize("path", ["/healthz", "/readyz"])
def test_probes(client, path):
    response = client.get(path)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "ready"}


def test_root_descriptor(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"]
    assert response.json()["api"] == "/api/v1"


def test_dashboard_summary_is_internally_consistent(client, viewer_headers, store):
    summary = client.get("/api/v1/dashboard/summary", headers=viewer_headers).json()
    assert summary["provider"] == "mock"
    assert summary["total_resources"] == len(store.list_resources())
    assert sum(item["resources"] for item in summary["environments"]) == summary["total_resources"]

    servers = [r for r in store.list_resources() if r.kind == "ec2"]
    assert summary["servers_total"] == len(servers)
    assert (
        summary["servers_healthy"] + summary["servers_warning"] + summary["servers_critical"]
        == len(servers)
    )
    assert 0 <= summary["compliance_score"] <= 100
    assert summary["open_findings"] >= 1
    assert set(summary["findings_by_severity"]) == {"critical", "high", "medium", "low"}


def test_security_headers_are_present(client):
    response = client.get("/healthz")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Content-Security-Policy"].startswith("default-src 'none'")
    assert response.headers["X-Request-ID"]
    assert float(response.headers["X-Response-Time-Ms"]) >= 0


def test_request_id_is_echoed(client):
    response = client.get("/healthz", headers={"X-Request-ID": "trace-abc-123"})
    assert response.headers["X-Request-ID"] == "trace-abc-123"
