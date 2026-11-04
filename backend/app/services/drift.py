"""Configuration drift detection.

Terraform guarantees the *declared* state is applied; it does not tell you
when somebody changes the account afterwards. This module compares the
committed desired-state contract against live provider inventory and emits a
machine readable report that CI publishes and the dashboard renders.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from app.db.store import Store
from app.schemas import DriftItem, DriftReport, Environment, Resource, Severity

DEFAULT_DESIRED_STATE = Path(__file__).resolve().parents[1] / "data" / "desired_state.json"

_KIND_SEVERITY = {
    "security_group": Severity.CRITICAL,
    "iam_role": Severity.HIGH,
    "ec2": Severity.HIGH,
    "load_balancer": Severity.HIGH,
    "vpc": Severity.HIGH,
    "target_group": Severity.MEDIUM,
}

_MISSING_SEVERITY = {
    "ec2": Severity.CRITICAL,
    "load_balancer": Severity.CRITICAL,
    "security_group": Severity.HIGH,
    "iam_role": Severity.HIGH,
}


def load_desired_state(path: Path | str | None = None) -> dict[str, Any]:
    target = Path(path) if path else DEFAULT_DESIRED_STATE
    with target.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalise(value: Any) -> Any:
    """Make config values comparable regardless of ordering/type."""
    if isinstance(value, list):
        normalised = [_normalise(item) for item in value]
        # Ingress/egress rules are sets, not ordered lists.
        if all(isinstance(item, dict) for item in normalised):
            return sorted(
                (
                    f"{item.get('protocol', '')}:{item.get('from_port', '')}:{item.get('to_port', '')}"
                    f":{item.get('cidr') or ('sg=' + str(item.get('source_sg')) if item.get('source_sg') else '*')}"
                )
                for item in normalised
            )
        return sorted(str(item) for item in normalised)
    if isinstance(value, dict):
        return {key: _normalise(item) for key, item in sorted(value.items())}
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _describe(value: Any) -> str:
    """Render a value compactly enough for a table cell."""
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        rules = []
        for item in value:
            source = item.get("cidr") or (
                f"sg={item.get('source_sg')}" if item.get("source_sg") else "*"
            )
            rules.append(
                f"{item.get('protocol', '-1')}/{item.get('from_port', '*')}-{item.get('to_port', '*')}<-{source}"
            )
        return f"{len(value)} rule(s): " + ", ".join(sorted(rules))
    if isinstance(value, dict | list):
        return json.dumps(value, sort_keys=True, default=str)
    return str(value)


def compare(
    resources: Iterable[Resource], desired: dict[str, Any], environment: Environment
) -> DriftReport:
    """Pure comparison used by both the API and the CLI (no side effects)."""
    inventory = {r.name: r for r in resources if r.environment == environment}
    declared = desired.get("environments", {}).get(environment.value, [])
    managed_kinds = {entry["kind"] for entry in declared}
    declared_names = {entry["name"] for entry in declared}
    items: list[DriftItem] = []
    checked = 0

    for entry in declared:
        checked += 1
        name = entry["name"]
        kind = entry["kind"]
        actual = inventory.get(name)
        if actual is None:
            items.append(
                DriftItem(
                    resource_name=name,
                    kind=kind,
                    environment=environment,
                    drift_type="missing",
                    expected="present",
                    actual="absent",
                    severity=_MISSING_SEVERITY.get(kind, Severity.MEDIUM),
                )
            )
            continue

        for key, expected_value in (entry.get("config") or {}).items():
            actual_value = actual.config.get(key)
            if _normalise(actual_value) != _normalise(expected_value):
                items.append(
                    DriftItem(
                        resource_name=name,
                        kind=kind,
                        environment=environment,
                        drift_type="modified",
                        expected=f"{key}={_describe(expected_value)}",
                        actual=f"{key}={_describe(actual_value)}",
                        severity=_KIND_SEVERITY.get(kind, Severity.MEDIUM),
                    )
                )

        for key, expected_value in (entry.get("tags") or {}).items():
            actual_value = actual.tags.get(key, "")
            if str(actual_value) != str(expected_value):
                items.append(
                    DriftItem(
                        resource_name=name,
                        kind=kind,
                        environment=environment,
                        drift_type="unmanaged_tag",
                        expected=f"{key}={expected_value}",
                        actual=f"{key}={actual_value or '<missing>'}",
                        severity=Severity.LOW,
                    )
                )

    for resource in inventory.values():
        if resource.name in declared_names:
            continue
        if resource.kind not in managed_kinds:
            continue
        items.append(
            DriftItem(
                resource_name=resource.name,
                kind=resource.kind,
                environment=environment,
                drift_type="unexpected",
                expected="absent",
                actual="present",
                severity=Severity.MEDIUM,
            )
        )

    severity_rank = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
    }
    items.sort(key=lambda item: (severity_rank[item.severity], item.resource_name))

    return DriftReport(
        environment=environment,
        provider="desired-state-contract",
        checked_resources=checked,
        drift_detected=bool(items),
        items=items,
    )


def detect(
    store: Store,
    environment: Environment,
    *,
    desired_path: Path | str | None = None,
) -> DriftReport:
    desired = load_desired_state(desired_path)
    return compare(store.list_resources(), desired, Environment(environment))


def to_markdown(report: DriftReport) -> str:
    """Render a report for GitHub step summaries."""
    lines = [
        f"## Drift report - {report.environment.value}",
        "",
        f"- Checked resources: **{report.checked_resources}**",
        f"- Drifted resources: **{report.drifted_resources}**",
        f"- Status: **{'DRIFT DETECTED' if report.drift_detected else 'in sync'}**",
        "",
    ]
    if report.items:
        lines += ["| Severity | Resource | Type | Expected | Actual |", "|---|---|---|---|---|"]
        for item in report.items:
            lines.append(
                f"| {item.severity} | `{item.resource_name}` | {item.drift_type} | "
                f"{item.expected} | {item.actual} |"
            )
    return "\n".join(lines)
