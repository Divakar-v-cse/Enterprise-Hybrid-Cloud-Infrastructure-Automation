"""Executive dashboard aggregates."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_provider, get_store, require_permissions
from app.core.rbac import Permission
from app.db.store import Store
from app.schemas import DashboardSummary, User
from app.services import deployments, inventory

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DeploymentMetrics(dict):
    """Loose mapping type - kept as a dict for forward compatibility."""


@router.get("/summary", response_model=DashboardSummary, summary="Aggregated platform posture")
def summary(
    _: User = Depends(require_permissions(Permission.INFRA_READ)),
    store: Store = Depends(get_store),
    provider=Depends(get_provider),
) -> DashboardSummary:
    return inventory.dashboard_summary(store, provider.name)


@router.get("/deployment-metrics", summary="Delivery performance indicators")
def deployment_metrics(
    _: User = Depends(require_permissions(Permission.DEPLOYMENT_READ)),
    store: Store = Depends(get_store),
) -> dict:
    history = store.list_deployments()
    return {
        "total": len(history),
        "success_rate": deployments.success_rate(store),
        "average_duration_minutes": deployments.average_duration_minutes(store),
        "pending_approvals": sum(1 for d in history if str(d.status) == "pending_approval"),
        "last_deployment_at": history[0].created_at.isoformat() if history else None,
    }
