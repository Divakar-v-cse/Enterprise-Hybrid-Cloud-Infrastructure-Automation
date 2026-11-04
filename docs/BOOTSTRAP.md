# Account bootstrap

One-time steps to connect this repository to a real AWS account. Everything here is deliberately
manual: bootstrapping trust is the one operation that should not be automated by the pipeline it
enables.

Replace `<account-id>` and `<region>` before running anything.

## 1. Terraform state backend

```bash
ACCOUNT_ID=<account-id>
REGION=ap-south-1
BUCKET="hccp-terraform-state-${ACCOUNT_ID}"

aws s3api create-bucket \
  --bucket "$BUCKET" --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION"

aws s3api put-bucket-versioning \
  --bucket "$BUCKET" --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket "$BUCKET" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"aws:kms","KMSMasterKeyID":"alias/hccp-terraform-state"},"BucketKeyEnabled":true}]}'

aws s3api put-public-access-block \
  --bucket "$BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

aws dynamodb create-table \
  --table-name hccp-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "$REGION"
```

Create the KMS key used above (or drop the `KMSMasterKeyID` and rely on SSE-S3):

```bash
aws kms create-key --description "Terraform state encryption" --enable-key-rotation
aws kms create-alias --alias-name alias/hccp-terraform-state --target-key-id <key-id>
```

## 2. Apply the development stack

The dev stack creates the GitHub OIDC provider and the deployment roles. Run it once with an
administrator profile:

```bash
cd terraform/environments/dev
terraform init -backend-config=backend.hcl
terraform plan -out=tfplan
terraform apply tfplan
terraform output github_actions_role_arn
terraform output -json instance_private_ips
```

Note the `github_actions_role_arn` value. Production reuses the same OIDC provider
(`create_github_oidc_provider = false`) and discovers it by URL.

## 3. GitHub repository configuration

Settings → Secrets and variables → Actions → **Variables**:

| Variable | Value |
|---|---|
| `AWS_OIDC_ROLE_ARN` | `github_actions_role_arn` output from dev |
| `AWS_AUDIT_ROLE_ARN` | A read-only role for drift/compliance (optional; reuse the plan role for a demo) |
| `TF_STATE_BUCKET` | `hccp-terraform-state-<account-id>` |
| `TF_LOCK_TABLE` | `hccp-terraform-locks` |

Settings → Environments:

| Environment | Protection |
|---|---|
| `dev` | No reviewers required |
| `prod` | Required reviewers (at least one), restrict to `main`, prevent self-review |

No repository secrets are required: authentication is OIDC only.

## 4. Production stack

```bash
cd terraform/environments/prod
# Set certificate_arn in terraform.tfvars (or via -var) before applying.
terraform init -backend-config=backend.hcl
terraform plan -out=tfplan
terraform apply tfplan
```

Production validation rejects:
- a single NAT gateway,
- fewer than two web or application instances,
- disabled ALB deletion protection,
- a missing ACM certificate when HTTPS is expected (listener falls back to HTTP otherwise, so supply
  the certificate before exposing the endpoint).

## 5. Configure the servers

```bash
cd ansible
ansible-galaxy collection install -r requirements.yml

# Discover hosts by tag (preferred)
ansible-inventory -i inventories/aws_ec2.yml --graph

# Converge
ansible-playbook playbooks/site.yml -i inventories/aws_ec2.yml -e target_env=dev

# Prove the baseline
ansible-playbook playbooks/validate.yml -i inventories/aws_ec2.yml -e target_env=dev
```

Administrative access uses SSM Session Manager:

```bash
aws ssm start-session --target $(terraform -chdir=../terraform/environments/dev output -json instance_ids | jq -r '."web-01"')
```

## 6. Point the control plane at the account

```bash
export HCCP_PROVIDER=aws
export HCCP_AWS_REGION=ap-south-1
export HCCP_ENVIRONMENT=dev
export HCCP_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"
export HCCP_SEED_DEMO_DATA=false
# Credentials via SSO: aws sso login --profile hccp
export AWS_PROFILE=hccp
uvicorn app.main:app --port 8000
```

`GET /readyz` must report `"reachable": true` and a non-zero resource count. The AWS provider maps
`describe_vpcs`, `describe_subnets`, `describe_security_groups`, `describe_instances`,
`describe_load_balancers` and `describe_flow_logs` into the same schema the fixtures use.

## 7. First drift baseline

After the first apply, the live account is the reference. Regenerate the contract only when an
intended change has been applied:

```bash
python scripts/drift_detect.py --provider aws --format json > reports/baseline.json
# Review, then update backend/app/data/desired_state.json intentionally and commit it.
```

## 8. Teardown

```bash
cd terraform/environments/prod && terraform destroy
cd ../dev && terraform destroy
```

The state bucket and lock table are outside Terraform and must be deleted manually after confirming
no environment still references them.
