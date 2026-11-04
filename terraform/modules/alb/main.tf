locals {
  https_enabled = var.certificate_arn != null
  tags          = merge(var.tags, { Module = "alb" })
}

resource "aws_lb" "this" {
  name                             = var.name
  internal                         = var.internal
  load_balancer_type               = "application"
  security_groups                  = var.security_group_ids
  subnets                          = var.subnet_ids
  idle_timeout                     = var.idle_timeout
  enable_deletion_protection       = var.enable_deletion_protection
  enable_http2                     = true
  drop_invalid_header_fields       = var.drop_invalid_header_fields
  enable_cross_zone_load_balancing = true

  dynamic "access_logs" {
    for_each = var.enable_access_logs ? [1] : []

    content {
      bucket  = var.access_logs_bucket
      prefix  = var.access_logs_prefix
      enabled = true
    }
  }

  tags = merge(local.tags, { Name = var.name })

  lifecycle {
    precondition {
      condition     = !var.enable_access_logs || var.access_logs_bucket != null
      error_message = "access_logs_bucket must be provided when enable_access_logs is true."
    }
  }
}

resource "aws_lb_target_group" "this" {
  for_each = var.target_groups

  name                 = substr("${var.name}-${each.key}", 0, 32)
  port                 = each.value.port
  protocol             = each.value.protocol
  target_type          = each.value.target_type
  vpc_id               = var.vpc_id
  deregistration_delay = 30

  health_check {
    enabled             = true
    path                = each.value.health_check_path
    matcher             = each.value.health_check_matcher
    interval            = each.value.interval
    timeout             = each.value.timeout
    healthy_threshold   = each.value.healthy_threshold
    unhealthy_threshold = each.value.unhealthy_threshold
    protocol            = each.value.protocol == "HTTPS" ? "HTTPS" : "HTTP"
  }

  dynamic "stickiness" {
    for_each = each.value.stickiness_enabled ? [1] : []

    content {
      type            = "lb_cookie"
      cookie_duration = 3600
      enabled         = true
    }
  }

  tags = merge(local.tags, { Name = "${var.name}-${each.key}" })
}

# HTTPS listener (preferred path)
resource "aws_lb_listener" "https" {
  count = local.https_enabled ? 1 : 0

  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = var.ssl_policy
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this[var.default_target_group].arn
  }

  tags = local.tags
}

# HTTP listener: redirect to HTTPS when TLS is configured, otherwise forward.
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  dynamic "default_action" {
    for_each = local.https_enabled ? [1] : []

    content {
      type = "redirect"

      redirect {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  }

  dynamic "default_action" {
    for_each = local.https_enabled ? [] : [1]

    content {
      type             = "forward"
      target_group_arn = aws_lb_target_group.this[var.default_target_group].arn
    }
  }

  tags = local.tags
}
