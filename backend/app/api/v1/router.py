"""Aggregate v1 router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import audit, auth, compliance, dashboard, deployments, drift, resources, servers, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(resources.router)
api_router.include_router(deployments.router)
api_router.include_router(compliance.router)
api_router.include_router(drift.router)
api_router.include_router(servers.router)
api_router.include_router(audit.router)
api_router.include_router(users.router)


@api_router.get("/meta", tags=["meta"], summary="Control plane metadata")
def meta() -> dict:
    from app.core.rbac import ROLE_PERMISSIONS

    return {
        "roles": {
            role.value: sorted(permission.value for permission in permissions)
            for role, permissions in ROLE_PERMISSIONS.items()
        },
        "components": [
            "terraform",
            "ansible",
            "fastapi",
            "react",
            "github-actions",
        ],
    }
