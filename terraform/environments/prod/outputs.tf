output "environment" {
  description = "Environment name."
  value       = var.environment
}

output "vpc_id" {
  description = "VPC identifier."
  value       = module.vpc.vpc_id
}

output "vpc_cidr_block" {
  description = "VPC CIDR block."
  value       = module.vpc.vpc_cidr_block
}

output "public_subnet_ids" {
  description = "Public subnet ids keyed by short name."
  value       = module.subnets.public_subnet_ids
}

output "private_subnet_ids" {
  description = "Private subnet ids keyed by short name."
  value       = module.subnets.private_subnet_ids
}

output "data_subnet_ids" {
  description = "Data tier subnet ids keyed by short name."
  value       = module.subnets.data_subnet_ids
}

output "nat_gateway_public_ips" {
  description = "Egress addresses that must be allow-listed by downstream partners."
  value       = module.routing.nat_public_ips
}

output "security_group_ids" {
  description = "Security groups by tier."
  value = {
    alb     = module.alb_security_group.security_group_id
    linux   = module.linux_security_group.security_group_id
    windows = module.windows_security_group.security_group_id
    data    = module.data_security_group.security_group_id
  }
}

output "instance_ids" {
  description = "Compute instance ids keyed by short name."
  value       = module.compute.instance_ids
}

output "instance_private_ips" {
  description = "Private IP addresses keyed by short name (Ansible inventory source)."
  value       = module.compute.private_ips
}

output "load_balancer_dns_name" {
  description = "Public DNS name of the application load balancer."
  value       = module.load_balancer.load_balancer_dns_name
}

output "load_balancer_zone_id" {
  description = "Route 53 alias zone id for the load balancer."
  value       = module.load_balancer.load_balancer_zone_id
}

output "target_group_arns" {
  description = "Target group ARNs keyed by name."
  value       = module.load_balancer.target_group_arns
}

output "ec2_role_arn" {
  description = "Runtime role assumed by EC2 instances."
  value       = module.ec2_role.role_arn
}

output "github_actions_role_arn" {
  description = "Role assumed by GitHub Actions via OIDC - set as AWS_ROLE_ARN in the repository."
  value       = module.github_actions_role.role_arn
}

output "kms_key_alias" {
  description = "KMS alias used for EBS and log encryption."
  value       = aws_kms_alias.ebs.name
}

output "alerts_topic_arn" {
  description = "SNS topic for operational alarms."
  value       = aws_sns_topic.alerts.arn
}

output "artifact_bucket_name" {
  description = "Bucket expected by the runtime policy for deployment artifacts."
  value       = "${local.name_prefix}-artifacts"
}

output "ssm_start_session_commands" {
  description = "Copy/paste commands to open a shell without SSH keys."
  value = {
    for name, instance_id in module.compute.instance_ids :
    name => "aws ssm start-session --target ${instance_id}"
  }
}
