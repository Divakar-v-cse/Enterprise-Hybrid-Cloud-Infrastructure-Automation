variable "name" {
  description = "Load balancer name (<= 32 characters)."
  type        = string

  validation {
    condition     = length(var.name) <= 32
    error_message = "ALB names must be 32 characters or fewer."
  }
}

variable "internal" {
  description = "Create an internal load balancer."
  type        = bool
  default     = false
}

variable "vpc_id" {
  description = "VPC hosting the load balancer."
  type        = string
}

variable "subnet_ids" {
  description = "Subnets the load balancer is attached to (public for internet-facing)."
  type        = list(string)
}

variable "security_group_ids" {
  description = "Security groups attached to the load balancer."
  type        = list(string)
}

variable "certificate_arn" {
  description = "ACM certificate ARN. When set, HTTPS termination is enabled."
  type        = string
  default     = null
}

variable "ssl_policy" {
  description = "ALB TLS security policy."
  type        = string
  default     = "ELBSecurityPolicy-TLS13-1-2-2021-06"
}

variable "enable_deletion_protection" {
  description = "Prevent accidental destroy (mandatory in production)."
  type        = bool
  default     = true
}

variable "idle_timeout" {
  description = "Connection idle timeout in seconds."
  type        = number
  default     = 60

  validation {
    condition     = var.idle_timeout >= 1 && var.idle_timeout <= 4000
    error_message = "idle_timeout must be between 1 and 4000 seconds."
  }
}

variable "drop_invalid_header_fields" {
  description = "Reject requests with malformed headers (WAF friendly)."
  type        = bool
  default     = true
}

variable "enable_access_logs" {
  description = "Deliver access logs to S3."
  type        = bool
  default     = true
}

variable "access_logs_bucket" {
  description = "S3 bucket for access logs (required when enable_access_logs is true)."
  type        = string
  default     = null
}

variable "access_logs_prefix" {
  description = "S3 prefix for access logs."
  type        = string
  default     = "alb"
}

variable "target_groups" {
  description = "Target groups keyed by name."
  type = map(object({
    port                 = number
    protocol             = optional(string, "HTTP")
    target_type          = optional(string, "instance")
    health_check_path    = optional(string, "/healthz")
    health_check_matcher = optional(string, "200-299")
    interval             = optional(number, 30)
    timeout              = optional(number, 5)
    healthy_threshold    = optional(number, 3)
    unhealthy_threshold  = optional(number, 3)
    stickiness_enabled   = optional(bool, false)
  }))
}

variable "default_target_group" {
  description = "Key in target_groups receiving default listener traffic."
  type        = string
}

variable "tags" {
  description = "Additional tags merged onto every resource."
  type        = map(string)
  default     = {}
}
