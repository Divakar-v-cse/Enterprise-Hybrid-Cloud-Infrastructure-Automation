"""Pydantic schemas shared by the API layer and the persistence adapters."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.rbac import Role


def utcnow() -> datetime:
    return datetime.now(UTC)


class Environment(StrEnum):
    DEV = "dev"
    PROD = "prod"


class ResourceKind(StrEnum):
    VPC = "vpc"
    SUBNET = "subnet"
    ROUTE_TABLE = "route_table"
    SECURITY_GROUP = "security_group"
    IAM_ROLE = "iam_role"
    EC2 = "ec2"
    LOAD_BALANCER = "load_balancer"
    TARGET_GROUP = "target_group"


class ResourceStatus(StrEnum):
    AVAILABLE = "available"
    RUNNING = "running"
    STOPPED = "stopped"
    DEGRADED = "degraded"
    PENDING = "pending"


class DeploymentStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"


class DeploymentComponent(StrEnum):
    NETWORK = "network"
    COMPUTE = "compute"
    CONFIGURATION = "configuration"
    APPLICATION = "application"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FindingStatus(StrEnum):
    FAIL = "fail"
    PASS = "pass"
    WAIVED = "waived"


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class PatchStatus(StrEnum):
    COMPLIANT = "compliant"
    PENDING = "pending"
    OVERDUE = "overdue"


class HealthSnapshot(BaseModel):
    score: int = Field(ge=0, le=100)
    status: HealthStatus
    cpu_percent: float = Field(ge=0, le=100)
    memory_percent: float = Field(ge=0, le=100)
    disk_percent: float = Field(ge=0, le=100)
    patch_status: PatchStatus
    agent_version: str
    uptime_hours: int = Field(ge=0)
    last_seen: datetime = Field(default_factory=utcnow)


class Resource(BaseModel):
    id: str
    name: str
    kind: ResourceKind
    environment: Environment
    region: str
    status: ResourceStatus
    owner: str
    monthly_cost_usd: float = Field(ge=0)
    created_at: datetime = Field(default_factory=utcnow)
    tags: dict[str, str] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    health: HealthSnapshot | None = None

    @property
    def is_compute(self) -> bool:
        return self.kind == ResourceKind.EC2

    @property
    def operating_system(self) -> str | None:
        value = self.config.get("os")
        return str(value) if value else None


class User(BaseModel):
    id: str
    email: str
    full_name: str
    role: Role
    is_active: bool = True
    mfa_enabled: bool = True
    password_hash: str = Field(exclude=True, repr=False)
    created_at: datetime = Field(default_factory=utcnow)
    last_login_at: datetime | None = None

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        return value.strip().lower()


class Deployment(BaseModel):
    id: str
    environment: Environment
    component: DeploymentComponent
    version: str
    status: DeploymentStatus
    requested_by: str
    requested_by_email: str
    approved_by: str | None = None
    change_summary: str
    risk_level: Severity = Severity.LOW
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    rollback_of: str | None = None
    logs: list[str] = Field(default_factory=list)

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            DeploymentStatus.SUCCEEDED,
            DeploymentStatus.FAILED,
            DeploymentStatus.REJECTED,
            DeploymentStatus.ROLLED_BACK,
        }


class ComplianceFinding(BaseModel):
    id: str
    rule_id: str
    title: str
    category: str
    severity: Severity
    status: FindingStatus
    resource_id: str
    resource_name: str
    environment: Environment
    description: str
    remediation: str
    detected_at: datetime = Field(default_factory=utcnow)


class AuditEvent(BaseModel):
    id: str
    timestamp: datetime = Field(default_factory=utcnow)
    actor_id: str
    actor_email: str
    action: str
    target: str
    environment: str | None = None
    outcome: str = "success"
    source_ip: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class DriftItem(BaseModel):
    resource_name: str
    kind: str
    environment: Environment
    drift_type: str  # missing | unexpected | modified | unmanaged_tag
    expected: str | None = None
    actual: str | None = None
    severity: Severity = Severity.MEDIUM


class DriftReport(BaseModel):
    generated_at: datetime = Field(default_factory=utcnow)
    environment: Environment
    provider: str
    checked_resources: int
    drift_detected: bool
    items: list[DriftItem] = Field(default_factory=list)

    @property
    def drifted_resources(self) -> int:
        return len({item.resource_name for item in self.items})


# ---------------------------------------------------------------------------
# Request / response payloads
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserPublic(BaseModel):
    id: str
    email: str
    full_name: str
    role: Role
    is_active: bool
    mfa_enabled: bool
    last_login_at: datetime | None = None
    permissions: list[str] = Field(default_factory=list)


class LoginResponse(TokenPair):
    user: UserPublic


class RoleUpdateRequest(BaseModel):
    role: Role


class UserCreateRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    role: Role = Role.VIEWER
    password: str = Field(min_length=10, max_length=256)
    mfa_enabled: bool = True


class DeploymentCreateRequest(BaseModel):
    environment: Environment
    component: DeploymentComponent
    version: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._/-]+$")
    change_summary: str = Field(min_length=10, max_length=500)
    risk_level: Severity = Severity.LOW


class DeploymentActionRequest(BaseModel):
    reason: str = Field(default="", max_length=500)


class ScanRequest(BaseModel):
    environment: Environment | None = None


class EnvironmentSummary(BaseModel):
    environment: Environment
    resources: int
    monthly_cost_usd: float
    servers: int
    healthy_servers: int
    open_findings: int
    critical_findings: int
    last_deployment: datetime | None = None
    last_deployment_status: str | None = None


class DashboardSummary(BaseModel):
    generated_at: datetime = Field(default_factory=utcnow)
    provider: str
    total_resources: int
    total_monthly_cost_usd: float
    servers_total: int
    servers_healthy: int
    servers_warning: int
    servers_critical: int
    open_findings: int
    critical_findings: int
    compliance_score: float
    pending_approvals: int
    environments: list[EnvironmentSummary]
    cost_by_kind: dict[str, float]
    findings_by_severity: dict[str, int]


class AuditPage(BaseModel):
    items: list[AuditEvent]
    total: int
    limit: int
    offset: int


class Page(BaseModel):
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int
