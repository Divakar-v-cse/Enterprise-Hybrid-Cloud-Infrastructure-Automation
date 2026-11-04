variable "name" {
  description = "Name prefix applied to the VPC and every supporting resource."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,40}$", var.name))
    error_message = "name must be lowercase alphanumeric with dashes, 3-41 characters."
  }
}

variable "cidr_block" {
  description = "IPv4 CIDR block for the VPC (must be /16 to leave room for 3 tiers x 3 AZs)."
  type        = string
  default     = "10.20.0.0/16"

  validation {
    condition     = can(cidrhost(var.cidr_block, 0)) && tonumber(split("/", var.cidr_block)[1]) == 16
    error_message = "cidr_block must be a valid /16 CIDR block."
  }
}

variable "enable_dns_hostnames" {
  description = "Enable DNS hostnames (required for ALB and SSM endpoints)."
  type        = bool
  default     = true
}

variable "enable_flow_logs" {
  description = "Publish VPC flow logs to CloudWatch Logs."
  type        = bool
  default     = true
}

variable "flow_logs_retention_days" {
  description = "Retention for the flow log group."
  type        = number
  default     = 90

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.flow_logs_retention_days)
    error_message = "flow_logs_retention_days must be a CloudWatch Logs supported retention value."
  }
}

variable "kms_key_arn" {
  description = "Optional KMS key for the flow log group. Uses the CloudWatch default key when null."
  type        = string
  default     = null
}

variable "tags" {
  description = "Additional tags merged onto every resource."
  type        = map(string)
  default     = {}
}
