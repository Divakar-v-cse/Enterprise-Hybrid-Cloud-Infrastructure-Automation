variable "vpc_id" {
  description = "VPC that owns the subnets."
  type        = string
}

variable "name" {
  description = "Name prefix for the subnets."
  type        = string
}

variable "subnets" {
  description = <<-EOT
    Subnets keyed by short name. `tier` drives routing and tagging:
    public (internet gateway), private (NAT egress), data (no internet egress).
  EOT
  type = map(object({
    cidr_block              = string
    availability_zone       = string
    tier                    = string
    map_public_ip_on_launch = optional(bool, false)
  }))

  validation {
    condition     = alltrue([for s in values(var.subnets) : contains(["public", "private", "data"], s.tier)])
    error_message = "Every subnet tier must be one of: public, private, data."
  }

  validation {
    condition     = length(var.subnets) > 0
    error_message = "At least one subnet must be declared."
  }
}

variable "tags" {
  description = "Additional tags merged onto every subnet."
  type        = map(string)
  default     = {}
}
