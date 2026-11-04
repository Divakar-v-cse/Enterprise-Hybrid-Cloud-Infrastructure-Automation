#!/usr/bin/env python3
"""Compare live infrastructure against the committed desired-state contract.

Examples
--------
    python scripts/drift_detect.py --provider mock
    python scripts/drift_detect.py --provider aws --environment prod --fail-on-drift
    python scripts/drift_detect.py --format markdown --output drift.md

Exit codes: 0 in sync, 1 drift detected (with --fail-on-drift), 2 execution error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.providers.aws import AWSProvider  # noqa: E402
from app.providers.mock import MockProvider  # noqa: E402
from app.schemas import Environment  # noqa: E402
from app.services.drift import compare, load_desired_state, to_markdown  # noqa: E402

SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", choices=["mock", "aws"], default="mock")
    parser.add_argument("--region", default="ap-south-1")
    parser.add_argument("--environment", choices=["dev", "prod", "all"], default="all")
    parser.add_argument("--desired", type=Path, default=None, help="Path to desired_state.json")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--min-severity",
        choices=["critical", "high", "medium", "low"],
        default="low",
        help="Ignore drift items below this severity when deciding the exit code",
    )
    parser.add_argument("--fail-on-drift", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    provider = (
        AWSProvider(region=args.region) if args.provider == "aws" else MockProvider(region=args.region)
    )
    try:
        resources = provider.list_resources()
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"error: unable to read inventory from {args.provider}: {exc}", file=sys.stderr)
        return 2

    desired = load_desired_state(args.desired)
    environments = list(Environment) if args.environment == "all" else [Environment(args.environment)]
    reports = [compare(resources, desired, environment) for environment in environments]

    blocking = [
        item
        for report in reports
        for item in report.items
        if SEVERITY_RANK[item.severity] <= SEVERITY_RANK[args.min_severity]
    ]

    if args.format == "json":
        payload = json.dumps(
            {
                "provider": args.provider,
                "reports": [report.model_dump(mode="json") for report in reports],
                "blocking_items": len(blocking),
            },
            indent=2,
        )
        rendered = payload
    elif args.format == "markdown":
        rendered = "\n\n".join(to_markdown(report) for report in reports)
    else:
        lines = []
        for report in reports:
            lines.append(
                f"[{report.environment.value}] checked={report.checked_resources} "
                f"drift_items={len(report.items)} status="
                f"{'DRIFT' if report.drift_detected else 'in-sync'}"
            )
            for item in report.items:
                lines.append(
                    f"  - {item.severity.upper():8} {item.drift_type:12} {item.resource_name}: "
                    f"{item.expected} -> {item.actual}"
                )
        rendered = "\n".join(lines)

    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"\nreport written to {args.output}", file=sys.stderr)

    if args.fail_on_drift and blocking:
        print(f"\n{len(blocking)} drift item(s) at or above '{args.min_severity}'", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
