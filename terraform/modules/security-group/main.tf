resource "aws_security_group" "this" {
  name        = var.name
  description = var.description
  vpc_id      = var.vpc_id

  tags = merge(var.tags, { Name = var.name, Module = "security-group" })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "this" {
  for_each = var.ingress_rules

  security_group_id = aws_security_group.this.id
  description       = each.value.description != "" ? each.value.description : each.key
  ip_protocol       = each.value.ip_protocol
  from_port         = each.value.from_port
  to_port           = each.value.to_port
  cidr_ipv4         = each.value.cidr_ipv4
  referenced_security_group_id = (
    each.value.referenced_security_group_id != null ? each.value.referenced_security_group_id : null
  )

  tags = merge(var.tags, { Name = "${var.name}-${each.key}" })

  lifecycle {
    precondition {
      condition     = (each.value.cidr_ipv4 != null) != (each.value.referenced_security_group_id != null)
      error_message = "Ingress rule '${each.key}' must set exactly one of cidr_ipv4 or referenced_security_group_id."
    }
  }
}

resource "aws_vpc_security_group_egress_rule" "this" {
  for_each = var.egress_rules

  security_group_id = aws_security_group.this.id
  description       = each.value.description != "" ? each.value.description : each.key
  ip_protocol       = each.value.ip_protocol
  from_port         = each.value.from_port
  to_port           = each.value.to_port
  cidr_ipv4         = each.value.cidr_ipv4
  referenced_security_group_id = (
    each.value.referenced_security_group_id != null ? each.value.referenced_security_group_id : null
  )

  tags = merge(var.tags, { Name = "${var.name}-${each.key}" })

  lifecycle {
    precondition {
      condition     = (each.value.cidr_ipv4 != null) != (each.value.referenced_security_group_id != null)
      error_message = "Egress rule '${each.key}' must set exactly one of cidr_ipv4 or referenced_security_group_id."
    }
  }
}
