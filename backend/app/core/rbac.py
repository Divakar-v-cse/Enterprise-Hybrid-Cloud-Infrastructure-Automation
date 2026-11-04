"""Role based access control definitions.

Roles are intentionally coarse grained (viewer -> operator -> approver ->
admin) so that separation-of-duties is enforceable: the identity that
*requests* a production deployment can never be the identity that *approves*
it, even with the approver role.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    APPROVER = "approver"
    ADMIN = "admin"


class Permission(StrEnum):
    INFRA_READ = "infrastructure:read"
    DEPLOYMENT_READ = "deployment:read"
    DEPLOYMENT_CREATE = "deployment:create"
    DEPLOYMENT_APPROVE = "deployment:approve"
    DEPLOYMENT_ROLLBACK = "deployment:rollback"
    COMPLIANCE_READ = "compliance:read"
    COMPLIANCE_SCAN = "compliance:scan"
    DRIFT_READ = "drift:read"
    DRIFT_RUN = "drift:run"
    AUDIT_READ = "audit:read"
    USER_READ = "user:read"
    USER_MANAGE = "user:manage"


_VIEWER: frozenset[Permission] = frozenset(
    {
        Permission.INFRA_READ,
        Permission.DEPLOYMENT_READ,
        Permission.COMPLIANCE_READ,
        Permission.DRIFT_READ,
        Permission.AUDIT_READ,
    }
)

_OPERATOR: frozenset[Permission] = _VIEWER | {
    Permission.DEPLOYMENT_CREATE,
    Permission.COMPLIANCE_SCAN,
    Permission.DRIFT_RUN,
}

_APPROVER: frozenset[Permission] = _OPERATOR | {
    Permission.DEPLOYMENT_APPROVE,
    Permission.DEPLOYMENT_ROLLBACK,
}

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: _VIEWER,
    Role.OPERATOR: _OPERATOR,
    Role.APPROVER: _APPROVER,
    Role.ADMIN: frozenset(Permission),
}


def permissions_for(role: str | Role) -> frozenset[Permission]:
    """Return the permission set for a role, tolerating unknown roles."""
    try:
        return ROLE_PERMISSIONS[Role(role)]
    except (ValueError, KeyError):
        return frozenset()


def role_has_permission(role: str | Role, permission: Permission) -> bool:
    return permission in permissions_for(role)
