"""Cloud provider abstraction.

The control plane never talks to boto3 directly: it depends on this narrow
protocol. That keeps the API testable without credentials and makes adding a
second cloud (Azure/GCP) a matter of implementing four methods.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.schemas import Environment, Resource


@dataclass(frozen=True)
class ProviderHealth:
    provider: str
    reachable: bool
    region: str
    detail: str = ""
    latency_ms: float | None = None


@runtime_checkable
class CloudProvider(Protocol):
    name: str
    region: str

    def list_resources(self, environment: Environment | None = None) -> list[Resource]:
        """Return every managed resource, optionally filtered by environment."""

    def get_resource(self, resource_id: str) -> Resource | None:
        """Return a single resource or ``None``."""

    def health(self) -> ProviderHealth:
        """Cheap reachability probe used by ``/readyz``."""


class ProviderError(RuntimeError):
    """Raised when the upstream cloud API cannot satisfy a request."""
