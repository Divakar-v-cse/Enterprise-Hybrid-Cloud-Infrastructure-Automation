# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses semantic versioning.

## [1.0.0] - 2026-11-04

### Added

**Infrastructure**
- Seven reusable Terraform modules: `vpc`, `subnets`, `routing`, `security-group`, `iam`, `ec2`,
  `alb`.
- Development and production root stacks with separate CIDRs, sizing, NAT strategy, retention and
  protection defaults.
- S3 + DynamoDB remote state with KMS encryption and a partial backend configuration per environment.
- VPC flow logs, ALB access logs to an encrypted bucket with a 90-day lifecycle, KMS-encrypted EBS.
- GitHub Actions OIDC provider and a scoped deployment role — no static AWS keys.

**Configuration management**
- Six Ansible roles covering Linux baseline, users, security updates, firewall, nginx and IIS.
- Static inventories for dev/prod plus a tag-driven `aws_ec2` dynamic inventory.
- Playbooks for full convergence, hardening, rolling patching, user reconciliation and read-only
  conformance validation.
- Windows TLS hardening: SSL 2.0/3.0, TLS 1.0/1.1 disabled; TLS 1.2 enforced.

**Control plane**
- FastAPI service with JWT authentication, refresh-token rotation, revocation and login throttling.
- Four-role RBAC with twelve permissions and separation of duties on deployment approval.
- Deployment state machine with approval, rejection, failure and rollback paths, plus audit events.
- Fourteen-control policy engine with severity-weighted scoring and persistent waivers.
- Desired-state drift detection producing text, JSON and markdown reports.
- Read-only AWS provider adapter and a deterministic fixture provider.
- Structured JSON logging, correlation ids, security headers and a stable error envelope.

**Dashboard**
- React + TypeScript operations dashboard: overview, inventory, servers, deployments, compliance,
  drift, audit trail and access management.
- Permission-aware navigation, token refresh, loading and error states, custom SVG charts.

**Automation**
- CI workflow: Ruff, 88 backend tests with coverage, frontend typecheck/tests/build, Terraform format
  and validation, Ansible structural validation, gitleaks and Checkov.
- Terraform plan workflow with OIDC, artifact upload and job-summary output.
- Protected Terraform apply workflow with confirmation string and environment reviewers.
- Scheduled drift detection and weekly compliance evidence collection.
- Docker Compose local environment and per-service Dockerfiles.
- `scripts/validate_all.py` single-command validation.

### Known limitations

- No `terraform apply` was executed against a live AWS account in this release.
- The API store is in-memory and single-worker; PostgreSQL is a documented swap point.
- Server health metrics come from fixtures until a CloudWatch-backed collector is added.
- `ansible-lint` and Checkov run in advisory mode in CI.

[1.0.0]: https://github.com/Divakar-v-cse/Enterprise-Hybrid-Cloud-Infrastructure-Automation/releases/tag/v1.0.0
