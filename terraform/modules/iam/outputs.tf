output "role_arn" {
  description = "ARN of the IAM role."
  value       = aws_iam_role.this.arn
}

output "role_name" {
  description = "Name of the IAM role."
  value       = aws_iam_role.this.name
}

output "role_id" {
  description = "Stable unique id of the IAM role."
  value       = aws_iam_role.this.unique_id
}

output "instance_profile_name" {
  description = "Instance profile name (null when not created)."
  value       = var.create_instance_profile ? aws_iam_instance_profile.this[0].name : null
}

output "instance_profile_arn" {
  description = "Instance profile ARN (null when not created)."
  value       = var.create_instance_profile ? aws_iam_instance_profile.this[0].arn : null
}
