#!/usr/bin/env python3
"""Evaluate the policy-as-code baseline and emit a report.

Used by the scheduled compliance workflow and available locally:

    python scripts/compliance_report.py --provider mock --format markdown
    python scripts/compliance_report.py --provider aws --fail-on-critical

Exit codes: 0 within policy, 1 critical findings present, 2 execution error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import Settings  # noqa: E402
from app.db.store import Store  # noqa: E402
from app.providers.aws import AWSProvider  # noqa: E402
from app.providers.mock import MockProvider  # noqa: E402
from app.schemas import Environment, FindingStatus, Severity  # noqa: E402
from app.services import compliance  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["mock", "aws"], default="mock")
    parser.add_argument("--region", default="ap-south-1")
    parser.add_argument("--environment", choices=["dev", "prod", "all"], default="all")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--fail-on-critical", action="store_true")
    args = parser.parse_args()

    provider = (
        AWSProvider(region=args.region) if args.provider == "aws" else MockProvider(region=args.region)
    )
    try:
        resources = provider.list_resources()
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"error: unable to read inventory from {args.provider}: {exc}", file=sys.stderr)
        return 2

    store = Store(Settings(seed_demo_data=False, environment="local"))
    store.replace_inventory(resources)

    environment = None if args.environment == "all" else Environment(args.environment)
    result = compliance.scan(store, environment)
    failures = [finding for finding in result.findings if finding.status is FindingStatus.FAIL]
    critical = [finding for finding in failures if finding.severity is Severity.CRITICAL]

    if args.format == "json":
        rendered = json.dumps(
            {
                "provider": args.provider,
                "evaluated": result.evaluated,
                "passed": result.passed,
                "failed": result.failed,
                "score": result.score,
                "findings": [
                    {
                        "rule": finding.rule_id,
                        "resource": finding.resource_name,
                        "environment": finding.environment,
                        "severity": finding.severity,
                        "title": finding.title,
                        "remediation": finding.remediation,
                    }
                    for finding in failures
                ],
            },
            indent=2,
        )
    elif args.format == "markdown":
        lines = [
            "## Compliance report",
            "",
            f"- Provider: **{args.provider}**",
            f"- Controls evaluated: **{result.evaluated}**",
            f"- Passed: **{result.passed}**",
            f"- Failed: **{result.failed}**",
            f"- Weighted score: **{result.score}%**",
            "",
        ]
        if failures:
            lines += ["| Severity | Control | Resource | Finding |", "|---|---|---|---|"]
            for finding in failures:
                lines.append(
                    f"| {finding.severity} | `{finding.rule_id}` | `{finding.resource_name}` | "
                    f"{finding.description} |"
                )
        else:
            lines.append("No failing controls.")
        rendered = "\n".join(lines)
    else:
        lines = [f"Compliance score: {result.score}% ({result.passed}/{result.evaluated} controls passing)"]
        for finding in failures:
            lines.append(
                f"  [{finding.severity.upper()}] {finding.rule_id} {finding.resource_name}: "
                f"{finding.description}"
            )
        rendered = "\n".join(lines)

    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")

    if args.fail_on_critical and critical:
        print(f"\n{len(critical)} critical finding(s) present", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
