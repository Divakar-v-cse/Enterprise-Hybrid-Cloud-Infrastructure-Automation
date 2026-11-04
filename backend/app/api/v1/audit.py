"""Audit trail endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_store, require_permissions
from app.core.rbac import Permission
from app.db.store import Store
from app.schemas import AuditPage, User

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=AuditPage, summary="Search the immutable audit trail")
def list_audit(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None, max_length=80),
    actor: str | None = Query(default=None, max_length=120),
    _: User = Depends(require_permissions(Permission.AUDIT_READ)),
    store: Store = Depends(get_store),
) -> AuditPage:
    items, total = store.list_audit(limit=limit, offset=offset, action=action, actor=actor)
    return AuditPage(items=items, total=total, limit=limit, offset=offset)
