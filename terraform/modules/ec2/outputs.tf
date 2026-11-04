output "instance_ids" {
  description = "Instance ids keyed by short name."
  value       = { for key, instance in aws_instance.this : key => instance.id }
}

output "private_ips" {
  description = "Private IP addresses keyed by short name."
  value       = { for key, instance in aws_instance.this : key => instance.private_ip }
}

output "public_ips" {
  description = "Public IP addresses keyed by short name (null for private instances)."
  value       = { for key, instance in aws_instance.this : key => instance.public_ip }
}

output "instance_arns" {
  description = "Instance ARNs keyed by short name."
  value       = { for key, instance in aws_instance.this : key => instance.arn }
}

output "availability_zones" {
  description = "AZ per instance."
  value       = { for key, instance in aws_instance.this : key => instance.availability_zone }
}
