# Architecture

## 1. Responsibility split

| Component | Owns | Explicitly does not own |
|---|---|---|
| Terraform | Network, identity, compute, ingress, logging buckets | Package state, running services, application releases |
| Ansible | OS baseline, users, firewalls, patching, nginx/IIS | Cloud resource creation, DNS, certificates |
| GitHub Actions | Change approval, plan review, apply execution | Runtime traffic, alerting |
| FastAPI control plane | Inventory read model, policy evaluation, drift comparison, deployment records, audit | Mutating cloud resources |
| React dashboard | Presentation and operator workflow | Business logic or authorisation decisions |

The API is deliberately read-only against the provider. Mutations exist only in Terraform, which
means the console, the API and the pipeline cannot diverge into competing sources of truth.

## 2. Request lifecycle

```text
client ──► CORS ──► RequestContextMiddleware ──► router ──► dependency chain ──► service ──► store
                          │                          │
                          │ request id, timing       ├─ HTTPBearer → decode JWT → revoke check
                          │ security headers         ├─ user lookup + role freshness check
                          ▼                          └─ require_permissions(...)
                    JSON access log                        │
                                                           └─► AppError → error envelope
```

1. `RequestContextMiddleware` assigns or propagates `X-Request-ID`, records timing and emits a JSON
   access log with method, path, status, latency, client IP and actor.
2. `get_current_user` verifies the HS256 signature, `iss`, `aud`, `exp` and `nbf`, rejects revoked
   token ids, loads the account and rejects tokens whose role no longer matches the account.
3. `require_permissions` evaluates the role's permission set and returns a structured 403 listing the
   missing permissions.
4. Domain errors derive from `AppError`; the handler renders
   `{"error": {"code", "message", "request_id", "details"}}` with no internal details leaked.

## 3. Network layout

Subnets are derived from the environment CIDR with `cidrsubnet(cidr, 8, index)`:

| Tier | Dev | Prod | Route | Notes |
|---|---|---|---|---|
| public-1..3 | `10.20.0.0/24`, `10.20.1.0/24`, `10.20.2.0/24` | `10.10.0.0/24` … | `0.0.0.0/0 → IGW` | ALB and NAT only |
| private-1..3 | `10.20.10.0/24` … | `10.10.10.0/24` … | `0.0.0.0/0 → NAT (same AZ)` | Linux and Windows compute |
| data-1..3 | `10.20.20.0/24` … | `10.10.20.0/24` … | no default route | Reserved for managed databases |

Security group graph:

```text
Internet ──443/80──► alb-sg ──8080──► linux-sg ──5432──► data-sg
                        └──────80────► windows-sg
RDP 3389: only from var.admin_cidrs (empty by default; SSM is the access path)
Egress: linux/windows → NAT; data tier has no egress
```

## 4. Deployment lifecycle

```text
            create (prod)                approve (approver, not requester)
  ┌──────────────────────────► pending_approval ──────────────────────────┐
  │                                    │ reject                            │
  │                                    ▼                                   ▼
  │                                 rejected                          in_progress
  │                                                                        │
  │ create (dev, auto-approved)                                            ├─ success → succeeded ──► rolled_back
  └──────────────────────────► approved ───────────────────────────────────┘         │
                                                                                    └─ failure → failed
```

Every transition calls `_require_transition`, so an invalid state change is a 409 rather than a
silent overwrite. Each transition writes an audit event with actor, target and environment.

The `PipelineRunner` protocol is the integration seam. `SimulatedRunner` produces deterministic logs
for local and CI use; a production implementation would dispatch `workflow_dispatch` to
`terraform-plan.yml`/`terraform-apply.yml` or start a CodePipeline execution and poll the result.

## 5. Data model and persistence

`Store` is a lock-guarded in-memory repository behind a narrow method surface: users, resources,
deployments, findings, audit events, revoked tokens and login attempts. Routes and services depend on
the methods, not on the storage engine. Replacing it with PostgreSQL means implementing the same
methods with SQLAlchemy sessions; no route changes.

Tables in a relational deployment would be: `users`, `resources`, `deployments`, `deployment_events`,
`compliance_findings`, `audit_events`, `revoked_tokens`.

