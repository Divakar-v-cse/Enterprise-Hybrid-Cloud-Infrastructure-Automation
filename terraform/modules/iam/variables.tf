variable "name" {
  description = "IAM role name."
  type        = string
}

variable "description" {
  description = "Human readable purpose of the role."
  type        = string
  default     = "Managed by Terraform"
}

variable "assume_role_principals" {
  description = "AWS service principals allowed to assume the role (ignored when trust_policy_json is set)."
  type        = list(string)
  default     = ["ec2.amazonaws.com"]
}

variable "trust_policy_json" {
  description = "Full assume-role policy JSON. Use for federated (OIDC) or cross-account trusts."
  type        = string
  default     = null
}

variable "managed_policy_arns" {
  description = "AWS managed or customer managed policy ARNs attached to the role."
  type        = list(string)
  default     = []
}

variable "inline_policies" {
  description = "Inline policies keyed by policy name, value is a JSON document."
  type        = map(string)
  default     = {}
}

variable "permissions_boundary_arn" {
  description = "Permissions boundary limiting the maximum effective permissions."
  type        = string
  default     = null
}

variable "max_session_duration" {
  description = "Maximum session duration in seconds (3600-43200)."
  type        = number
  default     = 3600

  validation {
    condition     = var.max_session_duration >= 3600 && var.max_session_duration <= 43200
    error_message = "max_session_duration must be between 3600 and 43200 seconds."
  }
}

variable "create_instance_profile" {
  description = "Create an instance profile so EC2 can use the role."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Additional tags merged onto the role."
  type        = map(string)
  default     = {}
}
