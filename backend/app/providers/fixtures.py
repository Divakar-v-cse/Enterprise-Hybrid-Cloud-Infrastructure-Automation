"""Deterministic demo inventory.

This is the fixture used by the ``mock`` provider so the dashboard, drift
engine and compliance scanner can be exercised locally and in CI without AWS
credentials. Names, tags and configuration mirror what the Terraform
environments actually create, so the shapes stay honest.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.schemas import (
    Environment,
    HealthSnapshot,
    HealthStatus,
    PatchStatus,
    Resource,
    ResourceKind,
    ResourceStatus,
)

_NOW = datetime.now(UTC)
_CREATED = _NOW - timedelta(days=42)
_OWNER = "platform-engineering"
_COST_CENTER = "CC-4471"


def _tags(env: str, tier: str, **extra: str) -> dict[str, str]:
    tags = {
        "Environment": env,
        "Owner": _OWNER,
        "CostCenter": _COST_CENTER,
        "ManagedBy": "terraform",
        "Tier": tier,
    }
    tags.update(extra)
    return tags


def _health(
    *,
    cpu: float,
    memory: float,
    disk: float,
    patch: PatchStatus,
    uptime: int,
    agent: str = "2.14.3",
) -> HealthSnapshot:
    """Derive a 0-100 health score from the resource signals."""
    score = 100.0
    score -= max(0.0, cpu - 70) * 0.9
    score -= max(0.0, memory - 75) * 1.1
    score -= max(0.0, disk - 80) * 1.4
    if patch is PatchStatus.PENDING:
        score -= 8
    elif patch is PatchStatus.OVERDUE:
        score -= 25
    score = int(max(0, min(100, round(score))))
    status = (
        HealthStatus.HEALTHY
        if score >= 85
        else HealthStatus.WARNING
        if score >= 60
        else HealthStatus.CRITICAL
    )
    return HealthSnapshot(
        score=score,
        status=status,
        cpu_percent=cpu,
        memory_percent=memory,
        disk_percent=disk,
        patch_status=patch,
        agent_version=agent,
        uptime_hours=uptime,
        last_seen=_NOW - timedelta(minutes=2),
    )


def _vpc(env: str, cidr: str, flow_logs: bool = True) -> Resource:
    return Resource(
        id=f"vpc-{env}-01",
        name=f"hccp-{env}-vpc",
        kind=ResourceKind.VPC,
        environment=Environment(env),
        region="ap-south-1",
        status=ResourceStatus.AVAILABLE,
        owner=_OWNER,
        monthly_cost_usd=0.0,
        created_at=_CREATED,
        tags=_tags(env, "network"),
        config={
            "cidr_block": cidr,
            "flow_logs_enabled": flow_logs,
            "dns_hostnames": True,
            "dns_support": True,
            "availability_zones": ["ap-south-1a", "ap-south-1b", "ap-south-1c"],
        },
    )


def _subnets(env: str, base: int) -> list[Resource]:
    prefixes = {"public": 0, "private": 16, "data": 32}
    zones = ["ap-south-1a", "ap-south-1b", "ap-south-1c"]
    resources: list[Resource] = []
    for tier, offset in prefixes.items():
        for index, zone in enumerate(zones, start=1):
            name = f"hccp-{env}-{tier}-{index}"
            resources.append(
                Resource(
                    id=f"subnet-{env}-{tier}-{index}",
                    name=name,
                    kind=ResourceKind.SUBNET,
                    environment=Environment(env),
                    region="ap-south-1",
                    status=ResourceStatus.AVAILABLE,
                    owner=_OWNER,
                    monthly_cost_usd=0.0,
                    created_at=_CREATED,
                    tags=_tags(env, tier),
                    config={
                        "cidr_block": f"10.{base}.{offset + index * 4}.0/24",
                        "availability_zone": zone,
                        "tier": tier,
                        "map_public_ip_on_launch": tier == "public",
                    },
                )
            )
    return resources


def _route_tables(env: str) -> list[Resource]:
    return [
        Resource(
            id=f"rtb-{env}-public",
            name=f"hccp-{env}-public-rt",
            kind=ResourceKind.ROUTE_TABLE,
            environment=Environment(env),
            region="ap-south-1",
            status=ResourceStatus.AVAILABLE,
            owner=_OWNER,
            monthly_cost_usd=0.0,
            created_at=_CREATED,
            tags=_tags(env, "network"),
            config={"routes": ["0.0.0.0/0 -> igw", "10.0.0.0/8 -> local"], "associated_tiers": ["public"]},
        ),
        Resource(
            id=f"rtb-{env}-private",
            name=f"hccp-{env}-private-rt",
            kind=ResourceKind.ROUTE_TABLE,
            environment=Environment(env),
            region="ap-south-1",
            status=ResourceStatus.AVAILABLE,
            owner=_OWNER,
            monthly_cost_usd=0.0,
            created_at=_CREATED,
            tags=_tags(env, "network"),
            config={
                "routes": ["0.0.0.0/0 -> nat", "10.0.0.0/8 -> local"],
                "associated_tiers": ["private", "data"],
            },
        ),
    ]


def _security_groups(env: str, *, open_ssh: bool = False) -> list[Resource]:
    web_ingress = [
        {"protocol": "tcp", "from_port": 443, "to_port": 443, "cidr": "0.0.0.0/0"},
        {"protocol": "tcp", "from_port": 80, "to_port": 80, "cidr": "0.0.0.0/0"},
    ]
    if open_ssh:
        web_ingress.append(
            {"protocol": "tcp", "from_port": 22, "to_port": 22, "cidr": "0.0.0.0/0"}
        )
    return [
        Resource(
            id=f"sg-{env}-alb",
            name=f"hccp-{env}-alb-sg",
            kind=ResourceKind.SECURITY_GROUP,
            environment=Environment(env),
            region="ap-south-1",
            status=ResourceStatus.AVAILABLE,
            owner=_OWNER,
            monthly_cost_usd=0.0,
            created_at=_CREATED,
            tags=_tags(env, "edge"),
            config={
                "description": "Public ingress for the application load balancer",
                "ingress": web_ingress,
                "egress": [{"protocol": "tcp", "from_port": 443, "to_port": 443, "cidr": "0.0.0.0/0"}],
            },
        ),
        Resource(
            id=f"sg-{env}-linux",
            name=f"hccp-{env}-linux-sg",
            kind=ResourceKind.SECURITY_GROUP,
            environment=Environment(env),
            region="ap-south-1",
            status=ResourceStatus.AVAILABLE,
            owner=_OWNER,
            monthly_cost_usd=0.0,
            created_at=_CREATED,
            tags=_tags(env, "compute"),
            config={
                "description": "Linux application tier - ingress only from the ALB",
                "ingress": [
                    {"protocol": "tcp", "from_port": 8080, "to_port": 8080, "source_sg": f"sg-{env}-alb"},
                ],
                "egress": [{"protocol": "-1", "from_port": 0, "to_port": 0, "cidr": "0.0.0.0/0"}],
            },
        ),
        Resource(
            id=f"sg-{env}-windows",
            name=f"hccp-{env}-windows-sg",
            kind=ResourceKind.SECURITY_GROUP,
            environment=Environment(env),
            region="ap-south-1",
            status=ResourceStatus.AVAILABLE,
            owner=_OWNER,
            monthly_cost_usd=0.0,
            created_at=_CREATED,
            tags=_tags(env, "compute"),
            config={
                "description": "Windows IIS tier - RDP from the bastion only",
                "ingress": [
                    {"protocol": "tcp", "from_port": 3389, "to_port": 3389, "cidr": "10.20.0.0/24"},
                    {"protocol": "tcp", "from_port": 443, "to_port": 443, "source_sg": f"sg-{env}-alb"},
                ],
                "egress": [{"protocol": "-1", "from_port": 0, "to_port": 0, "cidr": "0.0.0.0/0"}],
            },
        ),
        Resource(
            id=f"sg-{env}-data",
            name=f"hccp-{env}-data-sg",
            kind=ResourceKind.SECURITY_GROUP,
            environment=Environment(env),
            region="ap-south-1",
            status=ResourceStatus.AVAILABLE,
            owner=_OWNER,
            monthly_cost_usd=0.0,
            created_at=_CREATED,
            tags=_tags(env, "data"),
            config={
                "description": "Database tier - no internet ingress",
                "ingress": [
                    {"protocol": "tcp", "from_port": 5432, "to_port": 5432, "source_sg": f"sg-{env}-linux"},
                ],
                "egress": [],
            },
        ),
    ]


def _iam(env: str, *, wildcard: bool = False) -> list[Resource]:
    statements = (
        [{"Effect": "Allow", "Action": "*", "Resource": "*"}]
        if wildcard
        else [
            {"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "arn:aws:s3:::hccp-artifacts/*"},
            {"Effect": "Allow", "Action": ["logs:CreateLogStream", "logs:PutLogEvents"], "Resource": "*"},
        ]
    )
    return [
        Resource(
            id=f"role-{env}-ec2",
            name=f"hccp-{env}-ec2-role",
            kind=ResourceKind.IAM_ROLE,
            environment=Environment(env),
            region="ap-south-1",
            status=ResourceStatus.AVAILABLE,
            owner=_OWNER,
            monthly_cost_usd=0.0,
            created_at=_CREATED,
            tags=_tags(env, "identity"),
            config={
                "assume_role_policy": {"Service": "ec2.amazonaws.com"},
                "inline_policies": [{"name": "runtime-access", "statements": statements}],
                "instance_profile": f"hccp-{env}-ec2-profile",
                "permissions_boundary": f"arn:aws:iam::123456789012:policy/hccp-{env}-boundary",
            },
        ),
        Resource(
            id=f"role-{env}-ssm",
            name=f"hccp-{env}-ssm-role",
            kind=ResourceKind.IAM_ROLE,
            environment=Environment(env),
            region="ap-south-1",
            status=ResourceStatus.AVAILABLE,
            owner=_OWNER,
            monthly_cost_usd=0.0,
            created_at=_CREATED,
            tags=_tags(env, "identity"),
            config={
                "assume_role_policy": {"Service": "ec2.amazonaws.com"},
                "managed_policies": ["arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"],
                "instance_profile": f"hccp-{env}-ssm-profile",
            },
        ),
        Resource(
            id=f"role-{env}-cicd",
            name=f"hccp-{env}-github-oidc-role",
            kind=ResourceKind.IAM_ROLE,
            environment=Environment(env),
            region="ap-south-1",
            status=ResourceStatus.AVAILABLE,
            owner=_OWNER,
            monthly_cost_usd=0.0,
            created_at=_CREATED,
            tags=_tags(env, "identity"),
            config={
                "assume_role_policy": {"Service": "oidc"},
                "federated_provider": "token.actions.githubusercontent.com",
                "condition": f"repo:Divakar-v-cse/*:ref:refs/heads/main:environment:{env}",
            },
        ),
    ]


def _ec2(
    env: str,
    suffix: str,
    *,
    os_name: str,
    instance_type: str,
    private_ip: str,
    public_ip: str | None,
    health: HealthSnapshot,
    imds_v2: bool = True,
    ebs_encrypted: bool = True,
    tags: dict[str, str] | None = None,
) -> Resource:
    display = "linux" if os_name.lower().startswith("linux") else "windows"
    return Resource(
        id=f"i-{env}-{suffix}",
        name=f"hccp-{env}-{suffix}",
        kind=ResourceKind.EC2,
        environment=Environment(env),
        region="ap-south-1",
        status=ResourceStatus.RUNNING,
        owner=_OWNER,
        monthly_cost_usd={"t3.micro": 8.47, "t3.medium": 33.87, "m6i.large": 76.65}.get(
            instance_type, 45.0
        ),
        created_at=_CREATED,
        tags=tags or _tags(env, "compute", PatchGroup=f"{env}-{display}"),
        config={
            "instance_type": instance_type,
            "os": "Linux" if display == "linux" else "Windows Server 2022",
            "ami": "ami-0a7f4c2b1f9a1c3d4",
            "private_ip": private_ip,
            "public_ip": public_ip,
            "availability_zone": "ap-south-1a",
            "imds_v2_required": imds_v2,
            "ebs_encrypted": ebs_encrypted,
            "ssm_managed": True,
            "backup_enabled": True,
            "subnet_tier": "private",
        },
        health=health,
    )


def _alb(env: str, *, deletion_protection: bool, access_logs: bool = True) -> list[Resource]:
    return [
        Resource(
            id=f"alb-{env}-01",
            name=f"hccp-{env}-alb",
            kind=ResourceKind.LOAD_BALANCER,
            environment=Environment(env),
            region="ap-south-1",
            status=ResourceStatus.AVAILABLE,
            owner=_OWNER,
            monthly_cost_usd=22.4,
            created_at=_CREATED,
            tags=_tags(env, "edge"),
            config={
                "scheme": "internet-facing",
                "type": "application",
                "listeners": [{"port": 443, "protocol": "HTTPS"}, {"port": 80, "protocol": "HTTP", "redirect_to": 443}],
                "deletion_protection": deletion_protection,
                "access_logs_enabled": access_logs,
                "drop_invalid_headers": True,
                "waf_attached": True,
            },
        ),
        Resource(
            id=f"tg-{env}-linux",
            name=f"hccp-{env}-linux-tg",
            kind=ResourceKind.TARGET_GROUP,
            environment=Environment(env),
            region="ap-south-1",
            status=ResourceStatus.AVAILABLE,
            owner=_OWNER,
            monthly_cost_usd=0.0,
            created_at=_CREATED,
            tags=_tags(env, "edge"),
            config={"port": 8080, "protocol": "HTTP", "health_check_path": "/healthz", "targets": 2},
        ),
        Resource(
            id=f"tg-{env}-windows",
            name=f"hccp-{env}-windows-tg",
            kind=ResourceKind.TARGET_GROUP,
            environment=Environment(env),
            region="ap-south-1",
            status=ResourceStatus.AVAILABLE,
            owner=_OWNER,
            monthly_cost_usd=0.0,
            created_at=_CREATED,
            tags=_tags(env, "edge"),
            config={"port": 443, "protocol": "HTTPS", "health_check_path": "/health", "targets": 1},
        ),
    ]


def build_inventory() -> list[Resource]:
    """Return the full demo inventory for dev and prod."""
    resources: list[Resource] = []

    # ---- development ------------------------------------------------------
    resources.append(_vpc("dev", "10.20.0.0/16"))
    resources.extend(_subnets("dev", 20))
    resources.extend(_route_tables("dev"))
    resources.extend(_security_groups("dev", open_ssh=True))
    resources.extend(_iam("dev", wildcard=True))
    resources.append(
        _ec2(
            "dev",
            "web-01",
            os_name="Linux",
            instance_type="t3.micro",
            private_ip="10.20.16.11",
            public_ip=None,
            health=_health(cpu=34.2, memory=48.7, disk=41.2, patch=PatchStatus.COMPLIANT, uptime=312),
        )
    )
    resources.append(
        _ec2(
            "dev",
            "app-01",
            os_name="Linux",
            instance_type="t3.micro",
            private_ip="10.20.16.12",
            public_ip=None,
            health=_health(cpu=71.8, memory=82.4, disk=63.1, patch=PatchStatus.PENDING, uptime=312),
            tags=_tags("dev", "compute", PatchGroup="dev-linux", CostCenter=""),
        )
    )
    resources.append(
        _ec2(
            "dev",
            "win-01",
            os_name="Windows",
            instance_type="t3.medium",
            private_ip="10.20.16.21",
            public_ip=None,
            health=_health(cpu=22.4, memory=61.2, disk=55.8, patch=PatchStatus.OVERDUE, uptime=180),
            imds_v2=False,
        )
    )
    resources.extend(_alb("dev", deletion_protection=False))

    # ---- production -------------------------------------------------------
    resources.append(_vpc("prod", "10.10.0.0/16"))
    resources.extend(_subnets("prod", 10))
    resources.extend(_route_tables("prod"))
    resources.extend(_security_groups("prod"))
    resources.extend(_iam("prod"))
    for index, health in enumerate(
        (
            _health(cpu=41.5, memory=58.3, disk=47.9, patch=PatchStatus.COMPLIANT, uptime=2_190),
            _health(cpu=52.1, memory=66.4, disk=51.2, patch=PatchStatus.COMPLIANT, uptime=2_190),
            _health(cpu=88.6, memory=91.2, disk=86.4, patch=PatchStatus.OVERDUE, uptime=1_204),
        ),
        start=1,
    ):
        resources.append(
            _ec2(
                "prod",
                f"web-{index:02d}",
                os_name="Linux",
                instance_type="m6i.large",
                private_ip=f"10.10.16.{10 + index}",
                public_ip=None,
                health=health,
            )
        )
    for index, health in enumerate(
        (
            _health(cpu=37.2, memory=54.9, disk=44.1, patch=PatchStatus.COMPLIANT, uptime=2_190),
            _health(cpu=44.8, memory=62.7, disk=49.6, patch=PatchStatus.PENDING, uptime=2_190),
        ),
        start=1,
    ):
        resources.append(
            _ec2(
                "prod",
                f"app-{index:02d}",
                os_name="Linux",
                instance_type="m6i.large",
                private_ip=f"10.10.16.{30 + index}",
                public_ip=None,
                health=health,
            )
        )
    resources.append(
        _ec2(
            "prod",
            "win-01",
            os_name="Windows",
            instance_type="t3.medium",
            private_ip="10.10.16.41",
            public_ip=None,
            health=_health(cpu=28.7, memory=63.5, disk=58.2, patch=PatchStatus.COMPLIANT, uptime=2_190),
        )
    )
    resources.extend(_alb("prod", deletion_protection=True))
    return resources
