"""Thread-safe repository for control-plane state.

The API depends on this class, not on a database driver. Swapping the
in-memory implementation for PostgreSQL means implementing the same methods
with SQLAlchemy sessions (``backend/app/db/postgres.py`` would be the natural
home) - no route or service changes required.
"""

from __future__ import annotations

import threading
import uuid
from collections import deque
from datetime import UTC, datetime, timedelta

from app.core.config import Settings
from app.core.security import hash_password
from app.schemas import (
    AuditEvent,
    ComplianceFinding,
    Deployment,
    DeploymentComponent,
    DeploymentStatus,
    Environment,
    FindingStatus,
    Resource,
    Role,
    Severity,
    User,
    utcnow,
)

_MAX_AUDIT_EVENTS = 2_000


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class Store:
    """In-process, lock-guarded store. Single-worker only by design."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.RLock()
        self.users: dict[str, User] = {}
        self.resources: dict[str, Resource] = {}
        self.deployments: dict[str, Deployment] = {}
        self.findings: list[ComplianceFinding] = []
        self.audit_events: deque[AuditEvent] = deque(maxlen=_MAX_AUDIT_EVENTS)
        self._revoked_tokens: dict[str, float] = {}
        self._login_attempts: dict[str, list[float]] = {}
        self._seed_users()

    # -- users --------------------------------------------------------------
    def _seed_users(self) -> None:
        if not self._settings.seed_demo_data:
            return
        seeds = [
            ("admin@hccp.io", "Aarav Menon", Role.ADMIN),
            ("operator@hccp.io", "Priya Raghavan", Role.OPERATOR),
            ("approver@hccp.io", "Daniel Fischer", Role.APPROVER),
            ("viewer@hccp.io", "Sofia Almeida", Role.VIEWER),
        ]
        for email, name, role in seeds:
            password = self._settings.demo_password(role.value)
            user = User(
                id=_id("usr"),
                email=email,
                full_name=name,
                role=role,
                password_hash=hash_password(password, iterations=10_000),
                mfa_enabled=True,
                created_at=utcnow() - timedelta(days=90),
                last_login_at=utcnow() - timedelta(hours=6),
            )
            self.users[user.id] = user

    def get_user(self, user_id: str) -> User | None:
        with self._lock:
            return self.users.get(user_id)

    def get_user_by_email(self, email: str) -> User | None:
        normalised = email.strip().lower()
        with self._lock:
            return next((u for u in self.users.values() if u.email == normalised), None)

    def list_users(self) -> list[User]:
        with self._lock:
            return sorted(self.users.values(), key=lambda u: u.email)

    def add_user(self, user: User) -> User:
        with self._lock:
            self.users[user.id] = user
            return user

    def update_role(self, user_id: str, role: Role) -> User | None:
        with self._lock:
            user = self.users.get(user_id)
            if user is None:
                return None
            updated = user.model_copy(update={"role": role})
            self.users[user_id] = updated
            return updated

    def touch_login(self, user_id: str) -> None:
        with self._lock:
            user = self.users.get(user_id)
            if user is not None:
                self.users[user_id] = user.model_copy(update={"last_login_at": utcnow()})

    # -- login throttling ---------------------------------------------------
    def register_failed_login(self, key: str) -> None:
        now = datetime.now(UTC).timestamp()
        with self._lock:
            attempts = [t for t in self._login_attempts.get(key, []) if now - t < self._settings.login_lockout_seconds]
            attempts.append(now)
            self._login_attempts[key] = attempts

    def login_locked(self, key: str) -> bool:
        now = datetime.now(UTC).timestamp()
        with self._lock:
            attempts = [
                t for t in self._login_attempts.get(key, []) if now - t < self._settings.login_lockout_seconds
            ]
            self._login_attempts[key] = attempts
            return len(attempts) >= self._settings.login_max_attempts

    def clear_login_attempts(self, key: str) -> None:
        with self._lock:
            self._login_attempts.pop(key, None)

    # -- tokens -------------------------------------------------------------
    def revoke_token(self, jti: str, expires_at: float) -> None:
        with self._lock:
            self._revoked_tokens[jti] = expires_at

    def is_revoked(self, jti: str) -> bool:
        now = datetime.now(UTC).timestamp()
        with self._lock:
            expired = [key for key, exp in self._revoked_tokens.items() if exp <= now]
            for key in expired:
                self._revoked_tokens.pop(key, None)
            return jti in self._revoked_tokens

    # -- inventory ----------------------------------------------------------
    def replace_inventory(self, resources: list[Resource]) -> None:
        with self._lock:
            self.resources = {resource.id: resource for resource in resources}

    def list_resources(self) -> list[Resource]:
        with self._lock:
            return list(self.resources.values())

    def get_resource(self, resource_id: str) -> Resource | None:
        with self._lock:
            return self.resources.get(resource_id)

    # -- deployments --------------------------------------------------------
    def add_deployment(self, deployment: Deployment) -> Deployment:
        with self._lock:
            self.deployments[deployment.id] = deployment
            return deployment

    def get_deployment(self, deployment_id: str) -> Deployment | None:
        with self._lock:
            return self.deployments.get(deployment_id)

    def list_deployments(self) -> list[Deployment]:
        with self._lock:
            return sorted(self.deployments.values(), key=lambda d: d.created_at, reverse=True)

    def save_deployment(self, deployment: Deployment) -> Deployment:
        with self._lock:
            self.deployments[deployment.id] = deployment
            return deployment

    # -- findings -----------------------------------------------------------
    def replace_findings(self, findings: list[ComplianceFinding]) -> None:
        with self._lock:
            waived = {f.rule_id + f.resource_id for f in self.findings if f.status == FindingStatus.WAIVED}
            merged: list[ComplianceFinding] = []
            for finding in findings:
                if finding.rule_id + finding.resource_id in waived:
                    merged.append(
                        finding.model_copy(update={"status": FindingStatus.WAIVED})
                    )
                else:
                    merged.append(finding)
            self.findings = merged

    def list_findings(self) -> list[ComplianceFinding]:
        with self._lock:
            return list(self.findings)

    def set_finding_status(self, finding_id: str, status: FindingStatus) -> ComplianceFinding | None:
        with self._lock:
            for index, finding in enumerate(self.findings):
                if finding.id == finding_id:
                    updated = finding.model_copy(update={"status": status})
                    self.findings[index] = updated
                    return updated
            return None

    # -- audit --------------------------------------------------------------
    def append_audit(self, event: AuditEvent) -> AuditEvent:
        with self._lock:
            self.audit_events.appendleft(event)
            return event

    def list_audit(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        action: str | None = None,
        actor: str | None = None,
    ) -> tuple[list[AuditEvent], int]:
        with self._lock:
            events = list(self.audit_events)
        if action:
            events = [e for e in events if e.action.startswith(action)]
        if actor:
            events = [e for e in events if actor.lower() in e.actor_email.lower()]
        total = len(events)
        return events[offset : offset + limit], total

    # -- seeding ------------------------------------------------------------
    def seed_deployment_history(self) -> None:
        """Insert a realistic deployment history for the dashboard timeline."""
        if not self._settings.seed_demo_data:
            return
        now = utcnow()
        history = [
            (Environment.PROD, DeploymentComponent.APPLICATION, "v2.14.0", DeploymentStatus.SUCCEEDED, 26, 14.5),
            (Environment.PROD, DeploymentComponent.CONFIGURATION, "ansible-9f2c41a", DeploymentStatus.SUCCEEDED, 52, 6.2),
            (Environment.DEV, DeploymentComponent.COMPUTE, "v2.15.0-rc1", DeploymentStatus.SUCCEEDED, 8, 4.1),
            (Environment.PROD, DeploymentComponent.NETWORK, "terraform-4b81c0d", DeploymentStatus.FAILED, 74, 3.4),
            (Environment.DEV, DeploymentComponent.APPLICATION, "v2.14.2", DeploymentStatus.SUCCEEDED, 96, 5.5),
            (Environment.PROD, DeploymentComponent.APPLICATION, "v2.13.4", DeploymentStatus.ROLLED_BACK, 120, 8.0),
            (Environment.DEV, DeploymentComponent.NETWORK, "terraform-1ac77e2", DeploymentStatus.SUCCEEDED, 168, 7.6),
        ]
        for env, component, version, status, hours_ago, duration in history:
            created = now - timedelta(hours=hours_ago)
            self.add_deployment(
                Deployment(
                    id=_id("dep"),
                    environment=env,
                    component=component,
                    version=version,
                    status=status,
                    requested_by="usr-seed",
                    requested_by_email="operator@hccp.io",
                    approved_by="approver@hccp.io" if env is Environment.PROD else None,
                    change_summary=f"Automated {component.value} rollout for {version}",
                    risk_level=Severity.MEDIUM if env is Environment.PROD else Severity.LOW,
                    created_at=created,
                    started_at=created + timedelta(minutes=1),
                    completed_at=created + timedelta(minutes=duration),
                    logs=[
                        f"[{created:%H:%M:%S}] terraform plan: no unexpected changes",
                        f"[{created:%H:%M:%S}] ansible-playbook --limit {env.value}: ok",
                        f"[{created:%H:%M:%S}] health checks passed",
                    ]
                    if status is DeploymentStatus.SUCCEEDED
                    else [
                        f"[{created:%H:%M:%S}] applying changes",
                        f"[{created:%H:%M:%S}] health check failed: 2/3 targets unhealthy",
                        f"[{created:%H:%M:%S}] automatic rollback completed",
                    ],
                )
            )

    def seed_audit_history(self) -> None:
        if not self._settings.seed_demo_data:
            return
        now = utcnow()
        events = [
            ("admin@hccp.io", "settings.rotate_signing_key", "control-plane", "success", 3),
            ("approver@hccp.io", "deployment.approve", "dep-prod-2.14.0", "success", 26),
            ("operator@hccp.io", "deployment.create", "dep-prod-2.14.0", "success", 27),
            ("operator@hccp.io", "drift.run", "environment:prod", "success", 30),
            ("operator@hccp.io", "compliance.scan", "environment:prod", "success", 31),
            ("viewer@hccp.io", "auth.login", "control-plane", "success", 40),
            ("operator@hccp.io", "deployment.rollback", "dep-prod-2.13.4", "success", 120),
            ("unknown@external", "auth.login", "control-plane", "failure", 121),
        ]
        for email, action, target, outcome, minutes_ago in reversed(events):
            timestamp = now - timedelta(minutes=minutes_ago)
            self.append_audit(
                AuditEvent(
                    id=_id("evt"),
                    timestamp=timestamp,
                    actor_id="usr-seed",
                    actor_email=email,
                    action=action,
                    target=target,
                    outcome=outcome,
                    source_ip="10.0.1.24" if outcome == "success" else "203.0.113.77",
                )
            )


def new_id(prefix: str) -> str:
    return _id(prefix)


__all__ = ["Store", "new_id", "datetime"]
