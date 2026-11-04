"""AWS provider backed by boto3 ``describe`` calls (read-only).

Design notes
------------
* The provider is read-only by design. Mutations belong to Terraform, which is
  the single source of truth for infrastructure state; the control plane only
  observes and orchestrates pipelines. This prevents console drift.
* Credentials resolve through the standard boto3 chain (SSO, instance profile,
  GitHub OIDC role). No keys are ever read from this repository.
* ``describe_*`` calls are paginated for you by boto3 resource collections.
"""

from __future__ import annotations

import time
from typing import Any

from app.core.logging import get_logger
from app.providers.base import ProviderError, ProviderHealth
from app.schemas import (
    Environment,
    HealthSnapshot,
    HealthStatus,
    PatchStatus,
    Resource,
    ResourceKind,
    ResourceStatus,
)

logger = get_logger(__name__)

_STATE_MAP = {
    "running": ResourceStatus.RUNNING,
    "stopped": ResourceStatus.STOPPED,
    "pending": ResourceStatus.PENDING,
    "stopping": ResourceStatus.PENDING,
    "available": ResourceStatus.AVAILABLE,
    "active": ResourceStatus.AVAILABLE,
}

_MONTHLY_HOURS = 730.0
# Approximate on-demand hourly prices (ap-south-1, USD) used for chargeback
# estimates. Replace with Cost Explorer data in a production deployment.
_HOURLY_PRICE = {
    "t3.micro": 0.0116,
    "t3.medium": 0.0464,
    "t3.large": 0.0928,
    "m6i.large": 0.1050,
    "m6i.xlarge": 0.2100,
    "c6i.large": 0.0940,
}
_ALB_HOURLY = 0.0307


