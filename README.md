# Enterprise Hybrid Cloud Infrastructure Automation

A production-shaped reference platform that provisions AWS infrastructure with Terraform, configures
Linux and Windows servers with Ansible, gates every change through GitHub Actions, and exposes the
whole estate through a FastAPI control plane and a React operations dashboard.

[![CI](https://github.com/Divakar-v-cse/Enterprise-Hybrid-Cloud-Infrastructure-Automation/actions/workflows/ci.yml/badge.svg)](https://github.com/Divakar-v-cse/Enterprise-Hybrid-Cloud-Infrastructure-Automation/actions/workflows/ci.yml)
[![Terraform](https://img.shields.io/badge/terraform-1.6%2B-7B42BC)](https://developer.hashicorp.com/terraform)
[![Ansible](https://img.shields.io/badge/ansible-2.16%2B-EE0000)](https://docs.ansible.com/)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## What this repository demonstrates

| Capability | Where it lives |
|---|---|
| Reusable Terraform modules: VPC, subnets, route tables, security groups, IAM, EC2, ALB | [`terraform/modules`](terraform/modules) |
| Isolated development and production stacks with remote state | [`terraform/environments`](terraform/environments) |
| Linux and Windows configuration management, patching and user lifecycle | [`ansible`](ansible) |
| Keyless CI/CD with OIDC, plan review and protected applies | [`.github/workflows`](.github/workflows) |
| Desired-state drift detection and policy-as-code compliance | [`backend/app/services`](backend/app/services), [`scripts`](scripts) |
| Authenticated operations API with RBAC, audit trail and structured errors | [`backend/app`](backend/app) |
| Executive dashboard: inventory, health, deployments, compliance, drift | [`frontend`](frontend) |
| Automated tests and a one-command local validation environment | [`backend/tests`](backend/tests), [`frontend/src`](frontend/src), [`docker-compose.yml`](docker-compose.yml) |

Nothing in this repository requires an AWS account to run or to be reviewed: the API ships with a
deterministic fixture provider, and every workflow degrades gracefully when credentials are absent.

---

## Architecture

```text
                         ┌──────────────────────────────────────────┐
                         │        GitHub Actions (OIDC)             │
                         │  ci · plan · apply · drift · compliance  │
                         └───────────────┬──────────────────────────┘
                                         │ assume role (no static keys)
        ┌────────────────────────────────┼────────────────────────────────┐
        │                                │                                │
┌───────▼────────┐              ┌────────▼─────────┐            ┌─────────▼────────┐
│   Terraform    │              │     Ansible      │            │    FastAPI       │
│  modules +     │              │  roles for Linux │            │  control plane   │
│  dev/prod envs │              │  and Windows     │            │  (read + orchestration)
└───────┬────────┘              └────────┬─────────┘            └─────────┬────────┘
        │                                │                                │
        │  provisions                    │  configures                    │  observes
        ▼                                ▼                                ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                              AWS account · ap-south-1                             │
│  VPC 10.20.0.0/16 (dev) · 10.10.0.0/16 (prod)                                     │
│  public subnets → ALB → private subnets (Linux + Windows) → data subnets           │
│  IAM roles · KMS · S3 log buckets · CloudWatch · SNS · SSM                        │
└───────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
                         ┌──────────────────────────────────────────┐
                         │   React dashboard (Vite + TypeScript)    │
                         │  overview · resources · servers ·         │
                         │  deployments · compliance · drift · audit │
                         └──────────────────────────────────────────┘
```

Design rules that shaped the code:

1. **Terraform owns infrastructure.** The API is read-only against the cloud. There is no "create
   resource" endpoint, so console and API drift cannot compete with the state file.
2. **Ansible owns configuration.** Server state is converged by playbooks; the dashboard reports the
   resulting health rather than mutating hosts.
3. **GitHub Actions owns change.** Environments, approvals and OIDC replace long-lived access keys.
4. **The control plane owns evidence.** Authentication, authorisation, audit and policy evaluation
   are centralised so every action has a traceable record.

More detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Technology stack

| Layer | Technology | Notes |
|---|---|---|
| Cloud | AWS (VPC, EC2, ALB, IAM, KMS, S3, CloudWatch, SNS, SSM) | `ap-south-1` default, configurable per environment |
| Infrastructure as code | Terraform 1.6+ (`hashicorp/aws ~> 5.60`) | 7 modules, 2 root environments, S3 + DynamoDB state |
| Configuration management | Ansible 2.16+ (`ansible.posix`, `community.general`, `ansible.windows`, `community.windows`, `amazon.aws`) | 6 roles, static and dynamic inventories |
| API | FastAPI 0.115, Pydantic 2, Uvicorn | JWT HS256, PBKDF2 password hashing, JSON logs |
| Dashboard | React 18, TypeScript 5.6, Vite 5, React Router 6 | Custom SVG charts, no UI framework |
| CI/CD | GitHub Actions | OIDC, plan artifacts, drift schedule, compliance evidence |
| Testing | pytest + coverage, Vitest + Testing Library, `terraform validate`, custom Ansible validator | 101 automated tests |

---

## Repository layout

```text
.
├── .github/workflows/          ci · terraform-plan · terraform-apply · drift-detection · compliance-scan
├── ansible/
│   ├── inventories/{dev,prod}/ static inventories + group_vars
│   ├── inventories/aws_ec2.yml dynamic inventory for real accounts
│   ├── playbooks/              site · linux · windows · hardening · patch · users · validate
│   └── roles/                  common · users · security_updates · firewall · linux_webapp · windows_iis
├── backend/
│   ├── app/
│   │   ├── api/v1/             auth · dashboard · resources · deployments · compliance · drift · servers · audit · users
│   │   ├── core/               config · security · rbac · errors · logging · middleware
│   │   ├── providers/          provider protocol, mock fixtures, AWS boto3 adapter
│   │   ├── services/           inventory · deployments · compliance · drift · audit
│   │   └── data/               desired_state.json (drift contract)
│   └── tests/                  88 tests
├── docs/                       architecture · runbook · bootstrap
├── frontend/
│   └── src/                    api · components · context · hooks · lib · pages
├── scripts/                    drift_detect · compliance_report · validate_terraform · validate_ansible · validate_all
├── terraform/
│   ├── environments/{dev,prod} root stacks, tfvars, backend config
│   └── modules/                vpc · subnets · routing · security-group · iam · ec2 · alb
├── docker-compose.yml          local API + dashboard
└── Makefile                    common operator commands
```

---

## Quick start

### 1. API and dashboard without Docker

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

```bash
# Frontend (second terminal)
cd frontend
npm install
npm run dev                        # http://localhost:5173, proxies /api to :8000
```

Open <http://localhost:5173> and sign in with a seeded account:

| Role | Email | Password | Can do |
|---|---|---|---|
| Admin | `admin@hccp.io` | `Admin#2026` | Everything, including user and role management |
| Approver | `approver@hccp.io` | `Approver#2026` | Approve, reject and roll back deployments |
| Operator | `operator@hccp.io` | `Operator#2026` | Request deployments, run scans and drift detection |
| Viewer | `viewer@hccp.io` | `Viewer#2026` | Read-only access to every view |

Seeded accounts exist only when `HCCP_SEED_DEMO_DATA=true`; production configuration refuses to
start with demo data enabled.

### 2. Full local environment with Docker

```bash
docker compose up --build
# dashboard -> http://localhost:8080
# API docs  -> http://localhost:8000/docs
```

### 3. One-command validation

```bash
python scripts/validate_all.py          # Ansible + backend + Terraform + frontend
python scripts/validate_all.py --fast   # skip the frontend production build
```

---

## Terraform

### Modules

| Module | Creates | Notable guarantees |
|---|---|---|
| `vpc` | VPC, internet gateway, CloudWatch log group, IAM role, flow logs | Flow logs on by default; DNS hostnames enabled |
| `subnets` | Public, private and data subnets across up to 4 AZs | Tier validation; public subnets never auto-assign public IPs |
| `routing` | Public/private/data route tables, associations, EIPs, NAT gateways | One NAT per AZ in production; data tier has no default route |
| `security-group` | Security group plus named ingress/egress rules | Every rule must set exactly one of CIDR or source SG |
| `iam` | Role, inline policies, managed attachments, instance profile, boundary | Permissions boundary supported; OIDC trust via `trust_policy_json` |
| `ec2` | Instances, AMI resolution, encrypted gp3 root volumes, status alarms | IMDSv2 enforced; encryption mandatory; AMI drift ignored by design |
| `alb` | ALB, target groups, HTTPS listener, HTTP→HTTPS redirect, access logs | Deletion protection default true; TLS 1.3 policy; invalid headers dropped |

### Environments

| | Development | Production |
|---|---|---|
| VPC | `10.20.0.0/16` | `10.10.0.0/16` |
| NAT | Single gateway (cost) | One per AZ |
| Compute | 2 × `t3.micro` web, 1 app, 1 Windows | 3 × `m6i.large` web, 2 app, 1 Windows |
| ALB deletion protection | Disabled | Enforced by validation |
| Flow log retention | 30 days | 365 days |
| Approval | Auto-apply on merge | Manual, protected environment |

```bash
cd terraform/environments/dev
terraform init -backend-config=backend.hcl   # see docs/BOOTSTRAP.md for the bucket/lock table
terraform plan -out=tfplan
terraform apply tfplan
terraform output -json instance_private_ips   # feed the Ansible inventory
```

State is remote (S3 + DynamoDB lock) and encrypted with a dedicated KMS key. No state file is ever
committed; `.gitignore` denies `*.tfstate`, `*.tfplan` and `.terraform/`.

---

## Ansible

```bash
cd ansible
ansible-galaxy collection install -r requirements.yml

# Dry run against the static development inventory
ansible-playbook playbooks/site.yml -i inventories/dev/hosts.yml --check --diff

# Converge, then prove the baseline holds
ansible-playbook playbooks/site.yml -i inventories/dev/hosts.yml
ansible-playbook playbooks/validate.yml -i inventories/dev/hosts.yml

# Rolling security patch (serial: 1, health gate between hosts)
ansible-playbook playbooks/patch.yml -i inventories/prod/hosts.yml -e target_env=prod
```

| Role | Applies to | What it enforces |
|---|---|---|
| `common` | Linux | Baseline packages, chrony, journald persistence, sysctl hardening, auditd rules, SSH hardening |
| `users` | Linux + Windows | Declared admin accounts, keys, sudo policy, root lock, removed users |
| `security_updates` | Linux + Windows | unattended-upgrades / dnf-automatic / PSWindowsUpdate, optional immediate patching |
| `firewall` | Linux + Windows | ufw or firewalld default-deny, explicit port allow-list, Windows firewall profiles |
| `linux_webapp` | Linux | nginx, health endpoint, security headers, JSON access logs |
| `windows_iis` | Windows | IIS features, app pool, site binding, TLS 1.2+ only, legacy protocols disabled |

On real AWS accounts use the dynamic inventory (`inventories/aws_ec2.yml`); it groups hosts by
`Environment`, `OS`, `PatchGroup` and `Role` tags that Terraform applies.

---

## Control plane API

Base path `/api/v1`. Interactive documentation is served at `/docs` outside production.

| Method | Path | Permission | Purpose |
|---|---|---|---|
| `POST` | `/auth/login` | public | Issue access and refresh tokens, with brute-force throttling |
| `POST` | `/auth/refresh` | public | Rotate a single-use refresh token |
| `POST` | `/auth/logout` | authenticated | Revoke the current access token |
| `GET` | `/auth/me` | authenticated | Profile and effective permissions |
| `GET` | `/dashboard/summary` | `infrastructure:read` | Aggregate posture for the dashboard |
| `GET` | `/resources` | `infrastructure:read` | Filterable inventory with pagination |
| `GET` | `/servers` | `infrastructure:read` | Linux and Windows fleet telemetry |
| `GET` | `/deployments` | `deployment:read` | Delivery history |
| `POST` | `/deployments` | `deployment:create` | Request a rollout (production is gated) |
| `POST` | `/deployments/{id}/approve` | `deployment:approve` | Approve and execute (separation of duties enforced) |
| `POST` | `/deployments/{id}/rollback` | `deployment:rollback` | Roll back a succeeded deployment |
| `GET` | `/compliance/findings` | `compliance:read` | Policy findings with severity ordering |
| `POST` | `/compliance/scan` | `compliance:scan` | Re-evaluate all controls |
| `POST` | `/compliance/findings/{id}/waive` | `compliance:scan` | Record a documented exception |
| `GET` | `/drift` | `drift:read` | Desired-state comparison per environment |
| `POST` | `/drift/run` | `drift:run` | Trigger detection and audit it |
| `GET` | `/audit` | `audit:read` | Query the immutable event trail |
| `GET` | `/users` | `user:read` | Accounts and roles |
| `PATCH` | `/users/{id}/role` | `user:manage` | Change a role (last-admin guard) |

### RBAC matrix

| Permission | Viewer | Operator | Approver | Admin |
|---|:--:|:--:|:--:|:--:|
| `infrastructure:read`, `deployment:read`, `compliance:read`, `drift:read`, `audit:read` | ✅ | ✅ | ✅ | ✅ |
| `deployment:create`, `compliance:scan`, `drift:run` | | ✅ | ✅ | ✅ |
| `deployment:approve`, `deployment:rollback` | | | ✅ | ✅ |
| `user:read`, `user:manage` | | | | ✅ |

Separation of duties is enforced independently of the role: the identity that requests a
deployment can never approve it.

### Security controls

- HS256 JWTs with `iss`, `aud`, `nbf`, `exp` and `jti`; revoked token IDs are retained until expiry.
- Refresh-token rotation: a replayed refresh token is rejected.
- PBKDF2-HMAC-SHA256 password hashing, 260k iterations, per-password salt, transparent rehash.
- Login throttling per email + source IP with `Retry-After`.
- Constant-time signature comparison; tampered, expired, wrong-audience and wrong-type tokens rejected.
- Security headers (`nosniff`, `DENY`, `no-referrer`, CSP) and correlation IDs on every response.
- Structured JSON logs with request id, actor and latency; no secrets or hashes are logged.
- Errors return a stable envelope with `code`, `message`, `request_id` and safe `details` only.

---

## Compliance and drift

### Policy-as-code

Fifteen controls across network, identity, data protection, patching, resilience and governance are
evaluated on startup and on demand. The score is severity-weighted (critical 10, high 5, medium 2,
low 1) and excludes documented waivers.

| Control | Severity | Checks |
|---|---|---|
| `HC-SG-001` | Critical | No SSH/RDP ingress from `0.0.0.0/0` |
| `HC-IAM-001` | Critical | No `Action:*` on `Resource:*` |
| `HC-EC2-001` | High | IMDSv2 required |
| `HC-EC2-002` | High | EBS encrypted at rest |
| `HC-EC2-003` | High | Patch baseline current |
| `HC-VPC-001` | High | Flow logs enabled |
| `HC-ALB-002` | High | Production ALB deletion protection |
| `HC-ALB-003` | High | TLS on every listener, HTTP redirects |
| `HC-ID-001` | Critical | Privileged accounts require MFA |
| `HC-EC2-004` | Medium | No public IP on private-subnet instances |
| `HC-EC2-005` | Medium | Instances are SSM managed |
| `HC-EC2-006` | Medium | Backup plan attached |
| `HC-IAM-002` | Medium | Permissions boundary present |
| `HC-TAG-001` | Medium | `Environment`, `Owner`, `CostCenter`, `ManagedBy` present |
| `HC-ALB-001` | Medium | ALB access logs enabled |

### Drift detection

`backend/app/data/desired_state.json` is the committed contract: the resources Terraform should have
created and the configuration it should have applied. The detector compares live inventory against it
and classifies each difference as `missing`, `unexpected`, `modified` or `unmanaged_tag`.

```bash
python scripts/drift_detect.py --provider mock                        # fixture demo (4 known drifts)
python scripts/drift_detect.py --provider aws --fail-on-drift         # CI gate
python scripts/drift_detect.py --format markdown --output drift.md
```

The fixture estate intentionally contains four realistic drifts: a resized dev instance, SSH opened on
a dev load balancer security group, a cleared cost-centre tag, and a terminated production node that
is still declared. They make the dashboard and the scheduled workflow demonstrable without AWS.

---

## CI/CD

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | push, PR | Ruff + 88 backend tests with coverage, frontend typecheck/tests/build, `terraform fmt` + validate, Ansible structural validation, gitleaks + Checkov |
| `terraform-plan.yml` | PR touching Terraform, manual | OIDC assume role, init remote state, plan, publish plan to the job summary and an artifact |
| `terraform-apply.yml` | manual only | Confirmation string, protected GitHub Environment, plan + apply, outputs artifact |
| `drift-detection.yml` | daily 02:15 UTC, manual | Compares live state to the contract, publishes markdown, fails on real drift |
| `compliance-scan.yml` | weekly Monday, manual | Policy evaluation with 90-day evidence retention |

### One-time repository configuration

| Name | Type | Purpose |
|---|---|---|
| `AWS_OIDC_ROLE_ARN` | variable | Role assumed by plan/apply workflows |
| `AWS_AUDIT_ROLE_ARN` | variable | Read-only role for drift and compliance |
| `TF_STATE_BUCKET` | variable | S3 bucket holding Terraform state |
| `TF_LOCK_TABLE` | variable | DynamoDB table for state locking |

Create the `dev` and `prod` GitHub Environments with required reviewers on `prod`. No AWS access key
is stored in the repository; trust is established through the GitHub OIDC provider created by the dev
stack (see [docs/BOOTSTRAP.md](docs/BOOTSTRAP.md)).

---

## Testing

Run everything locally:

```bash
python scripts/validate_all.py
```

Individual suites:

```bash
cd backend  && pytest -q --cov=app --cov-report=term-missing
cd frontend && npm test && npm run build
python scripts/validate_terraform.py
python scripts/validate_ansible.py
```

The API test suite covers authentication and token lifecycle, brute-force throttling, the RBAC
matrix, inventory filtering and pagination, the deployment state machine including failure and
rollback paths, compliance scoring and waivers, drift classification, audit recording, error
envelopes and CORS. The AWS provider adapter is excluded from coverage because it requires live
credentials; it is exercised only in a configured account.

Reference results from the validation run recorded in this repository are listed in
[docs/ARCHITECTURE.md § Validation results](docs/ARCHITECTURE.md#validation-results).

---

## Security and secrets

- No credentials, private keys or `.env` files are tracked. `.gitignore` and gitleaks enforce this.
- AWS access uses OIDC in CI and instance profiles on EC2. Static keys are never required.
- Terraform state lives in encrypted S3 with DynamoDB locking.
- Ansible secrets are expected from Vault or environment variables (`HCCP_ADMIN_SSH_KEY`,
  `HCCP_DEPLOY_SSH_KEY`), never from committed files.
- Production configuration refuses to start with the development signing key or seeded demo users.

See [SECURITY.md](SECURITY.md) for the disclosure process.

---

## Known limitations

This is an engineering reference, not a deployed service:

- The API keeps state in memory. It is a single-worker design; the repository documents the
  PostgreSQL swap point in `backend/app/db/store.py`.
- The default provider is deterministic fixtures, so dashboard data is synthetic until
  `HCCP_PROVIDER=aws` is set with credentials.
- Terraform has been validated with `terraform init -backend=false` and `terraform validate`; no
  `apply` was executed against an AWS account as part of this repository's build.
- Server health telemetry comes from fixtures; in production the CloudWatch agent or a small
  inventory exporter would populate the same schema.
- The simulated pipeline runner is the seam where a real GitHub Actions dispatch or CodePipeline
  call belongs.

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — components, network layout, data flows, validation results
- [Runbook](docs/RUNBOOK.md) — deploy, roll back, patch, respond to drift
- [Bootstrap](docs/BOOTSTRAP.md) — state bucket, OIDC, GitHub variables, first apply
- [Contributing](CONTRIBUTING.md) — workflow and local gates
- [Changelog](CHANGELOG.md)

## License

MIT — see [LICENSE](LICENSE).
