"""Inventory aggregation for dashboards and reporting."""

from __future__ import annotations

from collections import defaultdict

from app.db.store import Store
from app.providers.base import CloudProvider
from app.schemas import (
    DashboardSummary,
    DeploymentStatus,
    Environment,
    EnvironmentSummary,
    FindingStatus,
    HealthStatus,
    Resource,
    ResourceKind,
    Severity,
)


def refresh_inventory(store: Store, provider: CloudProvider) -> list[Resource]:
    """Pull the latest inventory from the provider into the store."""
    resources = provider.list_resources()
    store.replace_inventory(resources)
    return resources


def _servers(resources: list[Resource]) -> list[Resource]:
    return [r for r in resources if r.kind == ResourceKind.EC2]


def environment_summary(store: Store, environment: Environment) -> EnvironmentSummary:
    resources = [r for r in store.list_resources() if r.environment == environment]
    findings = [
        f
        for f in store.list_findings()
        if f.environment == environment and f.status is FindingStatus.FAIL
    ]
    deployments = [d for d in store.list_deployments() if d.environment == environment]
    servers = _servers(resources)
    healthy = sum(
        1 for s in servers if s.health is not None and s.health.status is HealthStatus.HEALTHY
    )
    return EnvironmentSummary(
        environment=environment,
        resources=len(resources),
        monthly_cost_usd=round(sum(r.monthly_cost_usd for r in resources), 2),
        servers=len(servers),
        healthy_servers=healthy,
        open_findings=len(findings),
        critical_findings=sum(1 for f in findings if f.severity is Severity.CRITICAL),
        last_deployment=deployments[0].created_at if deployments else None,
        last_deployment_status=deployments[0].status if deployments else None,
    )


def dashboard_summary(store: Store, provider_name: str) -> DashboardSummary:
    resources = store.list_resources()
    findings = store.list_findings()
    failed = [f for f in findings if f.status is FindingStatus.FAIL]
    servers = _servers(resources)

    cost_by_kind: dict[str, float] = defaultdict(float)
    for resource in resources:
        cost_by_kind[resource.kind] += resource.monthly_cost_usd

    findings_by_severity = {severity.value: 0 for severity in Severity}
    for finding in failed:
        findings_by_severity[str(finding.severity)] += 1

    weights = {Severity.CRITICAL: 10, Severity.HIGH: 5, Severity.MEDIUM: 2, Severity.LOW: 1}
    total_weight = sum(weights[f.severity] for f in findings if f.status is not FindingStatus.WAIVED)
    passed_weight = sum(
        weights[f.severity] for f in findings if f.status is FindingStatus.PASS
    )
    score = round(100.0 * passed_weight / total_weight, 1) if total_weight else 100.0

    pending = sum(
        1
        for d in store.list_deployments()
        if d.status is DeploymentStatus.PENDING_APPROVAL
    )

    return DashboardSummary(
        provider=provider_name,
        total_resources=len(resources),
        total_monthly_cost_usd=round(sum(r.monthly_cost_usd for r in resources), 2),
        servers_total=len(servers),
        servers_healthy=sum(
            1 for s in servers if s.health is not None and s.health.status is HealthStatus.HEALTHY
        ),
        servers_warning=sum(
            1 for s in servers if s.health is not None and s.health.status is HealthStatus.WARNING
        ),
        servers_critical=sum(
            1 for s in servers if s.health is not None and s.health.status is HealthStatus.CRITICAL
        ),
        open_findings=len(failed),
        critical_findings=sum(1 for f in failed if f.severity is Severity.CRITICAL),
        compliance_score=score,
        pending_approvals=pending,
        environments=[environment_summary(store, env) for env in Environment],
        cost_by_kind={str(kind): round(cost, 2) for kind, cost in sorted(cost_by_kind.items())},
        findings_by_severity=findings_by_severity,
    )
