variable "name" {
  description = "Security group name."
  type        = string
}

variable "description" {
  description = "Security group description (must explain the purpose)."
  type        = string
}

variable "vpc_id" {
  description = "VPC the group belongs to."
  type        = string
}

variable "ingress_rules" {
  description = <<-EOT
    Ingress rules keyed by a stable name. Exactly one of `cidr_ipv4` or
    `referenced_security_group_id` must be set per rule.
  EOT
  type = map(object({
    description                  = optional(string, "")
    ip_protocol                  = string
    from_port                    = optional(number, null)
    to_port                      = optional(number, null)
    cidr_ipv4                    = optional(string, null)
    referenced_security_group_id = optional(string, null)
  }))
  default = {}
}

variable "egress_rules" {
  description = "Egress rules keyed by a stable name."
  type = map(object({
    description                  = optional(string, "")
    ip_protocol                  = string
    from_port                    = optional(number, null)
    to_port                      = optional(number, null)
    cidr_ipv4                    = optional(string, null)
    referenced_security_group_id = optional(string, null)
  }))
  default = {}
}

variable "tags" {
  description = "Additional tags merged onto the security group."
  type        = map(string)
  default     = {}
}