The audit deque is bounded at 2,000 events in memory to keep the demo predictable; a real deployment
would append to an immutable store (Postgres partitioned table or CloudWatch Logs).

## 6. Policy engine

Rules are data, not branching logic:

```python
Rule(
    id="HC-SG-001",
    severity=Severity.CRITICAL,
    applies=lambda resource: resource.kind == ResourceKind.SECURITY_GROUP,
    evaluate=_check_open_admin_ports,
)
```

`scan()` iterates resources × rules, records a finding for every applicable evaluation (pass and
fail), and computes a severity-weighted score while excluding waivers. Finding IDs are deterministic
(`<rule>-<resource>`), which is what allows a waiver to survive a rescan.

## 7. Drift contract

`backend/app/data/desired_state.json` holds the declared configuration per environment. Each entry
carries `name`, `kind`, a `config` subset and a `tags` subset. Comparison semantics:

- a declared resource absent from the provider is `missing`;
- an undeclared resource of a managed kind is `unexpected`;
- a differing config key is `modified`;
- a differing tag is `unmanaged_tag`.

Lists of rule objects (security group ingress) are normalised to a sorted set of
`protocol/from-to<-source` strings before comparison, so ordering differences are not reported as
drift. Reports are sorted by severity and rendered as text, JSON or markdown.

## 8. Security architecture

| Control | Implementation |
|---|---|
| Authentication | HS256 JWT with `iss`, `aud`, `iat`, `nbf`, `exp`, `jti`; 60-minute access tokens |
| Session renewal | Single-use refresh tokens with rotation; replayed tokens rejected |
| Password storage | PBKDF2-HMAC-SHA256, 260,000 iterations, 16-byte random salt, constant-time compare |
| Brute force | 5 failed attempts per email + IP per 5 minutes, `Retry-After` returned |
| Authorisation | Four roles, twelve permissions, server-side enforcement on every route |
| Separation of duties | Requester cannot approve or reject their own deployment |
| Transport | TLS terminated at the ALB; HTTP redirects to HTTPS when a certificate is configured |
| Headers | `nosniff`, `DENY`, `no-referrer`, restrictive CSP, `no-store` |
| Audit | Every auth, deployment, compliance and drift action recorded with actor and source IP |
| Secrets | OIDC in CI, instance profiles on EC2, environment variables or Vault for Ansible |
| Logging | JSON with request id and actor; password hashes excluded from models and responses |

## 9. CI pipeline

```text
push / PR
   ├─ backend:  ruff → pytest (88) → coverage → artifacts
   ├─ frontend: npm ci → tsc → vitest (13) → vite build → bundle artifact
   ├─ terraform: fmt -check → init -backend=false → validate (dev, prod)
   ├─ ansible:  structural validation → collection install → ansible-lint (advisory)
   └─ security: gitleaks → checkov (advisory baseline)
                 └─ summary job fails the build if any required job failed
```

Terraform plan and apply workflows are separate so a pull request never holds credentials with write
scope. Both assume a role through OIDC and write the plan to the job summary for reviewers.

## 10. Validation results

Recorded from the build of this repository on Windows with Python 3.12.2, Node 22.23.0 and
Terraform 1.15.8:

| Gate | Result |
|---|---|
| `ruff check app tests` | All checks passed |
| `pytest` backend suite | 88 passed |
| Backend coverage (`--cov=app`) | 88% overall; AWS adapter excluded by design |
| `npx tsc --noEmit` | No type errors |
| `vitest run` | 13 passed across 2 files |
| `vite build` | 51 modules, 222.54 kB JS (68.17 kB gzip), 14.56 kB CSS |
| `terraform fmt -check -recursive` | Clean |
| `terraform validate` dev / prod | Success for both |
| `scripts/validate_ansible.py` | 41 YAML documents, 6 roles, structurally valid |
| `scripts/drift_detect.py --provider mock` | 4 drift items across dev and prod (expected fixture drift) |
| `scripts/compliance_report.py --provider mock` | Score 88.4%, 122/134 controls passing |

Reproduce with `python scripts/validate_all.py`.
