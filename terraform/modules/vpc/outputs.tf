output "vpc_id" {
  description = "Identifier of the VPC."
  value       = aws_vpc.this.id
}

output "vpc_cidr_block" {
  description = "CIDR block assigned to the VPC."
  value       = aws_vpc.this.cidr_block
}

output "internet_gateway_id" {
  description = "Internet gateway attached to the VPC."
  value       = aws_internet_gateway.this.id
}

output "default_route_table_id" {
  description = "Default route table created with the VPC."
  value       = aws_vpc.this.default_route_table_id
}

output "flow_log_group_name" {
  description = "CloudWatch log group receiving flow logs (null when disabled)."
  value       = var.enable_flow_logs ? aws_cloudwatch_log_group.flow_logs[0].name : null
}

output "flow_log_id" {
  description = "Flow log identifier (null when disabled)."
  value       = var.enable_flow_logs ? aws_flow_log.this[0].id : null
}
