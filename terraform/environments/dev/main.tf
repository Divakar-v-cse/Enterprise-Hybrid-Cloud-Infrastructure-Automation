data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

data "aws_elb_service_account" "current" {}

locals {
  name_prefix = "${var.project}-${var.environment}"

  common_tags = {
    Project     = "enterprise-hybrid-cloud"
    Environment = var.environment
    Owner       = var.owner
    CostCenter  = var.cost_center
    ManagedBy   = "terraform"
    Repository  = "Enterprise-Hybrid-Cloud-Infrastructure-Automation"
  }

  azs = slice(data.aws_availability_zones.available.names, 0, var.availability_zone_count)

  # /24 per subnet: public = 0-3, private = 10-13, data = 20-23
  subnet_map = merge(
    {
      for index, az in local.azs : "public-${index + 1}" => {
        cidr_block              = cidrsubnet(var.vpc_cidr, 8, index)
        availability_zone       = az
        tier                    = "public"
        map_public_ip_on_launch = false
      }
    },
    {
      for index, az in local.azs : "private-${index + 1}" => {
        cidr_block              = cidrsubnet(var.vpc_cidr, 8, 10 + index)
        availability_zone       = az
        tier                    = "private"
        map_public_ip_on_launch = false
      }
    },
    {
      for index, az in local.azs : "data-${index + 1}" => {
        cidr_block              = cidrsubnet(var.vpc_cidr, 8, 20 + index)
        availability_zone       = az
        tier                    = "data"
        map_public_ip_on_launch = false
      }
    }
  )

  private_subnet_ids = values(module.subnets.private_subnet_ids)
  public_subnet_ids  = values(module.subnets.public_subnet_ids)
}

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
module "vpc" {
  source = "../../modules/vpc"

  name                     = "${local.name_prefix}-vpc"
  cidr_block               = var.vpc_cidr
  enable_flow_logs         = true
  flow_logs_retention_days = var.flow_logs_retention_days
  tags                     = local.common_tags
}

module "subnets" {
  source = "../../modules/subnets"

  name    = local.name_prefix
  vpc_id  = module.vpc.vpc_id
  subnets = local.subnet_map
  tags    = local.common_tags
}

module "routing" {
  source = "../../modules/routing"

  name                     = local.name_prefix
  vpc_id                   = module.vpc.vpc_id
  internet_gateway_id      = module.vpc.internet_gateway_id
  public_subnet_ids        = module.subnets.public_subnet_ids
  public_subnet_ids_by_az  = module.subnets.public_subnet_ids_by_az
  private_subnet_ids_by_az = module.subnets.private_subnet_ids_by_az
  data_subnet_ids          = module.subnets.data_subnet_ids
  enable_nat_gateway       = var.enable_nat_gateway
  single_nat_gateway       = var.single_nat_gateway
  tags                     = local.common_tags
}

# ---------------------------------------------------------------------------
# KMS + logging bucket
# ---------------------------------------------------------------------------
resource "aws_kms_key" "ebs" {
  description             = "${local.name_prefix} EBS and log encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-ebs" })
}

resource "aws_kms_alias" "ebs" {
  name          = "alias/${local.name_prefix}-ebs"
  target_key_id = aws_kms_key.ebs.key_id
}

resource "aws_s3_bucket" "logs" {
  bucket = "${local.name_prefix}-alb-logs-${data.aws_caller_identity.current.account_id}"

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-logs" })
}

resource "aws_s3_bucket_public_access_block" "logs" {
  bucket                  = aws_s3_bucket.logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.ebs.arn
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    id     = "expire-access-logs"
    status = "Enabled"

    filter {}

    expiration {
      days = 90
    }
  }
}

