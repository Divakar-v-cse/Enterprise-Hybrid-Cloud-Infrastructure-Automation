variable "aws_region" {
  description = "AWS region for the environment."
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Environment name. Drives naming, sizing and protection defaults."
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be dev or prod."
  }
}

variable "project" {
  description = "Project slug used in resource names."
  type        = string
  default     = "hccp"
}

variable "owner" {
  description = "Owning team recorded in the Owner tag."
  type        = string
  default     = "platform-engineering"
}

variable "cost_center" {
  description = "Chargeback code recorded in the CostCenter tag."
  type        = string
  default     = "CC-4471"
}

variable "vpc_cidr" {
  description = "VPC CIDR (/16)."
  type        = string
  default     = "10.20.0.0/16"
}

variable "availability_zone_count" {
  description = "Number of AZs to spread subnets across."
  type        = number
  default     = 3

  validation {
    condition     = var.availability_zone_count >= 2 && var.availability_zone_count <= 4
    error_message = "availability_zone_count must be between 2 and 4."
  }
}

variable "ingress_cidrs" {
  description = "CIDRs allowed to reach the public ALB (restrict in production)."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "admin_cidrs" {
  description = "CIDRs allowed to reach RDP/SSH. Empty list disables direct administrative access."
  type        = list(string)
  default     = []
}

variable "web_instance_type" {
  description = "Instance type for the Linux web tier."
  type        = string
  default     = "m6i.large"
}

variable "app_instance_type" {
  description = "Instance type for the Linux application tier."
  type        = string
  default     = "m6i.large"
}

variable "windows_instance_type" {
  description = "Instance type for the Windows IIS tier."
  type        = string
  default     = "t3.medium"
}

variable "web_instance_count" {
  description = "Number of Linux web instances (production requires >= 2 for multi-AZ)."
  type        = number
  default     = 3

  validation {
    condition     = var.web_instance_count >= 2 && var.web_instance_count <= 8
    error_message = "Production requires between 2 and 8 web instances for availability."
  }
}

variable "app_instance_count" {
  description = "Number of Linux application instances."
  type        = number
  default     = 2

  validation {
    condition     = var.app_instance_count >= 2
    error_message = "Production requires at least 2 application instances."
  }
}

variable "windows_instance_count" {
  description = "Number of Windows IIS instances."
  type        = number
  default     = 1
}

variable "key_name" {
  description = "Optional EC2 key pair. Leave null to require SSM Session Manager."
  type        = string
  default     = null
}

variable "certificate_arn" {
  description = "ACM certificate ARN. When null the ALB serves HTTP only (dev default)."
  type        = string
  default     = null
}

variable "enable_nat_gateway" {
  description = "Create NAT gateways for private subnet egress."
  type        = bool
  default     = true
}

variable "single_nat_gateway" {
  description = "Use a single NAT gateway (cheaper, non-HA). Must stay false in production."
  type        = bool
  default     = false

  validation {
    condition     = var.single_nat_gateway == false
    error_message = "Production requires one NAT gateway per AZ for availability."
  }
}

variable "enable_deletion_protection" {
  description = "Protect the ALB from accidental deletion."
  type        = bool
  default     = true

  validation {
    condition     = var.enable_deletion_protection == true
    error_message = "Deletion protection is mandatory in production."
  }
}

variable "create_github_oidc_provider" {
  description = "Create the GitHub Actions OIDC provider. One per account: false in prod, the dev-created provider is discovered."
  type        = bool
  default     = false
}

variable "github_repository" {
  description = "GitHub repository allowed to assume the CI role (owner/name)."
  type        = string
  default     = "Divakar-v-cse/Enterprise-Hybrid-Cloud-Infrastructure-Automation"
}

variable "alert_email" {
  description = "Email subscribed to the operations SNS topic. Null skips the subscription."
  type        = string
  default     = null
}

variable "flow_logs_retention_days" {
  description = "Retention for VPC flow logs (one year in production)."
  type        = number
  default     = 365
}
