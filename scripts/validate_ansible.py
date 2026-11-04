#!/usr/bin/env python3
"""Static validation for the Ansible tree.

Runs anywhere Python is available (including Windows, where Ansible itself is
not supported as a control node). It parses every YAML file, checks playbook
role references, include paths, template sources and inventory wiring, and
exits non-zero when something is broken.

CI additionally runs ansible-lint on an Ubuntu runner for semantic checks.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
ANSIBLE = ROOT / "ansible"
ERRORS: list[str] = []
WARNINGS: list[str] = []
CHECKED_YAML = 0


def load_yaml(path: Path) -> Any:
    global CHECKED_YAML
    try:
        documents = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    except yaml.YAMLError as exc:
        ERRORS.append(f"{path.relative_to(ROOT)}: invalid YAML - {exc}")
        return None
    CHECKED_YAML += 1
    return documents[0] if documents else None


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def check_playbook(path: Path) -> None:
    data = load_yaml(path)
    if data is None:
        return
    if not isinstance(data, list):
        ERRORS.append(f"{rel(path)}: a playbook must be a list of plays")
        return

    for index, play in enumerate(data, start=1):
        if not isinstance(play, dict):
            ERRORS.append(f"{rel(path)}: play #{index} is not a mapping")
            continue
        import_key = next(
            (key for key in play if key.split(".")[-1] == "import_playbook"), None
        )
        if import_key is not None:
            target = ANSIBLE / "playbooks" / str(play[import_key])
            if not target.exists():
                ERRORS.append(f"{rel(path)}: imported playbook {play[import_key]} not found")
            continue
        if "hosts" not in play:
            ERRORS.append(f"{rel(path)}: play #{index} has no hosts")
        for role_entry in play.get("roles", []) or []:
            name = role_entry if isinstance(role_entry, str) else role_entry.get("role")
            if not name:
                ERRORS.append(f"{rel(path)}: malformed role entry {role_entry!r}")
                continue
            if not (ANSIBLE / "roles" / str(name) / "tasks" / "main.yml").exists():
                ERRORS.append(f"{rel(path)}: role '{name}' has no tasks/main.yml")


def check_role(role_dir: Path) -> None:
    role_name = role_dir.name
    tasks_file = role_dir / "tasks" / "main.yml"
    if not tasks_file.exists():
        ERRORS.append(f"ansible/roles/{role_name}: missing tasks/main.yml")
        return

    for task_file in (role_dir / "tasks").glob("*.yml"):
        data = load_yaml(task_file)
        if data is None:
            continue
        if not isinstance(data, list):
            ERRORS.append(f"{rel(task_file)}: tasks must be a list")
            continue
        for task in data:
            if not isinstance(task, dict):
                continue
            for key, value in task.items():
                if key in {"include_tasks", "import_tasks"}:
                    target = (task_file.parent / str(value)).resolve()
                    if not target.exists():
                        ERRORS.append(f"{rel(task_file)}: included file {value} not found")
                if key in {"template", "win_template"} and isinstance(value, dict):
                    src = value.get("src")
                    if src and "{{" not in str(src):
                        if not (role_dir / "templates" / str(src)).exists():
                            ERRORS.append(f"{rel(task_file)}: template '{src}' missing in {role_name}/templates")
                if key in {"copy", "win_copy", "script"} and isinstance(value, dict):
                    src = value.get("src")
                    if src and "{{" not in str(src):
                        candidate = role_dir / "files" / str(src)
                        if not candidate.exists():
                            WARNINGS.append(f"{rel(task_file)}: file '{src}' missing in {role_name}/files")

    handlers = role_dir / "handlers" / "main.yml"
    if handlers.exists():
        data = load_yaml(handlers)
        if data is not None and not isinstance(data, list):
            ERRORS.append(f"{rel(handlers)}: handlers must be a list")


def check_inventory(path: Path) -> None:
    data = load_yaml(path)
    if not isinstance(data, dict) or "all" not in data:
        ERRORS.append(f"{rel(path)}: inventory must define an 'all' group")
        return
    children = data["all"].get("children", {}) or {}
    for required in ("linux", "windows"):
        if required not in children:
            ERRORS.append(f"{rel(path)}: missing '{required}' host group")
        elif not (children[required] or {}).get("hosts"):
            ERRORS.append(f"{rel(path)}: group '{required}' has no hosts")


def check_cfg() -> None:
    cfg = ANSIBLE / "ansible.cfg"
    if not cfg.exists():
        ERRORS.append("ansible/ansible.cfg is missing")
        return
    text = cfg.read_text(encoding="utf-8")
    for section in ("[defaults]", "[privilege_escalation]", "[ssh_connection]"):
        if section not in text:
            ERRORS.append(f"ansible.cfg: missing {section}")
    inventory = ANSIBLE / "inventories" / "dev" / "hosts.yml"
    if not inventory.exists():
        ERRORS.append("ansible/inventories/dev/hosts.yml is missing")


def main() -> int:
    if not ANSIBLE.exists():
        print("ansible/ directory not found", file=sys.stderr)
        return 1

    check_cfg()

    for path in sorted(ANSIBLE.rglob("*.yml")):
        if any(part in {"collections", ".cache"} for part in path.parts):
            continue
        if path.parent == ANSIBLE / "playbooks":
            check_playbook(path)
        elif "roles" in path.parts:
            continue
        else:
            load_yaml(path)

    roles_dir = ANSIBLE / "roles"
    roles = sorted(p for p in roles_dir.iterdir() if p.is_dir()) if roles_dir.exists() else []
    for role in roles:
        check_role(role)

    for inventory in (ANSIBLE / "inventories").glob("*/hosts.yml"):
        check_inventory(inventory)

    print(f"Parsed {CHECKED_YAML} YAML documents across {len(roles)} roles")
    for warning in WARNINGS:
        print(f"WARN  {warning}")
    for error in ERRORS:
        print(f"ERROR {error}")
    if ERRORS:
        print(f"\n{len(ERRORS)} error(s) found")
        return 1
    print("Ansible tree is structurally valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
