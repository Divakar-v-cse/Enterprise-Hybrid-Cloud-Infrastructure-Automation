variable "name" {
  description = "Name prefix for the instances."
  type        = string
}

variable "instances" {
  description = <<-EOT
    Instances keyed by short name. The key becomes the `Name` tag suffix, so
    use stable names (`web-01`, `win-01`) to avoid unnecessary replacement.
  EOT
  type = map(object({
    subnet_id                   = string
    instance_type               = string
    os                          = string
    ami_id                      = optional(string, null)
    associate_public_ip_address = optional(bool, false)
    user_data                   = optional(string, null)
    root_volume_size            = optional(number, 30)
    patch_group                 = optional(string, "default")
    role                        = optional(string, "app")
  }))

  validation {
    condition     = alltrue([for instance in values(var.instances) : contains(["linux", "windows"], instance.os)])
    error_message = "Instance os must be either 'linux' or 'windows'."
  }

  validation {
    condition     = alltrue([for instance in values(var.instances) : instance.root_volume_size >= 20])
    error_message = "root_volume_size must be at least 20 GiB."
  }
}

variable "security_group_ids" {
  description = "Security groups attached to every instance."
  type        = list(string)
}

variable "iam_instance_profile_name" {
  description = "Instance profile granting SSM and CloudWatch access."
  type        = string
  default     = null
}

variable "key_name" {
  description = "Optional EC2 key pair. Prefer SSM Session Manager over SSH."
  type        = string
  default     = null
}

variable "kms_key_arn" {
  description = "KMS key used to encrypt the root EBS volume."
  type        = string
  default     = null
}

variable "enable_detailed_monitoring" {
  description = "Enable 1-minute CloudWatch metrics."
  type        = bool
  default     = true
}

variable "enable_status_alarms" {
  description = "Create a StatusCheckFailed alarm per instance."
  type        = bool
  default     = true
}

variable "alarm_sns_topic_arn" {
  description = "SNS topic receiving alarm notifications."
  type        = string
  default     = null
}

variable "linux_ami_pattern" {
  description = "AMI name filter used when ami_id is not supplied for Linux."
  type        = string
  default     = "al2023-ami-2023.*-x86_64"
}

variable "windows_ami_pattern" {
  description = "AMI name filter used when ami_id is not supplied for Windows."
  type        = string
  default     = "Windows_Server-2022-English-Full-Base-*"
}

variable "tags" {
  description = "Additional tags merged onto every instance."
  type        = map(string)
  default     = {}
}
