"""Policy-as-code engine and compliance API."""

from __future__ import annotations

from app.schemas import Environment
from app.services import compliance


def test_scan_flags_open_ssh_on_dev_security_group(store):
    result = compliance.scan(store)
    open_ssh = [
        f
        for f in result.findings
        if f.rule_id == "HC-SG-001" and f.resource_name == "hccp-dev-alb-sg"
    ]
    assert len(open_ssh) == 1
    finding = open_ssh[0]
    assert finding.status == "fail"
    assert finding.severity == "critical"
    assert "SSH" in finding.description


def test_scan_flags_wildcard_iam_policy(store):
    result = compliance.scan(store)
    wildcard = [
        f for f in result.findings if f.rule_id == "HC-IAM-001" and f.status == "fail"
    ]
    assert wildcard, "expected the dev IAM role to violate the wildcard rule"
    assert wildcard[0].resource_name == "hccp-dev-ec2-role"


def test_production_is_cleaner_than_development(store):
    dev = compliance.scan(store, Environment.DEV)
    prod = compliance.scan(store, Environment.PROD)
    assert dev.failed > 0
    assert dev.score < prod.score
    assert 0 <= dev.score <= 100


def test_scan_result_counts_are_consistent(store):
    result = compliance.scan(store)
    assert result.passed + result.failed == len(result.findings)
    assert result.evaluated >= result.passed + result.failed


def test_findings_endpoint_orders_by_severity(client, viewer_headers):
    response = client.get("/api/v1/compliance/findings?limit=200", headers=viewer_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert body["summary"]["fail"] >= 1

    severities = [item["severity"] for item in body["items"] if item["status"] == "fail"]
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    assert severities == sorted(severities, key=lambda s: order[s])
    assert severities[0] == "critical"


def test_findings_filter_by_environment_and_severity(client, viewer_headers):
    response = client.get(
        "/api/v1/compliance/findings?environment=prod&severity=high&limit=200",
        headers=viewer_headers,
    )
    assert response.status_code == 200
    for item in response.json()["items"]:
        assert item["environment"] == "prod"
        assert item["severity"] == "high"


def test_scan_endpoint_requires_operator(client, viewer_headers, operator_headers):
    denied = client.post("/api/v1/compliance/scan", headers=viewer_headers)
    assert denied.status_code == 403

    allowed = client.post("/api/v1/compliance/scan", headers=operator_headers)
    assert allowed.status_code == 200
    body = allowed.json()
    assert body["evaluated"] > 0
    assert body["failed"] >= 1
    assert body["score"] < 100


def test_waiver_survives_rescan(client, operator_headers, viewer_headers):
    findings = client.get(
        "/api/v1/compliance/findings?status=fail&severity=critical&limit=50", headers=viewer_headers
    ).json()["items"]
    assert findings
    target = findings[0]

    waived = client.post(f"/api/v1/compliance/findings/{target['id']}/waive", headers=operator_headers)
    assert waived.status_code == 200
    assert waived.json()["status"] == "waived"

    client.post("/api/v1/compliance/scan", headers=operator_headers)

    after = client.get("/api/v1/compliance/findings?limit=500", headers=viewer_headers).json()["items"]
    match = next(item for item in after if item["id"] == target["id"])
    assert match["status"] == "waived"


def test_waive_unknown_finding_is_404(client, operator_headers):
    response = client.post("/api/v1/compliance/findings/nope/waive", headers=operator_headers)
    assert response.status_code == 404


def test_rule_catalogue(client, viewer_headers):
    response = client.get("/api/v1/compliance/rules", headers=viewer_headers)
    assert response.status_code == 200
    rules = response.json()
    assert len(rules) >= 12
    ids = [rule["id"] for rule in rules]
    assert len(ids) == len(set(ids))
    assert {"HC-SG-001", "HC-IAM-001", "HC-VPC-001", "HC-ALB-002"} <= set(ids)
    for rule in rules:
        assert rule["remediation"]
        assert rule["severity"] in {"critical", "high", "medium", "low"}
