#!/usr/bin/env python3
"""Run every local validation gate in one command.

    python scripts/validate_all.py              # everything that is installed
    python scripts/validate_all.py --fast       # skip frontend build + backend coverage
    python scripts/validate_all.py --skip frontend

The script never calls AWS. Terraform runs with `-backend=false`, Ansible is
checked statically, and the API suite uses the deterministic mock provider.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def resolve(executable: str) -> str:
    """Resolve npm/npx on Windows, where they are .cmd shims."""
    for candidate in (executable, f"{executable}.cmd", f"{executable}.exe"):
        found = shutil.which(candidate)
        if found:
            return found
    return executable


NPM = resolve("npm")


def run(label: str, command: list[str], cwd: Path) -> tuple[str, bool, float, str]:
    started = time.perf_counter()
    print(f"\n==> {label}")
    print(f"    {' '.join(command)}")
    process = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    duration = time.perf_counter() - started
    output = (process.stdout or "") + (process.stderr or "")
    tail = "\n".join(output.strip().splitlines()[-12:])
    status = process.returncode == 0
    print(tail if tail else "    (no output)")
    return label, status, duration, tail


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fast", action="store_true", help="skip the frontend production build")
    parser.add_argument(
        "--skip",
        nargs="*",
        default=[],
        choices=["terraform", "ansible", "backend", "frontend"],
        help="components to skip",
    )
    args = parser.parse_args()

    results: list[tuple[str, bool, float, str]] = []

    if "ansible" not in args.skip:
        results.append(
            run("Ansible static validation", [PYTHON, "scripts/validate_ansible.py"], ROOT)
        )

    if "backend" not in args.skip:
        results.append(
            run(
                "Backend test suite",
                [PYTHON, "-m", "pytest", "-q", "--cov=app", "--cov-report=term:skip-covered"],
                ROOT / "backend",
            )
        )

    if "terraform" not in args.skip:
        results.append(
            run("Terraform format and validate", [PYTHON, "scripts/validate_terraform.py"], ROOT)
        )

    if "frontend" not in args.skip and (ROOT / "frontend" / "node_modules").exists():
        results.append(run("Frontend typecheck", [NPM, "run", "typecheck"], ROOT / "frontend"))
        results.append(run("Frontend unit tests", [NPM, "test"], ROOT / "frontend"))
        if not args.fast:
            results.append(run("Frontend production build", [NPM, "run", "build"], ROOT / "frontend"))
    elif "frontend" not in args.skip:
        print("\n==> Frontend: node_modules missing, run `npm install` in frontend/ to enable")

    print("\n" + "=" * 68)
    print(f"{'COMPONENT':<34}{'RESULT':<10}DURATION")
    print("-" * 68)
    for label, status, duration, _ in results:
        print(f"{label:<34}{'PASS' if status else 'FAIL':<10}{duration:6.1f}s")
    print("=" * 68)

    failed = [label for label, status, _, _ in results if not status]
    if failed:
        print(f"{len(failed)} check(s) failed: {', '.join(failed)}")
        return 1
    print("All validation gates passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
