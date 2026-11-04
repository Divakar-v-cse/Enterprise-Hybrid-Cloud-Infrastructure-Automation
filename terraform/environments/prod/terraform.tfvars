# Production environment - multi-AZ, deletion protection, one year of flow logs.
aws_region              = "ap-south-1"
environment             = "prod"
project                 = "hccp"
owner                   = "platform-engineering"
cost_center             = "CC-4471"
vpc_cidr                = "10.10.0.0/16"
availability_zone_count = 3

# Public ALB: TLS termination is enforced by the certificate below.
ingress_cidrs = ["0.0.0.0/0"]

# RDP/SSH is never exposed. Administrators use SSM Session Manager.
admin_cidrs = []

web_instance_type     = "m6i.large"
app_instance_type     = "m6i.large"
windows_instance_type = "t3.medium"

web_instance_count     = 3
app_instance_count     = 2
windows_instance_count = 1

enable_nat_gateway         = true
single_nat_gateway         = false
enable_deletion_protection = true
flow_logs_retention_days   = 365

# Provide the ACM certificate ARN out of band (CI variable) before applying.
certificate_arn = null
alert_email     = null

create_github_oidc_provider = false
github_repository           = "Divakar-v-cse/Enterprise-Hybrid-Cloud-Infrastructure-Automation"
