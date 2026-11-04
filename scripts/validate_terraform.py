#!/usr/bin/env python3
"""Format and validate every Terraform root module without touching AWS."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERRAFORM_DIR = ROOT / "terraform"
ENVIRONMENTS = ["dev", "prod"]


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def main() -> int:
    if shutil.which("terraform") is None:
        print("terraform is not installed; skipping Terraform validation", file=sys.stderr)
        return 2

    failures = 0

    print("==> terraform fmt -check -recursive")
    fmt = run(["terraform", "fmt", "-check", "-recursive"], TERRAFORM_DIR)
    if fmt.returncode != 0:
        print(fmt.stdout or fmt.stderr)
        print("formatting issues found - run `terraform fmt -recursive`")
        failures += 1
    else:
        print("formatting clean")

    for environment in ENVIRONMENTS:
        directory = TERRAFORM_DIR / "environments" / environment
        print(f"==> {environment}: terraform init -backend=false")
        init = run(["terraform", "init", "-backend=false", "-input=false", "-no-color"], directory)
        if init.returncode != 0:
            print(init.stderr[-4000:])
            failures += 1
            continue

        print(f"==> {environment}: terraform validate")
        validate = run(["terraform", "validate", "-no-color"], directory)
        print(validate.stdout.strip() or validate.stderr.strip())
        if validate.returncode != 0:
            failures += 1

    if failures:
        print(f"\n{failures} Terraform check(s) failed")
        return 1
    print("\nAll Terraform checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
