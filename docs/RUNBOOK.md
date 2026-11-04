# Operations runbook

All commands assume the repository root unless stated otherwise.

## 1. Daily checks

```bash
# Platform posture (API must be running)
curl -s http://localhost:8000/healthz
curl -s http://localhost:8000/readyz | jq

# Drift against the committed contract
python scripts/drift_detect.py --provider aws --fail-on-drift

# Compliance snapshot
python scripts/compliance_report.py --provider aws --format markdown --output reports/compliance.md
```

Dashboard equivalents: **Overview** for posture, **Drift** for contract comparison, **Compliance** for
findings and waivers, **Servers** for patch status.

## 2. Standard change (development)

1. Open a pull request; `ci.yml` and `terraform-plan.yml` run automatically.
2. Review the plan in the job summary. Any `replace` on a stateful resource needs an explicit note.
3. Merge. Development deployments are auto-approved through the API or the pipeline.
4. Confirm in **Deployments** that the run reached `succeeded` and the logs contain
   `post-deploy verification passed`.

## 3. Production change

1. `terraform plan` runs against production via `workflow_dispatch` (or the API request).
2. An operator with `deployment:create` requests the rollout. The request lands in
   `pending_approval`.
3. An **approver who is not the requester** reviews and approves. The API rejects self-approval with
   403 `separation of duties`.
4. `terraform-apply.yml` requires the `prod` GitHub Environment and a typed `apply` confirmation.
5. Post-apply, run the configuration gate:

```bash
cd ansible
ansible-playbook playbooks/validate.yml -i inventories/prod/hosts.yml -e target_env=prod
```

## 4. Rollback

```bash
# Via the API
curl -s -X POST "$API/api/v1/deployments/$DEPLOYMENT_ID/rollback" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"reason":"5xx rate above 2% for 10 minutes"}'
```

The original deployment moves to `rolled_back`, a new deployment with `rollback_of` set is created and
executed, and both transitions are audited. Infrastructure rollback is the inverse Terraform apply of
the previous commit; configuration rollback re-runs the previous release tag through Ansible.

## 5. Emergency patching (CVE)

```bash
cd ansible
ansible-playbook playbooks/patch.yml \
  -i inventories/prod/hosts.yml \
  -e target_env=prod --limit 'linux' --forks 1
```

`patch.yml` is `serial: 1` with a pre-check health probe and a post-patch probe retried for 100
seconds. A failing host stops the run; the ALB removes it from rotation first because the target group
health check fails.

## 6. Drift response

1. `python scripts/drift_detect.py --provider aws --environment prod` to see the items.
2. Decide the direction:
   - **Live is wrong** → `terraform apply` from `main` to restore the declared state.
   - **Code is wrong** → change Terraform, merge, apply, then update `desired_state.json`.
3. Never hand-edit resources in the console to "fix" drift; that recreates the problem.
4. Record the outcome in the change ticket and confirm the next scheduled drift run is clean.

Severity guidance: `critical` (security group, missing production compute) within 1 hour; `high`
within one business day; `medium`/`low` in the next sprint.

## 7. Compliance exception

```bash
curl -s -X POST "$API/api/v1/compliance/findings/HC-TAG-001-vpc-dev-01/waive" \
  -H "Authorization: Bearer $TOKEN"
```

A waiver is preserved across rescans. Use it only with a ticket reference and an expiry date tracked
outside the system; the API intentionally keeps waivers simple.

## 8. Access management

```bash
# Change a role (admin only)
curl -s -X PATCH "$API/api/v1/users/$USER_ID/role" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"role":"operator"}'

# Disable an account
curl -s -X POST "$API/api/v1/users/$USER_ID/deactivate" -H "Authorization: Bearer $ADMIN_TOKEN"
```

Guardrails: an admin cannot change their own role, cannot deactivate themselves, and the last active
admin cannot be demoted. Role changes invalidate outstanding tokens on the next request because the
role claim is compared with the stored role.

## 9. Token and key rotation

| Secret | Rotation |
|---|---|
| `HCCP_SECRET_KEY` | Generate with `python -c "import secrets;print(secrets.token_urlsafe(48))"`, deploy, expect all sessions to require re-login |
| GitHub OIDC | No static secret; adjust the trust policy `sub` conditions if the repository moves |
| Terraform state KMS key | Annual rotation is enabled on the key; the alias stays stable |
| Ansible SSH keys | Rotate via Vault, re-run `playbooks/users.yml`, confirm access, then remove the old key |

## 10. Incident checklist

1. Check `/readyz` for provider reachability and inventory size.
2. Check **Servers** for critical health and overdue patching.
3. Check **Deployments** for a recent failed or rolled-back change.
4. Check **Audit trail** for unexpected authentication failures or privilege changes.
5. If the API itself is the problem, it is stateless: restart the container, sessions survive until
   token expiry because signing keys are configuration.
6. Preserve evidence: export the audit page and the drift/compliance reports as artifacts.

## 11. Local troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `401 authentication_failed` on every call | Expired access token and refresh rejected | Sign in again; check `HCCP_SECRET_KEY` has not changed |
| Dashboard shows `API connected` but empty tables | API started with `HCCP_SEED_DEMO_DATA=false` and mock provider | Set it back to `true` for local use |
| `readyz` returns 503 | Provider unreachable or inventory empty | Check AWS credentials, or `HCCP_PROVIDER=mock` |
| Terraform `Error acquiring the state lock` | Previous run interrupted | `terraform force-unlock <lock-id>` after confirming no run is active |
| Ansible `UNREACHABLE` on Windows | WinRM not configured or port 5986 blocked | Verify the security group and `ansible_winrm_transport` |
| `npm run build` type errors | Stale `dist` types or missing install | `rm -rf node_modules && npm ci` |
