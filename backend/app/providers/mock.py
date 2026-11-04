"""Deterministic in-memory provider used for local dev, CI and demos."""

from __future__ import annotations

import copy
import time

from app.providers.base import ProviderHealth
from app.providers.fixtures import build_inventory
from app.schemas import Environment, Resource


class MockProvider:
    name = "mock"

    def __init__(self, region: str = "ap-south-1") -> None:
        self.region = region
        self._resources: list[Resource] = build_inventory()

    def list_resources(self, environment: Environment | None = None) -> list[Resource]:
        if environment is None:
            return copy.deepcopy(self._resources)
        target = Environment(environment)
        return [copy.deepcopy(r) for r in self._resources if r.environment == target.value]

    def get_resource(self, resource_id: str) -> Resource | None:
        for resource in self._resources:
            if resource.id == resource_id:
                return copy.deepcopy(resource)
        return None

    def health(self) -> ProviderHealth:
        started = time.perf_counter()
        return ProviderHealth(
            provider=self.name,
            reachable=True,
            region=self.region,
            detail="deterministic fixture provider",
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
        )