data "aws_iam_policy_document" "alb_logs" {
  statement {
    sid    = "AllowALBLogDelivery"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = [data.aws_elb_service_account.current.arn]
    }

    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.logs.arn}/alb/AWSLogs/${data.aws_caller_identity.current.account_id}/*"]
  }
}

resource "aws_s3_bucket_policy" "logs" {
  bucket = aws_s3_bucket.logs.id
  policy = data.aws_iam_policy_document.alb_logs.json

  depends_on = [aws_s3_bucket_public_access_block.logs]
}

# ---------------------------------------------------------------------------
# Security groups
# ---------------------------------------------------------------------------
module "alb_security_group" {
  source = "../../modules/security-group"

  name        = "${local.name_prefix}-alb-sg"
  description = "Public ingress to the ${var.environment} application load balancer"
  vpc_id      = module.vpc.vpc_id

  ingress_rules = merge(
    {
      https = {
        description = "HTTPS from approved networks"
        ip_protocol = "tcp"
        from_port   = 443
        to_port     = 443
        cidr_ipv4   = var.ingress_cidrs[0]
      }
      http = {
        description = "HTTP redirected to HTTPS"
        ip_protocol = "tcp"
        from_port   = 80
        to_port     = 80
        cidr_ipv4   = var.ingress_cidrs[0]
      }
    },
    { for index, cidr in slice(var.ingress_cidrs, 1, length(var.ingress_cidrs)) :
      "extra-${index}" => {
        description = "Additional approved CIDR"
        ip_protocol = "tcp"
        from_port   = 443
        to_port     = 443
        cidr_ipv4   = cidr
      }
    }
  )

  egress_rules = {
    to_linux = {
      description                  = "Forward to the Linux target group"
      ip_protocol                  = "tcp"
      from_port                    = 8080
      to_port                      = 8080
      referenced_security_group_id = module.linux_security_group.security_group_id
    }
    to_windows = {
      description                  = "Forward to the Windows target group"
      ip_protocol                  = "tcp"
      from_port                    = 80
      to_port                      = 80
      referenced_security_group_id = module.windows_security_group.security_group_id
    }
  }

  tags = local.common_tags
}

module "linux_security_group" {
  source = "../../modules/security-group"

  name        = "${local.name_prefix}-linux-sg"
  description = "Linux application tier - ingress only from the load balancer"
  vpc_id      = module.vpc.vpc_id

  ingress_rules = {
    from_alb = {
      description                  = "Application traffic from the ALB"
      ip_protocol                  = "tcp"
      from_port                    = 8080
      to_port                      = 8080
      referenced_security_group_id = module.alb_security_group.security_group_id
    }
  }

  # SSM and package repositories require outbound HTTPS.
  egress_rules = {
    all = {
      description = "Outbound to NAT gateway"
      ip_protocol = "-1"
      cidr_ipv4   = "0.0.0.0/0"
    }
  }

  tags = merge(local.common_tags, { Tier = "compute", OS = "Linux" })
}

module "windows_security_group" {
  source = "../../modules/security-group"

  name        = "${local.name_prefix}-windows-sg"
  description = "Windows IIS tier - RDP restricted to the administrative CIDRs"
  vpc_id      = module.vpc.vpc_id

  ingress_rules = merge(
    {
      from_alb = {
        description                  = "HTTP from the ALB (IIS serves the site)"
        ip_protocol                  = "tcp"
        from_port                    = 80
        to_port                      = 80
        referenced_security_group_id = module.alb_security_group.security_group_id
      }
    },
    {
      for index, cidr in var.admin_cidrs : "rdp-${index}" => {
        description = "RDP from approved administrative network"
        ip_protocol = "tcp"
        from_port   = 3389
        to_port     = 3389
        cidr_ipv4   = cidr
      }
    }
  )

  egress_rules = {
    all = {
      description = "Outbound to NAT gateway"
      ip_protocol = "-1"
      cidr_ipv4   = "0.0.0.0/0"
    }
  }

  tags = merge(local.common_tags, { Tier = "compute", OS = "Windows" })
}

module "data_security_group" {
  source = "../../modules/security-group"

  name        = "${local.name_prefix}-data-sg"
  description = "Data tier - reachable only from the Linux application tier"
  vpc_id      = module.vpc.vpc_id

  ingress_rules = {
    postgres = {
      description                  = "PostgreSQL from the application tier"
      ip_protocol                  = "tcp"
      from_port                    = 5432
      to_port                      = 5432
      referenced_security_group_id = module.linux_security_group.security_group_id
    }
  }

  egress_rules = {}

  tags = merge(local.common_tags, { Tier = "data" })
}

# ---------------------------------------------------------------------------
# IAM
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "ec2_runtime" {
  statement {
    sid    = "PublishMetrics"
    effect = "Allow"
    actions = [
      "cloudwatch:PutMetricData",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "ReadArtifacts"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:ListBucket"]
    resources = ["arn:aws:s3:::${local.name_prefix}-artifacts", "arn:aws:s3:::${local.name_prefix}-artifacts/*"]
  }
}

module "ec2_role" {
  source = "../../modules/iam"

  name                     = "${local.name_prefix}-ec2-role"
  description              = "Runtime role for ${var.environment} compute - SSM, CloudWatch, artifacts"
  create_instance_profile  = true
  managed_policy_arns      = ["arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"]
  inline_policies          = { runtime = data.aws_iam_policy_document.ec2_runtime.json }
  permissions_boundary_arn = aws_iam_policy.boundary.arn

  tags = local.common_tags
}

resource "aws_iam_policy" "boundary" {
  name        = "${local.name_prefix}-boundary"
  description = "Permissions boundary preventing privilege escalation from ${var.environment}"
  path        = "/"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCoreServices"
        Effect = "Allow"
        Action = [
          "s3:*",
          "logs:*",
          "cloudwatch:*",
          "ec2:Describe*",
          "ssm:*",
          "secretsmanager:GetSecretValue",
          "kms:Decrypt",
          "kms:DescribeKey",
        ]
        Resource = "*"
      },
      {
        Sid      = "DenyIdentityEscalation"
        Effect   = "Deny"
        Action   = ["iam:*", "organizations:*", "account:*"]
        Resource = "*"
      },
    ]
  })

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# GitHub Actions OIDC (keyless CI/CD)
# ---------------------------------------------------------------------------
resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 1 : 0

  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]

  tags = local.common_tags
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 0 : 1

  url = "https://token.actions.githubusercontent.com"
}

locals {
  github_oidc_arn = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn
}

data "aws_iam_policy_document" "github_assume_role" {
  statement {
    sid     = "GitHubActionsOIDC"
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_repository}:ref:refs/heads/main",
        "repo:${var.github_repository}:pull_request",
        "repo:${var.github_repository}:environment:${var.environment}",
      ]
    }
  }
}

data "aws_iam_policy_document" "github_permissions" {
  statement {
    sid    = "TerraformState"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:ListBucket",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
      "dynamodb:DescribeTable",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "ManageEnvironment"
    effect = "Allow"
    actions = [
      "ec2:*",
      "elasticloadbalancing:*",
      "iam:Get*",
      "iam:List*",
      "iam:PassRole",
      "kms:Describe*",
      "kms:List*",
      "s3:GetBucketPolicy",
      "logs:Describe*",
      "cloudwatch:Describe*",
    ]
    resources = ["*"]
  }
}

module "github_actions_role" {
  source = "../../modules/iam"

  name                 = "${local.name_prefix}-github-oidc-role"
  description          = "Assumed by GitHub Actions via OIDC to plan and apply ${var.environment}"
  trust_policy_json    = data.aws_iam_policy_document.github_assume_role.json
  inline_policies      = { deploy = data.aws_iam_policy_document.github_permissions.json }
  max_session_duration = 3600

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------
resource "aws_sns_topic" "alerts" {
  name = "${local.name_prefix}-alerts"

  tags = local.common_tags
}

resource "aws_sns_topic_subscription" "email" {
  count = var.alert_email != null ? 1 : 0

  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------
locals {
  linux_user_data = <<-EOT
    #!/bin/bash
    set -euo pipefail
    systemctl enable --now amazon-ssm-agent || true
    hostnamectl set-hostname "$(ec2-metadata --local-hostname 2>/dev/null | cut -d' ' -f2 || hostname)"
    echo "hccp bootstrap complete" > /var/log/hccp-bootstrap.log
  EOT

  windows_user_data = <<-EOT
    <powershell>
    Set-Service -Name AmazonSSMAgent -StartupType Automatic -ErrorAction SilentlyContinue
    Start-Service AmazonSSMAgent -ErrorAction SilentlyContinue
    New-Item -Path C:\hccp-bootstrap.log -ItemType File -Force | Out-Null
    Add-Content -Path C:\hccp-bootstrap.log -Value "hccp bootstrap complete"
    </powershell>
  EOT

  instances = merge(
    {
      for index in range(var.web_instance_count) : format("web-%02d", index + 1) => {
        subnet_id                   = local.private_subnet_ids[index % length(local.private_subnet_ids)]
        instance_type               = var.web_instance_type
        os                          = "linux"
        user_data                   = local.linux_user_data
        patch_group                 = "${var.environment}-linux"
        role                        = "web"
        associate_public_ip_address = false
      }
    },
    {
      for index in range(var.app_instance_count) : format("app-%02d", index + 1) => {
        subnet_id                   = local.private_subnet_ids[(index + 1) % length(local.private_subnet_ids)]
        instance_type               = var.app_instance_type
        os                          = "linux"
        user_data                   = local.linux_user_data
        patch_group                 = "${var.environment}-linux"
        role                        = "app"
        associate_public_ip_address = false
      }
    },
    {
      for index in range(var.windows_instance_count) : format("win-%02d", index + 1) => {
        subnet_id                   = local.private_subnet_ids[(index + 2) % length(local.private_subnet_ids)]
        instance_type               = var.windows_instance_type
        os                          = "windows"
        user_data                   = local.windows_user_data
        patch_group                 = "${var.environment}-windows"
        role                        = "web"
        associate_public_ip_address = false
      }
    }
  )
}

module "compute" {
  source = "../../modules/ec2"

  name                      = local.name_prefix
  instances                 = local.instances
  security_group_ids        = [module.linux_security_group.security_group_id, module.windows_security_group.security_group_id]
  iam_instance_profile_name = module.ec2_role.instance_profile_name
  key_name                  = var.key_name
  kms_key_arn               = aws_kms_key.ebs.arn
  alarm_sns_topic_arn       = aws_sns_topic.alerts.arn
  tags                      = local.common_tags
}

# ---------------------------------------------------------------------------
# Ingress
# ---------------------------------------------------------------------------
module "load_balancer" {
  source = "../../modules/alb"

  name                       = substr("${local.name_prefix}-alb", 0, 32)
  vpc_id                     = module.vpc.vpc_id
  subnet_ids                 = local.public_subnet_ids
  security_group_ids         = [module.alb_security_group.security_group_id]
  certificate_arn            = var.certificate_arn
  enable_deletion_protection = var.enable_deletion_protection
  access_logs_bucket         = aws_s3_bucket.logs.id
  default_target_group       = "linux"

  target_groups = {
    linux = {
      port              = 8080
      protocol          = "HTTP"
      health_check_path = "/healthz"
    }
    windows = {
      port              = 80
      protocol          = "HTTP"
      health_check_path = "/health"
    }
  }

  tags = local.common_tags
}
