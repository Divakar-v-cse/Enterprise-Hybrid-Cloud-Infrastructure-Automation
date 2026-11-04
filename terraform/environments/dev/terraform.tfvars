# Development environment - cost optimised, single NAT gateway.
aws_region              = "ap-south-1"
environment             = "dev"
project                 = "hccp"
owner                   = "platform-engineering"
cost_center             = "CC-4471"
vpc_cidr                = "10.20.0.0/16"
availability_zone_count = 3

# Open to the internet for demos. Restrict this list before using real data.
ingress_cidrs = ["0.0.0.0/0"]

# No direct RDP/SSH: use SSM Session Manager.
admin_cidrs = []

web_instance_type     = "t3.micro"
app_instance_type     = "t3.micro"
windows_instance_type = "t3.medium"

web_instance_count     = 2
app_instance_count     = 1
windows_instance_count = 1

enable_nat_gateway         = true
single_nat_gateway         = true
enable_deletion_protection = false
flow_logs_retention_days   = 30

certificate_arn = null
alert_email     = null

create_github_oidc_provider = true
github_repository           = "Divakar-v-cse/Enterprise-Hybrid-Cloud-Infrastructure-Automation"
