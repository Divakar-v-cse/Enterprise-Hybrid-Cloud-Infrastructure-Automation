"""Drift detection: contract comparison, API and reporting."""

from __future__ import annotations

from app.schemas import Environment, Resource, ResourceKind, ResourceStatus
from app.services import drift


def test_dev_environment_has_drift(store):
    report = drift.detect(store, Environment.DEV)
    assert report.drift_detected is True
    names = {item.resource_name for item in report.items}
    assert "hccp-dev-web-01" in names  # instance type changed outside Terraform
    assert "hccp-dev-alb-sg" in names  # SSH opened after apply


def test_prod_detects_missing_instance(store):
    report = drift.detect(store, Environment.PROD)
    missing = [item for item in report.items if item.drift_type == "missing"]
    assert any(item.resource_name == "hccp-prod-app-03" for item in missing)
    assert any(item.severity == "critical" for item in missing)


def test_report_is_sorted_by_severity(store):
    report = drift.detect(store, Environment.DEV)
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    ranks = [order[item.severity] for item in report.items]
    assert ranks == sorted(ranks)
    assert report.drifted_resources <= len(report.items)


def test_in_sync_contract_produces_no_drift():
    resource = Resource(
        id="i-123",
        name="hccp-test-web-01",
        kind=ResourceKind.EC2,
        environment=Environment.DEV,
        region="ap-south-1",
        status=ResourceStatus.RUNNING,
        owner="platform-engineering",
        monthly_cost_usd=10.0,
        tags={"Environment": "dev", "PatchGroup": "dev-linux"},
        config={"instance_type": "t3.micro", "imds_v2_required": True},
    )
    desired = {
        "environments": {
            "dev": [
                {
                    "name": "hccp-test-web-01",
                    "kind": "ec2",
                    "config": {"instance_type": "t3.micro", "imds_v2_required": True},
                    "tags": {"Environment": "dev", "PatchGroup": "dev-linux"},
                }
            ]
        }
    }
    report = drift.compare([resource], desired, Environment.DEV)
    assert report.drift_detected is False
    assert report.checked_resources == 1


def test_modified_config_is_detected():
    resource = Resource(
        id="i-456",
        name="hccp-test-app-01",
        kind=ResourceKind.EC2,
        environment=Environment.PROD,
        region="ap-south-1",
        status=ResourceStatus.RUNNING,
        owner="platform-engineering",
        monthly_cost_usd=10.0,
        tags={"Environment": "prod"},
        config={"instance_type": "t3.small"},
    )
    desired = {
        "environments": {
            "prod": [
                {
                    "name": "hccp-test-app-01",
                    "kind": "ec2",
                    "config": {"instance_type": "m6i.large"},
                }
            ]
        }
    }
    report = drift.compare([resource], desired, Environment.PROD)
    assert len(report.items) == 1
    item = report.items[0]
    assert item.drift_type == "modified"
    assert "m6i.large" in item.expected
    assert "t3.small" in item.actual


def test_unexpected_managed_kind_is_flagged():
    resource = Resource(
        id="sg-extra",
        name="hccp-prod-legacy-sg",
        kind=ResourceKind.SECURITY_GROUP,
        environment=Environment.PROD,
        region="ap-south-1",
        status=ResourceStatus.AVAILABLE,
        owner="unknown",
        monthly_cost_usd=0.0,
        config={},
    )
    desired = {"environments": {"prod": [{"name": "hccp-prod-alb-sg", "kind": "security_group"}]}}
    report = drift.compare([resource], desired, Environment.PROD)
    types = {item.drift_type for item in report.items}
    assert types == {"missing", "unexpected"}


def test_drift_api_returns_both_environments(client, viewer_headers):
    response = client.get("/api/v1/drift", headers=viewer_headers)
    assert response.status_code == 200
    reports = response.json()
    assert {report["environment"] for report in reports} == {"dev", "prod"}
    assert all(report["provider"] for report in reports)


def test_drift_run_requires_permission(client, viewer_headers, operator_headers):
    assert client.post("/api/v1/drift/run", headers=viewer_headers).status_code == 403

    response = client.post("/api/v1/drift/run?environment=dev", headers=operator_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["environment"] == "dev"


def test_markdown_render(store):
    report = drift.detect(store, Environment.PROD)
    markdown = drift.to_markdown(report)
    assert "## Drift report - prod" in markdown
    assert "Drifted resources" in markdown
    assert "| Severity |" in markdown
