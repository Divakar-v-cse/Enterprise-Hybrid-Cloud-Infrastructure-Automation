"""FastAPI application factory for the Hybrid Cloud Control Plane."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware
from app.db.store import Store
from app.providers.aws import AWSProvider
from app.providers.base import CloudProvider
from app.providers.mock import MockProvider
from app.schemas import Environment
from app.services import compliance, drift

logger = get_logger("app.startup")

TAGS_METADATA = [
    {"name": "auth", "description": "JWT authentication, refresh rotation and RBAC profile."},
    {"name": "dashboard", "description": "Aggregated posture and delivery metrics."},
    {"name": "infrastructure", "description": "Read-only inventory sourced from the cloud provider."},
    {"name": "deployments", "description": "Deployment intent, approval gate and rollback."},
    {"name": "compliance", "description": "Policy-as-code evaluation and exceptions."},
    {"name": "drift", "description": "Desired-state contract versus live infrastructure."},
    {"name": "servers", "description": "Linux and Windows fleet health."},
    {"name": "audit", "description": "Immutable, queryable audit trail."},
    {"name": "users", "description": "Account and role administration."},
]


def build_provider(settings: Settings) -> CloudProvider:
    if settings.provider == "aws":
        return AWSProvider(region=settings.aws_region, profile=settings.aws_profile)
    return MockProvider(region=settings.aws_region)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.environment, service="hccp-api")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        task: asyncio.Task | None = None
        interval = app.state.settings.drift_interval_seconds
        if interval > 0:

            async def _loop() -> None:
                while True:
                    await asyncio.sleep(interval)
                    for env in Environment:
                        try:
                            report = drift.detect(app.state.store, env)
                            app.state.drift_cache[env.value] = report
                            if report.drift_detected:
                                logger.warning(
                                    "drift detected by scheduler",
                                    extra={
                                        "environment": env.value,
                                        "drifted": report.drifted_resources,
                                    },
                                )
                        except Exception:  # noqa: BLE001 - keep the scheduler alive
                            logger.exception("scheduled drift run failed")

            task = asyncio.create_task(_loop(), name="drift-scheduler")

        logger.info(
            "control plane started",
            extra={
                "environment": settings.environment,
                "provider": app.state.provider.name,
                "resources": len(app.state.store.list_resources()),
            },
        )
        try:
            yield
        finally:
            if task is not None:
                task.cancel()

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description=(
            "Control plane for the Enterprise Hybrid Cloud Infrastructure Automation "
            "platform. Terraform owns infrastructure, Ansible owns configuration and "
            "this service provides inventory, compliance, drift and delivery visibility."
        ),
        openapi_tags=TAGS_METADATA,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-Response-Time-Ms"],
        max_age=600,
    )
    register_exception_handlers(app)

    store = Store(settings)
    provider = build_provider(settings)
    try:
        store.replace_inventory(provider.list_resources())
    except Exception:  # noqa: BLE001 - start degraded rather than crash-looping
        logger.exception("initial inventory load failed; starting with an empty inventory")
    store.seed_deployment_history()
    store.seed_audit_history()
    initial_scan = compliance.scan(store)
    store.replace_findings(initial_scan.findings)

    app.state.settings = settings
    app.state.store = store
    app.state.provider = provider
    app.state.drift_cache = {}

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", tags=["meta"], summary="Service descriptor")
    def root() -> dict:
        return {
            "service": settings.app_name,
            "version": settings.version,
            "environment": settings.environment,
            "provider": provider.name,
            "api": settings.api_v1_prefix,
            "docs": "/docs" if not settings.is_production else None,
        }

    @app.get("/healthz", tags=["meta"], summary="Liveness probe")
    def healthz() -> dict:
        return {"status": "ok", "version": settings.version}

    @app.get("/readyz", tags=["meta"], summary="Readiness probe")
    def readyz():
        provider_health = provider.health()
        store = app.state.store
        ready = provider_health.reachable and len(store.list_resources()) > 0
        payload = {
            "status": "ready" if ready else "degraded",
            "provider": {
                "name": provider_health.provider,
                "reachable": provider_health.reachable,
                "region": provider_health.region,
                "latency_ms": provider_health.latency_ms,
            },
            "resources": len(store.list_resources()),
            "findings": len(store.list_findings()),
        }
        return JSONResponse(status_code=200 if ready else 503, content=payload)

    return app


app = create_app()
