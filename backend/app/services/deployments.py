"""Deployment orchestration and state machine.

The control plane does not run Terraform itself; it records intent, enforces
separation of duties, triggers the pipeline and tracks the outcome. The
``PipelineRunner`` seam is where a real GitHub Actions dispatch / CodePipeline
call is plugged in.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Protocol

from app.core.errors import ConflictError, NotFoundError, PermissionDenied
from app.db.store import Store, new_id
from app.schemas import (
    Deployment,
    DeploymentComponent,
    DeploymentCreateRequest,
    DeploymentStatus,
    Environment,
    Severity,
    User,
    utcnow,
)
from app.services import audit

# Allowed transitions for the deployment state machine.
_TRANSITIONS: dict[DeploymentStatus, set[DeploymentStatus]] = {
    DeploymentStatus.PENDING_APPROVAL: {DeploymentStatus.APPROVED, DeploymentStatus.REJECTED},
    DeploymentStatus.APPROVED: {DeploymentStatus.IN_PROGRESS},
    DeploymentStatus.IN_PROGRESS: {DeploymentStatus.SUCCEEDED, DeploymentStatus.FAILED},
    DeploymentStatus.SUCCEEDED: {DeploymentStatus.ROLLED_BACK},
    DeploymentStatus.FAILED: set(),
    DeploymentStatus.REJECTED: set(),
    DeploymentStatus.ROLLED_BACK: set(),
}

_COMPONENT_STEPS: dict[DeploymentComponent, list[str]] = {
    DeploymentComponent.NETWORK: [
        "terraform plan -target=module.network",
        "terraform apply -auto-approve",
        "aws ec2 describe-route-tables --filters Name=tag:Environment,Values={env}",
    ],
    DeploymentComponent.COMPUTE: [
        "terraform plan -target=module.compute",
        "terraform apply -auto-approve",
        "aws elbv2 describe-target-health",
    ],
    DeploymentComponent.CONFIGURATION: [
        "ansible-playbook playbooks/site.yml --limit {env}",
        "ansible-playbook playbooks/validate.yml --limit {env}",
    ],
    DeploymentComponent.APPLICATION: [
        "docker build -t hccp/app:{version} .",
        "ansible-playbook playbooks/deploy_app.yml --limit {env}",
        "curl --fail https://{env}.hccp.internal/healthz",
    ],
}


class PipelineRunner(Protocol):
    def dispatch(self, deployment: Deployment) -> tuple[bool, list[str]]:
        """Run the pipeline. Returns ``(succeeded, log_lines)``."""


class SimulatedRunner:
    """Deterministic runner for local development and tests.

    A version containing ``fail`` intentionally fails so the failure and
    rollback paths can be exercised end to end without touching AWS.
    """

    def dispatch(self, deployment: Deployment) -> tuple[bool, list[str]]:
        env = deployment.environment
        steps = _COMPONENT_STEPS[deployment.component]
        logs: list[str] = [f"pipeline started for {deployment.component.value} -> {env}"]
        logs.extend(
            f"$ {step.format(env=env, version=deployment.version)}" for step in steps
        )
        failed = "fail" in deployment.version.lower()
        if failed:
            logs.append("ERROR health check failed: 2/3 targets unhealthy")
            logs.append("pipeline aborted - no further changes applied")
            return False, logs
        logs.append(f"pipeline completed: {len(steps)}/{len(steps)} steps succeeded")
        logs.append("post-deploy verification passed")
        return True, logs


def _require_transition(current: DeploymentStatus, target: DeploymentStatus) -> None:
    if target not in _TRANSITIONS[current]:
        raise ConflictError(
            f"Cannot move deployment from '{current}' to '{target}'.",
            details={"from": current, "to": target},
        )


def _dispatch(
    store: Store,
    deployment: Deployment,
    runner: PipelineRunner,
    actor: User,
) -> Deployment:
    _require_transition(deployment.status, DeploymentStatus.IN_PROGRESS)
    deployment = deployment.model_copy(
        update={
            "status": DeploymentStatus.IN_PROGRESS,
            "started_at": utcnow(),
            "updated_at": utcnow(),
        }
    )
    store.save_deployment(deployment)

    succeeded, logs = runner.dispatch(deployment)
    terminal = DeploymentStatus.SUCCEEDED if succeeded else DeploymentStatus.FAILED
    _require_transition(DeploymentStatus.IN_PROGRESS, terminal)
    deployment = deployment.model_copy(
        update={
            "status": terminal,
            "logs": logs,
            "completed_at": utcnow(),
            "updated_at": utcnow(),
        }
    )
    store.save_deployment(deployment)
    audit.record(
        store,
        actor=actor,
        action="deployment.run",
        target=deployment.id,
        environment=deployment.environment,
        outcome="success" if succeeded else "failure",
        details={"version": deployment.version, "component": deployment.component},
    )
    return deployment


def create(
    store: Store,
    request: DeploymentCreateRequest,
    actor: User,
    *,
    runner: PipelineRunner | None = None,
) -> Deployment:
    runner = runner or SimulatedRunner()
    environment = Environment(request.environment)

    # Production changes are always at least medium risk and always gated.
    risk = request.risk_level
    if environment is Environment.PROD and risk is Severity.LOW:
        risk = Severity.MEDIUM

    deployment = Deployment(
        id=new_id("dep"),
        environment=environment,
        component=request.component,
        version=request.version,
        # Non-prod rollouts are auto-approved but still traverse the state machine.
        status=DeploymentStatus.PENDING_APPROVAL
        if environment is Environment.PROD
        else DeploymentStatus.APPROVED,
        requested_by=actor.id,
        requested_by_email=actor.email,
        approved_by=None,
        change_summary=request.change_summary,
        risk_level=risk,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    store.add_deployment(deployment)
    audit.record(
        store,
        actor=actor,
        action="deployment.create",
        target=deployment.id,
        environment=environment,
        details={
            "component": request.component,
            "version": request.version,
            "risk": risk,
            "approval_required": environment is Environment.PROD,
        },
    )

    if environment is Environment.PROD:
        return deployment

    # Non-production rollouts run immediately, still through the state machine.
    return _dispatch(store, deployment, runner, actor)


def approve(
    store: Store,
    deployment_id: str,
    actor: User,
    *,
    reason: str = "",
    runner: PipelineRunner | None = None,
) -> Deployment:
    runner = runner or SimulatedRunner()
    deployment = store.get_deployment(deployment_id)
    if deployment is None:
        raise NotFoundError("Deployment not found.")

    if deployment.requested_by == actor.id:
        # Separation of duties: a requester can never self-approve.
        raise PermissionDenied(
            "Separation of duties: the requester cannot approve their own deployment."
        )
    if deployment.status is not DeploymentStatus.PENDING_APPROVAL:
        raise ConflictError(
            f"Deployment is '{deployment.status}', not awaiting approval."
        )

    _require_transition(deployment.status, DeploymentStatus.APPROVED)
    deployment = deployment.model_copy(
        update={
            "status": DeploymentStatus.APPROVED,
            "approved_by": actor.email,
            "updated_at": utcnow(),
        }
    )
    store.save_deployment(deployment)
    audit.record(
        store,
        actor=actor,
        action="deployment.approve",
        target=deployment.id,
        environment=deployment.environment,
        details={"reason": reason, "requested_by": deployment.requested_by_email},
    )
    return _dispatch(store, deployment, runner, actor)


def reject(store: Store, deployment_id: str, actor: User, *, reason: str = "") -> Deployment:
    deployment = store.get_deployment(deployment_id)
    if deployment is None:
        raise NotFoundError("Deployment not found.")
    if deployment.requested_by == actor.id:
        raise PermissionDenied("Separation of duties: the requester cannot review their own deployment.")
    _require_transition(deployment.status, DeploymentStatus.REJECTED)
    updated = deployment.model_copy(
        update={
            "status": DeploymentStatus.REJECTED,
            "approved_by": actor.email,
            "updated_at": utcnow(),
            "completed_at": utcnow(),
            "logs": deployment.logs + [f"rejected by {actor.email}: {reason or 'no reason given'}"],
        }
    )
    store.save_deployment(updated)
    audit.record(
        store,
        actor=actor,
        action="deployment.reject",
        target=deployment.id,
        environment=deployment.environment,
        details={"reason": reason},
    )
    return updated


def rollback(
    store: Store,
    deployment_id: str,
    actor: User,
    *,
    reason: str = "",
    runner: PipelineRunner | None = None,
) -> Deployment:
    runner = runner or SimulatedRunner()
    original = store.get_deployment(deployment_id)
    if original is None:
        raise NotFoundError("Deployment not found.")
    if original.status is not DeploymentStatus.SUCCEEDED:
        raise ConflictError("Only a succeeded deployment can be rolled back.")

    _require_transition(original.status, DeploymentStatus.ROLLED_BACK)
    rolled_back = original.model_copy(update={"status": DeploymentStatus.ROLLED_BACK, "updated_at": utcnow()})
    store.save_deployment(rolled_back)

    now = utcnow()
    rollback_deployment = Deployment(
        id=new_id("dep"),
        environment=original.environment,
        component=original.component,
        version=f"rollback-{original.version}",
        status=DeploymentStatus.APPROVED,
        requested_by=actor.id,
        requested_by_email=actor.email,
        approved_by=actor.email,
        change_summary=f"Rollback of {original.version}: {reason or 'operator initiated'}",
        risk_level=Severity.HIGH,
        created_at=now,
        updated_at=now,
        rollback_of=original.id,
    )
    store.add_deployment(rollback_deployment)
    result = _dispatch(store, rollback_deployment, runner, actor)
    audit.record(
        store,
        actor=actor,
        action="deployment.rollback",
        target=original.id,
        environment=original.environment,
        details={"reason": reason, "rollback_deployment": result.id},
    )
    return result


def timeline(store: Store, environment: Environment | None = None, limit: int = 20) -> list[Deployment]:
    deployments = store.list_deployments()
    if environment is not None:
        target = Environment(environment)
        deployments = [d for d in deployments if d.environment == target]
    return deployments[:limit]


def average_duration_minutes(store: Store) -> float:
    durations = [
        (d.completed_at - d.started_at).total_seconds() / 60
        for d in store.list_deployments()
        if d.completed_at and d.started_at and d.completed_at > d.started_at
    ]
    if not durations:
        return 0.0
    return round(sum(durations) / len(durations), 1)


def success_rate(store: Store) -> float:
    finished = [
        d
        for d in store.list_deployments()
        if d.status in {DeploymentStatus.SUCCEEDED, DeploymentStatus.FAILED, DeploymentStatus.ROLLED_BACK}
    ]
    if not finished:
        return 100.0
    good = sum(1 for d in finished if d.status is DeploymentStatus.SUCCEEDED)
    return round(100.0 * good / len(finished), 1)


__all__ = [
    "SimulatedRunner",
    "PipelineRunner",
    "create",
    "approve",
    "reject",
    "rollback",
    "timeline",
    "average_duration_minutes",
    "success_rate",
    "timedelta",
]
