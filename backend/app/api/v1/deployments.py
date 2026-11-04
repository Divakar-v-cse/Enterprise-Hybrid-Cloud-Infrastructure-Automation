"""Deployment lifecycle endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from app.api.deps import get_store, require_permissions
from app.core.errors import NotFoundError
from app.core.rbac import Permission
from app.db.store import Store
from app.schemas import (
    Deployment,
    DeploymentActionRequest,
    DeploymentCreateRequest,
    DeploymentStatus,
    Environment,
    User,
)
from app.services import deployments as deployment_service

router = APIRouter(prefix="/deployments", tags=["deployments"])


class DeploymentPage(BaseModel):
    items: list[Deployment]
    total: int
    limit: int


@router.get("", response_model=DeploymentPage, summary="Deployment history")
def list_deployments(
    environment: Environment | None = Query(default=None),
    deployment_status: DeploymentStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=25, ge=1, le=100),
    _: User = Depends(require_permissions(Permission.DEPLOYMENT_READ)),
    store: Store = Depends(get_store),
) -> DeploymentPage:
    items = store.list_deployments()
    if environment is not None:
        items = [d for d in items if d.environment == environment]
    if deployment_status is not None:
        items = [d for d in items if d.status == deployment_status]
    return DeploymentPage(items=items[:limit], total=len(items), limit=limit)


@router.get("/{deployment_id}", response_model=Deployment, summary="Deployment detail")
def get_deployment(
    deployment_id: str,
    _: User = Depends(require_permissions(Permission.DEPLOYMENT_READ)),
    store: Store = Depends(get_store),
) -> Deployment:
    deployment = store.get_deployment(deployment_id)
    if deployment is None:
        raise NotFoundError(f"Deployment '{deployment_id}' was not found.")
    return deployment


@router.post(
    "",
    response_model=Deployment,
    status_code=status.HTTP_201_CREATED,
    summary="Request a deployment (prod requires approval)",
)
def create_deployment(
    payload: DeploymentCreateRequest,
    user: User = Depends(require_permissions(Permission.DEPLOYMENT_CREATE)),
    store: Store = Depends(get_store),
) -> Deployment:
    return deployment_service.create(store, payload, user)


@router.post(
    "/{deployment_id}/approve",
    response_model=Deployment,
    summary="Approve and run a pending production deployment",
)
def approve_deployment(
    deployment_id: str,
    payload: DeploymentActionRequest,
    user: User = Depends(require_permissions(Permission.DEPLOYMENT_APPROVE)),
    store: Store = Depends(get_store),
) -> Deployment:
    return deployment_service.approve(store, deployment_id, user, reason=payload.reason)


@router.post(
    "/{deployment_id}/reject",
    response_model=Deployment,
    summary="Reject a pending deployment",
)
def reject_deployment(
    deployment_id: str,
    payload: DeploymentActionRequest,
    user: User = Depends(require_permissions(Permission.DEPLOYMENT_APPROVE)),
    store: Store = Depends(get_store),
) -> Deployment:
    return deployment_service.reject(store, deployment_id, user, reason=payload.reason)


@router.post(
    "/{deployment_id}/rollback",
    response_model=Deployment,
    summary="Roll back a succeeded deployment",
)
def rollback_deployment(
    deployment_id: str,
    payload: DeploymentActionRequest,
    user: User = Depends(require_permissions(Permission.DEPLOYMENT_ROLLBACK)),
    store: Store = Depends(get_store),
) -> Deployment:
    return deployment_service.rollback(store, deployment_id, user, reason=payload.reason)
