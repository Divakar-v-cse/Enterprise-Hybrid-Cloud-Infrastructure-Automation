# Remote state for the production environment.
#   terraform init -backend-config=backend.hcl
#
# Replace <account-id> with your 12 digit AWS account id.

bucket         = "hccp-terraform-state-<account-id>"
key            = "enterprise-hybrid-cloud/prod/terraform.tfstate"
region         = "ap-south-1"
encrypt        = true
kms_key_id     = "alias/hccp-terraform-state"
dynamodb_table = "hccp-terraform-locks"
