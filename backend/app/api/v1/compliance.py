"""Compliance posture endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import get_store, require_permissions
from app.core.errors import NotFoundError
from app.core.rbac import Permission
from app.db.store import Store
from app.schemas import (
    ComplianceFinding,
    Environment,
    FindingStatus,
    Severity,
    User,
)
from app.services import audit, compliance

router = APIRouter(prefix="/compliance", tags=["compliance"])


class FindingPage(BaseModel):
    items: list[ComplianceFinding]
    total: int
    summary: dict[str, int]


class ScanResponse(BaseModel):
    evaluated: int
    passed: int
    failed: int
    waived: int
    score: float


class RuleView(BaseModel):
    id: str
    title: str
    category: str
    severity: str
    description: str
    remediation: str


@router.get("/findings", response_model=FindingPage, summary="Query compliance findings")
def list_findings(
    environment: Environment | None = Query(default=None),
    severity: Severity | None = Query(default=None),
    finding_status: FindingStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(require_permissions(Permission.COMPLIANCE_READ)),
    store: Store = Depends(get_store),
) -> FindingPage:
    findings = store.list_findings()
    if environment is not None:
        findings = [f for f in findings if f.environment == environment]
    summary_counts = {
        "fail": sum(1 for f in findings if f.status is FindingStatus.FAIL),
        "pass": sum(1 for f in findings if f.status is FindingStatus.PASS),
        "waived": sum(1 for f in findings if f.status is FindingStatus.WAIVED),
    }
    if severity is not None:
        findings = [f for f in findings if f.severity == severity]
    if finding_status is not None:
        findings = [f for f in findings if f.status == finding_status]

    order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}
    failures = sorted(
        (f for f in findings if f.status is FindingStatus.FAIL),
        key=lambda f: (order[f.severity], f.resource_name),
    )
    others = [f for f in findings if f.status is not FindingStatus.FAIL]
    ordered = failures + others
    return FindingPage(items=ordered[:limit], total=len(ordered), summary=summary_counts)


@router.get("/rules", response_model=list[RuleView], summary="Policy catalogue")
def list_rules(
    _: User = Depends(require_permissions(Permission.COMPLIANCE_READ)),
) -> list[RuleView]:
    return [RuleView(**rule) for rule in compliance.rule_catalog()]


@router.post("/scan", response_model=ScanResponse, summary="Re-evaluate all policies")
def run_scan(
    environment: Environment | None = Query(default=None),
    user: User = Depends(require_permissions(Permission.COMPLIANCE_SCAN)),
    store: Store = Depends(get_store),
) -> ScanResponse:
    result = compliance.scan(store, environment)
    store.replace_findings(result.findings)
    audit.record(
        store,
        actor=user,
        action="compliance.scan",
        target=f"environment:{environment.value}" if environment else "all",
        environment=environment.value if environment else None,
        details={"evaluated": result.evaluated, "failed": result.failed, "score": result.score},
    )
    return ScanResponse(
        evaluated=result.evaluated,
        passed=result.passed,
        failed=result.failed,
        waived=result.waived,
        score=result.score,
    )


@router.post(
    "/findings/{finding_id}/waive",
    response_model=ComplianceFinding,
    summary="Waive a finding with a documented exception",
)
def waive_finding(
    finding_id: str,
    user: User = Depends(require_permissions(Permission.COMPLIANCE_SCAN)),
    store: Store = Depends(get_store),
) -> ComplianceFinding:
    finding = store.set_finding_status(finding_id, FindingStatus.WAIVED)
    if finding is None:
        raise NotFoundError(f"Finding '{finding_id}' was not found.")
    audit.record(
        store,
        actor=user,
        action="compliance.waive",
        target=finding_id,
        environment=finding.environment.value,
        details={"rule_id": finding.rule_id, "resource": finding.resource_name},
    )
    return finding
