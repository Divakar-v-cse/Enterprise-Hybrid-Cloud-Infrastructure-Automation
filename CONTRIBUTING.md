# Contributing

## Workflow

1. Branch from `main`: `feat/…`, `fix/…`, `docs/…`, `chore/…`.
2. Keep commits scoped and imperative: `Add ALB access log bucket policy`.
3. Run the local gates before pushing.
4. Open a pull request; describe the change, the blast radius and the rollback path.
5. A Terraform change requires the plan output pasted into the pull request description.
6. Production changes additionally require an approver who is not the author.

## Local gates

```bash
python scripts/validate_all.py
```

Equivalent individual commands:

```bash
# Backend
cd backend
ruff check app tests
pytest -q --cov=app

# Frontend
cd frontend
npm run typecheck
npm test
npm run build

# Infrastructure
python scripts/validate_terraform.py
python scripts/validate_ansible.py
python scripts/drift_detect.py --provider mock
```

## Conventions

### Terraform

- Modules expose `versions.tf`, `variables.tf`, `main.tf`, `outputs.tf` and nothing environment
  specific.
- Every variable has a description and a `type`; constraints use `validation` blocks.
- Resources carry `Name`, `Environment`, `Owner`, `CostCenter` and `ManagedBy` tags (via
  `default_tags` in the environment plus module-level tags).
- No provider configuration inside modules.
- Run `terraform fmt -recursive` before committing.

### Ansible

- Fully qualified collection names for every module (`ansible.builtin.copy`, not `copy`).
- Tasks are idempotent; `changed_when: false` for read-only commands.
- Every role has `defaults/main.yml`; no secrets in defaults or vars.
- Handler names are sentence case and referenced exactly.
- Playbooks are named after the outcome (`patch.yml`, `validate.yml`), not the tool.

### Python

- Type hints on public functions; `from __future__ import annotations`.
- Domain errors derive from `AppError`; do not raise bare `HTTPException` in services.
- New endpoints must declare a permission dependency and be covered by a test.
- Ruff with the repository configuration must pass.

### TypeScript / React

- Strict TypeScript; no `any`.
- Server state goes through `useApi`; mutations through `useMutation`.
- Authorisation checks use `can(permission)` for rendering only — the server is authoritative.
- Components stay presentational; formatting lives in `src/lib/format.ts`.

## Adding a compliance rule

1. Implement a pure `evaluate(resource) -> (passed, detail)` function in
   `backend/app/services/compliance.py`.
2. Append a `Rule(...)` to `RULES` with a stable id, severity, description and remediation.
3. Add a fixture that violates it (or assert against an existing one).
4. Extend `backend/tests/test_compliance.py`.
5. Update the control table in `README.md` and `docs/ARCHITECTURE.md`.

## Adding a Terraform module

1. Create `terraform/modules/<name>/` with the four standard files.
2. Validate it through both environments (`terraform init -backend=false && terraform validate`).
3. Add the module to the table in `README.md`.
4. Document any new variable that operators must supply.

## Commit hygiene

- No generated artifacts (`dist/`, `node_modules/`, `.terraform/`, state or plan files).
- No credentials, even in tests; use the seeded demo accounts.
- Update `CHANGELOG.md` for user-visible changes.
