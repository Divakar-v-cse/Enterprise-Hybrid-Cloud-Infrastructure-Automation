"""Infrastructure inventory endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_store, require_permissions
from app.core.errors import NotFoundError
from app.core.rbac import Permission
from app.db.store import Store
from app.schemas import (
    Environment,
    EnvironmentSummary,
    Resource,
    ResourceKind,
    ResourceStatus,
    User,
)
from app.services import inventory

router = APIRouter(tags=["infrastructure"])


from pydantic import BaseModel  # noqa: E402  (kept local to the router module)


class ResourcePage(BaseModel):
    items: list[Resource]
    total: int
    limit: int
    offset: int


@router.get("/resources", response_model=ResourcePage, summary="List managed resources")
def list_resources(
    environment: Environment | None = Query(default=None),
    kind: ResourceKind | None = Query(default=None),
    status_filter: ResourceStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_permissions(Permission.INFRA_READ)),
    store: Store = Depends(get_store),
) -> ResourcePage:
    resources = store.list_resources()
    if environment is not None:
        resources = [r for r in resources if r.environment == environment]
    if kind is not None:
        resources = [r for r in resources if r.kind == kind]
    if status_filter is not None:
        resources = [r for r in resources if r.status == status_filter]
    if search:
        needle = search.lower()
        resources = [
            r
            for r in resources
            if needle in r.name.lower()
            or needle in r.id.lower()
            or needle in r.owner.lower()
            or any(needle in value.lower() for value in r.tags.values())
        ]

    resources.sort(key=lambda r: (str(r.environment), str(r.kind), r.name))
    total = len(resources)
    return ResourcePage(items=resources[offset : offset + limit], total=total, limit=limit, offset=offset)


@router.get("/resources/{resource_id}", response_model=Resource, summary="Resource detail")
def get_resource(
    resource_id: str,
    _: User = Depends(require_permissions(Permission.INFRA_READ)),
    store: Store = Depends(get_store),
) -> Resource:
    resource = store.get_resource(resource_id)
    if resource is None:
        raise NotFoundError(f"Resource '{resource_id}' was not found.")
    return resource


@router.get(
    "/environments",
    response_model=list[EnvironmentSummary],
    summary="Per-environment rollup",
)
def list_environments(
    _: User = Depends(require_permissions(Permission.INFRA_READ)),
    store: Store = Depends(get_store),
) -> list[EnvironmentSummary]:
    return [inventory.environment_summary(store, env) for env in Environment]
