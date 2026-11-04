"""Server fleet health endpoints."""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import get_store, require_permissions
from app.core.rbac import Permission
from app.db.store import Store
from app.schemas import Environment, HealthStatus, PatchStatus, ResourceKind, User
from app.services import inventory

router = APIRouter(prefix="/servers", tags=["servers"])


class ServerView(BaseModel):
    id: str
    name: str
    environment: Environment
    operating_system: str
    instance_type: str
    private_ip: str | None = None
    status: str
    health_score: int | None = None
    health_status: str | None = None
    cpu_percent: float | None = None
    memory_percent: float | None = None
    disk_percent: float | None = None
    patch_status: str | None = None
    agent_version: str | None = None
    uptime_hours: int | None = None
    last_seen: str | None = None


class ServerFleetSummary(BaseModel):
    total: int
    by_os: dict[str, int]
    by_environment: dict[str, int]
    by_health: dict[str, int]
    by_patch_status: dict[str, int]
    average_health_score: float


def _to_view(resource) -> ServerView:
    health = resource.health
    return ServerView(
        id=resource.id,
        name=resource.name,
        environment=resource.environment,
        operating_system=str(resource.config.get("os", "unknown")),
        instance_type=str(resource.config.get("instance_type", "unknown")),
        private_ip=resource.config.get("private_ip"),
        status=str(resource.status),
        health_score=health.score if health else None,
        health_status=str(health.status) if health else None,
        cpu_percent=health.cpu_percent if health else None,
        memory_percent=health.memory_percent if health else None,
        disk_percent=health.disk_percent if health else None,
        patch_status=str(health.patch_status) if health else None,
        agent_version=health.agent_version if health else None,
        uptime_hours=health.uptime_hours if health else None,
        last_seen=health.last_seen.isoformat() if health else None,
    )


@router.get("", response_model=list[ServerView], summary="Server fleet with health telemetry")
def list_servers(
    environment: Environment | None = Query(default=None),
    _: User = Depends(require_permissions(Permission.INFRA_READ)),
    store: Store = Depends(get_store),
) -> list[ServerView]:
    servers = [r for r in store.list_resources() if r.kind == ResourceKind.EC2]
    if environment is not None:
        servers = [s for s in servers if s.environment == environment]
    view = [_to_view(server) for server in servers]
    view.sort(key=lambda s: (str(s.environment), s.health_score if s.health_score is not None else 0))
    return view


@router.get("/summary", response_model=ServerFleetSummary, summary="Fleet health rollup")
def fleet_summary(
    _: User = Depends(require_permissions(Permission.INFRA_READ)),
    store: Store = Depends(get_store),
) -> ServerFleetSummary:
    servers = [r for r in store.list_resources() if r.kind == ResourceKind.EC2]
    scores = [r.health.score for r in servers if r.health]
    by_os = Counter(str(r.config.get("os", "unknown")) for r in servers)
    by_env = Counter(str(r.environment) for r in servers)
    by_health = Counter(str(r.health.status) for r in servers if r.health)
    by_patch = Counter(str(r.health.patch_status) for r in servers if r.health)
    # Ensure every enum value is represented so the UI never has gaps.
    for status in HealthStatus:
        by_health.setdefault(status.value, 0)
    for patch in PatchStatus:
        by_patch.setdefault(patch.value, 0)
    return ServerFleetSummary(
        total=len(servers),
        by_os=dict(by_os),
        by_environment=dict(by_env),
        by_health=dict(by_health),
        by_patch_status=dict(by_patch),
        average_health_score=round(sum(scores) / len(scores), 1) if scores else 0.0,
    )


__all__ = ["router", "inventory"]
