"""Configuration drift endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_store, require_permissions
from app.core.rbac import Permission
from app.db.store import Store
from app.schemas import DriftReport, Environment, User
from app.services import audit, drift

router = APIRouter(prefix="/drift", tags=["drift"])


@router.get("", response_model=list[DriftReport], summary="Compare live state to the contract")
def get_drift(
    environment: Environment | None = Query(default=None),
    _: User = Depends(require_permissions(Permission.DRIFT_READ)),
    store: Store = Depends(get_store),
) -> list[DriftReport]:
    targets = [environment] if environment else list(Environment)
    return [drift.detect(store, env) for env in targets]


@router.post("/run", response_model=list[DriftReport], summary="Trigger a drift detection run")
def run_drift(
    environment: Environment | None = Query(default=None),
    user: User = Depends(require_permissions(Permission.DRIFT_RUN)),
    store: Store = Depends(get_store),
) -> list[DriftReport]:
    targets = [environment] if environment else list(Environment)
    reports = [drift.detect(store, env) for env in targets]
    for report in reports:
        audit.record(
            store,
            actor=user,
            action="drift.run",
            target=f"environment:{report.environment.value}",
            environment=report.environment.value,
            outcome="drift_detected" if report.drift_detected else "success",
            details={
                "checked": report.checked_resources,
                "drifted": report.drifted_resources,
            },
        )
    return reports