class AWSProvider:
    name = "aws"

    def __init__(self, region: str = "ap-south-1", profile: str | None = None) -> None:
        self.region = region
        self._profile = profile
        self._session: Any | None = None

    # -- session ------------------------------------------------------------
    def _get_session(self) -> Any:
        if self._session is None:
            try:
                import boto3
            except ImportError as exc:  # pragma: no cover - boto3 is a hard dep
                raise ProviderError("boto3 is not installed") from exc
            try:
                self._session = boto3.Session(profile_name=self._profile, region_name=self.region)
            except Exception as exc:  # noqa: BLE001 - surfaced as provider error
                raise ProviderError(f"unable to create AWS session: {exc}") from exc
        return self._session

    def _client(self, service: str) -> Any:
        return self._get_session().client(service, region_name=self.region)

    # -- mapping helpers ----------------------------------------------------
    @staticmethod
    def _tags(tag_list: list[dict[str, str]] | None) -> dict[str, str]:
        return {tag.get("Key", ""): tag.get("Value", "") for tag in tag_list or []}

    @staticmethod
    def _environment(tags: dict[str, str]) -> Environment | None:
        raw = tags.get("Environment", "").lower()
        return {"dev": Environment.DEV, "development": Environment.DEV, "prod": Environment.PROD,
                "production": Environment.PROD}.get(raw)

    def _environment_filter(self) -> list[dict[str, Any]]:
        return [{"Name": "tag:Environment", "Values": ["dev", "development", "prod", "production"]}]

    # -- protocol -----------------------------------------------------------
    def list_resources(self, environment: Environment | None = None) -> list[Resource]:
        resources: list[Resource] = []
        for loader in (self._load_vpcs, self._load_subnets, self._load_security_groups,
                       self._load_instances, self._load_load_balancers):
            try:
                resources.extend(loader())
            except Exception as exc:  # noqa: BLE001 - degrade gracefully per service
                logger.warning(
                    "aws describe call failed",
                    extra={"loader": loader.__name__, "error": str(exc)},
                )
        if environment is not None:
            target = Environment(environment).value
            resources = [r for r in resources if r.environment == target]
        return resources

    def get_resource(self, resource_id: str) -> Resource | None:
        return next((r for r in self.list_resources() if r.id == resource_id), None)

    def health(self) -> ProviderHealth:
        started = time.perf_counter()
        try:
            self._client("sts").get_caller_identity()
        except Exception as exc:  # noqa: BLE001
            return ProviderHealth(
                provider=self.name,
                reachable=False,
                region=self.region,
                detail=str(exc),
                latency_ms=round((time.perf_counter() - started) * 1000, 1),
            )
        return ProviderHealth(
            provider=self.name,
            reachable=True,
            region=self.region,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
        )

    # -- loaders ------------------------------------------------------------
    def _load_vpcs(self) -> list[Resource]:
        client = self._client("ec2")
        out: list[Resource] = []
        for vpc in client.describe_vpcs(Filters=self._environment_filter())["Vpcs"]:
            tags = self._tags(vpc.get("Tags"))
            env = self._environment(tags)
            if env is None:
                continue
            out.append(
                Resource(
                    id=vpc["VpcId"],
                    name=tags.get("Name", vpc["VpcId"]),
                    kind=ResourceKind.VPC,
                    environment=env,
                    region=self.region,
                    status=ResourceStatus.AVAILABLE,
                    owner=tags.get("Owner", "unknown"),
                    monthly_cost_usd=0.0,
                    tags=tags,
                    config={
                        "cidr_block": vpc.get("CidrBlock"),
                        "flow_logs_enabled": self._flow_logs_enabled(vpc["VpcId"]),
                        "dns_support": vpc.get("EnableDnsSupport", True),
                        "dns_hostnames": vpc.get("EnableDnsHostnames", False),
                    },
                )
            )
        return out

    def _flow_logs_enabled(self, vpc_id: str) -> bool:
        try:
            logs = self._client("ec2").describe_flow_logs(
                Filters=[{"Name": "resource-id", "Values": [vpc_id]}]
            )["FlowLogs"]
        except Exception:  # noqa: BLE001
            return False
        return any(log.get("FlowLogStatus") == "ACTIVE" for log in logs)

    def _load_subnets(self) -> list[Resource]:
        client = self._client("ec2")
        out: list[Resource] = []
        for subnet in client.describe_subnets(Filters=self._environment_filter())["Subnets"]:
            tags = self._tags(subnet.get("Tags"))
            env = self._environment(tags)
            if env is None:
                continue
            out.append(
                Resource(
                    id=subnet["SubnetId"],
                    name=tags.get("Name", subnet["SubnetId"]),
                    kind=ResourceKind.SUBNET,
                    environment=env,
                    region=self.region,
                    status=ResourceStatus.AVAILABLE,
                    owner=tags.get("Owner", "unknown"),
                    monthly_cost_usd=0.0,
                    tags=tags,
                    config={
                        "cidr_block": subnet.get("CidrBlock"),
                        "availability_zone": subnet.get("AvailabilityZone"),
                        "tier": tags.get("Tier", "private"),
                        "map_public_ip_on_launch": subnet.get("MapPublicIpOnLaunch", False),
                    },
                )
            )
        return out

    def _load_security_groups(self) -> list[Resource]:
        client = self._client("ec2")
        out: list[Resource] = []
        for group in client.describe_security_groups(Filters=self._environment_filter())["SecurityGroups"]:
            tags = self._tags(group.get("Tags"))
            env = self._environment(tags)
            if env is None:
                continue
            ingress = []
            for permission in group.get("IpPermissions", []):
                for ip_range in permission.get("IpRanges", []):
                    ingress.append(
                        {
                            "protocol": permission.get("IpProtocol", "-1"),
                            "from_port": permission.get("FromPort", 0),
                            "to_port": permission.get("ToPort", 0),
                            "cidr": ip_range.get("CidrIp"),
                        }
                    )
            out.append(
                Resource(
                    id=group["GroupId"],
                    name=tags.get("Name", group.get("GroupName", group["GroupId"])),
                    kind=ResourceKind.SECURITY_GROUP,
                    environment=env,
                    region=self.region,
                    status=ResourceStatus.AVAILABLE,
                    owner=tags.get("Owner", "unknown"),
                    monthly_cost_usd=0.0,
                    tags=tags,
                    config={"description": group.get("Description", ""), "ingress": ingress},
                )
            )
        return out

    def _load_instances(self) -> list[Resource]:
        client = self._client("ec2")
        out: list[Resource] = []
        paginator = client.get_paginator("describe_instances")
        for page in paginator.paginate(Filters=self._environment_filter()):
            for reservation in page["Reservations"]:
                for instance in reservation["Instances"]:
                    tags = self._tags(instance.get("Tags"))
                    env = self._environment(tags)
                    if env is None:
                        continue
                    instance_type = instance.get("InstanceType", "t3.micro")
                    platform = instance.get("Platform", "linux")
                    state = instance.get("State", {}).get("Name", "pending")
                    private_ip = instance.get("PrivateIpAddress")
                    health = HealthSnapshot(
                        score=90 if state == "running" else 40,
                        status=HealthStatus.HEALTHY if state == "running" else HealthStatus.WARNING,
                        cpu_percent=0.0,
                        memory_percent=0.0,
                        disk_percent=0.0,
                        patch_status=PatchStatus.PENDING,
                        agent_version="unknown",
                        uptime_hours=0,
                    )
                    out.append(
                        Resource(
                            id=instance["InstanceId"],
                            name=tags.get("Name", instance["InstanceId"]),
                            kind=ResourceKind.EC2,
                            environment=env,
                            region=self.region,
                            status=_STATE_MAP.get(state, ResourceStatus.PENDING),
                            owner=tags.get("Owner", "unknown"),
                            monthly_cost_usd=round(_HOURLY_PRICE.get(instance_type, 0.05) * _MONTHLY_HOURS, 2),
                            tags=tags,
                            config={
                                "instance_type": instance_type,
                                "os": "Windows Server" if platform == "windows" else "Linux",
                                "ami": instance.get("ImageId"),
                                "private_ip": private_ip,
                                "public_ip": instance.get("PublicIpAddress"),
                                "availability_zone": instance.get("Placement", {}).get("AvailabilityZone"),
                                "imds_v2_required": instance.get("MetadataOptions", {}).get(
                                    "HttpTokens"
                                )
                                == "required",
                                "ebs_encrypted": all(
                                    volume.get("Encrypted", False)
                                    for volume in instance.get("BlockDeviceMappings", [])
                                ),
                                "ssm_managed": tags.get("SSMManaged") == "true",
                                "subnet_tier": tags.get("Tier", "private"),
                            },
                            health=health,
                        )
                    )
        return out

    def _load_load_balancers(self) -> list[Resource]:
        client = self._client("elbv2")
        out: list[Resource] = []
        for balancer in client.describe_load_balancers()["LoadBalancers"]:
            arn = balancer["LoadBalancerArn"]
            tags = self._tags(client.describe_tags(ResourceArns=[arn])["TagDescriptions"][0].get("Tags"))
            env = self._environment(tags)
            if env is None:
                continue
            attributes = {
                item["Key"]: item["Value"]
                for item in client.describe_load_balancer_attributes(LoadBalancerArn=arn)["Attributes"]
            }
            out.append(
                Resource(
                    id=arn.rsplit("/", 1)[-1],
                    name=balancer["LoadBalancerName"],
                    kind=ResourceKind.LOAD_BALANCER,
                    environment=env,
                    region=self.region,
                    status=ResourceStatus.AVAILABLE,
                    owner=tags.get("Owner", "unknown"),
                    monthly_cost_usd=round(_ALB_HOURLY * _MONTHLY_HOURS, 2),
                    tags=tags,
                    config={
                        "scheme": balancer.get("Scheme"),
                        "type": balancer.get("Type"),
                        "deletion_protection": attributes.get("deletion_protection.enabled") == "true",
                        "access_logs_enabled": attributes.get("access_logs.s3.enabled") == "true",
                        "drop_invalid_headers": attributes.get("routing.http.drop_invalid_header_fields.enabled")
                        == "true",
                    },
                )
            )
        return out
