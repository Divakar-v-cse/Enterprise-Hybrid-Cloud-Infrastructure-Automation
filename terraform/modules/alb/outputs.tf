output "load_balancer_arn" {
  description = "ARN of the application load balancer."
  value       = aws_lb.this.arn
}

output "load_balancer_dns_name" {
  description = "DNS name to point the application record at."
  value       = aws_lb.this.dns_name
}

output "load_balancer_zone_id" {
  description = "Canonical hosted zone id for Route 53 alias records."
  value       = aws_lb.this.zone_id
}

output "target_group_arns" {
  description = "Target group ARNs keyed by target group name."
  value       = { for key, tg in aws_lb_target_group.this : key => tg.arn }
}

output "https_listener_arn" {
  description = "ARN of the HTTPS listener (null when TLS is not configured)."
  value       = local.https_enabled ? aws_lb_listener.https[0].arn : null
}
