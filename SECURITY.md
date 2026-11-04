# Security policy

## Supported versions

| Version | Supported |
|---|---|
| `main` | ✅ |
| Older tags | ❌ |

## Reporting a vulnerability

Do not open a public issue for a security problem.

1. Email the maintainer with a description, reproduction steps and impact assessment.
2. Expect an acknowledgement within 3 business days.
3. Do not include live credentials, customer data or exploit payloads against third-party systems.

If you are unsure whether something is a vulnerability, report it privately anyway.

## Security model

### Identity and access

- Four roles (`viewer`, `operator`, `approver`, `admin`) with twelve permissions, enforced in the API
  dependency chain — never in the browser.
- Separation of duties: the requester of a production deployment cannot approve or reject it.
- Role changes invalidate outstanding tokens because the role claim is compared with the stored role
  on every request.
- The last active administrator cannot be demoted or deactivated, and an administrator cannot change
  their own role.

### Credentials

- Passwords: PBKDF2-HMAC-SHA256, 260,000 iterations, 16-byte random salt per password, constant-time
  comparison, transparent rehash when the iteration count increases.
- Sessions: HS256 JWT with a 60-minute access token and a single-use rotating refresh token.
  Revoked token ids are retained until natural expiry.
- AWS: OIDC federation in CI, instance profiles on EC2. No long-lived access keys are required or
  accepted by the workflows.
- Ansible secrets are read from the environment or Vault (`HCCP_ADMIN_SSH_KEY`,
  `HCCP_DEPLOY_SSH_KEY`), never from committed files.

### Data protection

- Terraform state: S3 with SSE-KMS, versioning, public access blocked, DynamoDB locking.
- EBS root volumes: encrypted with the environment KMS key.
- VPC flow logs and ALB access logs: encrypted, retained per environment (30 days dev, 365 prod).
- Audit events: append-only in the store abstraction; a relational deployment writes them to an
  immutable table.

### Application hardening

- Security headers on every response: `X-Content-Type-Options`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer`, restrictive `Content-Security-Policy`, `Cache-Control: no-store`.
- Login throttling per email and source IP, returning `429` with `Retry-After`.
- Strict CORS allow-list from configuration; wildcard origins are not used.
- Request validation via Pydantic models; unexpected exceptions return a generic 500 with a request id
  and are logged with a stack trace server-side only.
- Container images run as a non-root user with a health check and no build tooling at runtime.

## Secret handling rules

1. `.env`, `*.pem`, `*.key`, `*.tfstate`, `*.tfplan` and credentials files are git-ignored.
2. Gitleaks runs in CI with an allow-list limited to documented demo credentials.
3. Never paste production credentials into an issue, pull request, chat or commit.
4. Rotate `HCCP_SECRET_KEY` by generating a new value and redeploying; all sessions will require
   re-authentication.

## Infrastructure guardrails

- `terraform fmt -check` and `terraform validate` gate every pull request.
- Production variable validation rejects single-NAT layouts, undersized fleets and disabled deletion
  protection.
- Security groups require exactly one of a CIDR or a source security group per rule, preventing
  accidental `0.0.0.0/0` rules on internal tiers.
- `HC-SG-001` fails the compliance score if SSH or RDP becomes internet-reachable.
- Checkov runs as an advisory baseline; its findings are reviewed before each release.
