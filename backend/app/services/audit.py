"""Audit trail helpers."""

from __future__ import annotations

from typing import Any

from app.db.store import Store, new_id
from app.schemas import AuditEvent, User


def record(
    store: Store,
    *,
    actor: User | None,
    action: str,
    target: str,
    environment: str | None = None,
    outcome: str = "success",
    source_ip: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    """Append an immutable audit event.

    Authentication failures still produce an event even though there is no
    authenticated actor; the attempted email is carried in ``details``.
    """
    event = AuditEvent(
        id=new_id("evt"),
        actor_id=actor.id if actor else "anonymous",
        actor_email=actor.email if actor else str((details or {}).get("email", "anonymous")),
        action=action,
        target=target,
        environment=environment,
        outcome=outcome,
        source_ip=source_ip,
        details=details or {},
    )
    return store.append_audit(event)
