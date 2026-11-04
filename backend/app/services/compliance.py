"""Policy-as-code compliance engine.

Each rule is a pure predicate over a ``Resource`` (plus an optional identity
check over users). The engine is deterministic and cheap enough to run on
every startup, which is what keeps the dashboard's posture score live.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.db.store import Store
from app.schemas import (
    ComplianceFinding,
    Environment,
    FindingStatus,
    PatchStatus,
    Resource,
    ResourceKind,
    Severity,
)

_SEVERITY_WEIGHT = {
    Severity.CRITICAL: 10,
    Severity.HIGH: 5,
    Severity.MEDIUM: 2,
    Severity.LOW: 1,
}

_REQUIRED_TAGS = ("Environment", "Owner", "CostCenter", "ManagedBy")
_PRIVILEGED_PORTS = {22: "SSH", 3389: "RDP"}


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    category: str
    severity: Severity
    description: str
    remediation: str
    applies: Callable[[Resource], bool]
    evaluate: Callable[[Resource], tuple[bool, str]]


def _ingress(resource: Resource) -> list[dict]:
    value = resource.config.get("ingress", [])
    return value if isinstance(value, list) else []


def _open_to_world(rule: dict, port: int) -> bool:
    if rule.get("cidr") not in {"0.0.0.0/0", "::/0"}:
        return False
    try:
        return int(rule.get("from_port", -1)) <= port <= int(rule.get("to_port", -1))
    except (TypeError, ValueError):
        return False


def _check_open_admin_ports(resource: Resource) -> tuple[bool, str]:
    exposed = [
        f"{protocol} ({port})"
        for port, protocol in _PRIVILEGED_PORTS.items()
        for rule in _ingress(resource)
        if _open_to_world(rule, port)
    ]
    if exposed:
        return False, f"Administrative ports open to 0.0.0.0/0: {', '.join(exposed)}"
    return True, "No administrative ports exposed to the internet"


def _check_imds(resource: Resource) -> tuple[bool, str]:
    if resource.config.get("imds_v2_required") is True:
        return True, "IMDSv2 enforced"
    return False, "Instance metadata service allows IMDSv1 (token optional)"


def _check_ebs(resource: Resource) -> tuple[bool, str]:
    if resource.config.get("ebs_encrypted") is True:
        return True, "All attached EBS volumes encrypted"
    return False, "Unencrypted EBS volume attached"


def _check_iam_wildcard(resource: Resource) -> tuple[bool, str]:
    policies = resource.config.get("inline_policies", []) or []
    offenders = []
    for policy in policies:
        for statement in policy.get("statements", []) or []:
            action = statement.get("Action")
            actions = action if isinstance(action, list) else [action]
            resource_scope = statement.get("Resource")
            wildcard_resource = resource_scope == "*" or resource_scope == ["*"]
            if "*" in actions and wildcard_resource:
                offenders.append(policy.get("name", "unnamed"))
    if offenders:
        return False, f"Wildcard Action:* on Resource:* in policy {', '.join(offenders)}"
    return True, "No wildcard administrative statements"


def _check_required_tags(resource: Resource) -> tuple[bool, str]:
    missing = [tag for tag in _REQUIRED_TAGS if not resource.tags.get(tag, "").strip()]
    if missing:
        return False, f"Missing required tags: {', '.join(missing)}"
    return True, "All required tags present"


def _check_flow_logs(resource: Resource) -> tuple[bool, str]:
    if resource.config.get("flow_logs_enabled") is True:
        return True, "VPC flow logs enabled"
    return False, "VPC flow logs disabled - no network audit trail"


def _check_alb_logs(resource: Resource) -> tuple[bool, str]:
    if resource.config.get("access_logs_enabled") is True:
        return True, "ALB access logging enabled"
    return False, "ALB access logging disabled"


def _check_alb_deletion_protection(resource: Resource) -> tuple[bool, str]:
    if resource.config.get("deletion_protection") is True:
        return True, "Deletion protection enabled"
    return False, "Deletion protection disabled on a production load balancer"


def _check_alb_tls(resource: Resource) -> tuple[bool, str]:
    listeners = resource.config.get("listeners", []) or []
    plain = [
        listener
        for listener in listeners
        if listener.get("protocol") == "HTTP" and not listener.get("redirect_to")
    ]
    if plain:
        return False, "HTTP listener without HTTPS redirect"
    return True, "TLS only (HTTP redirects to HTTPS)"


def _check_patching(resource: Resource) -> tuple[bool, str]:
    health = resource.health
    if health is None:
        return True, "No patch telemetry"
    if health.patch_status is PatchStatus.COMPLIANT:
        return True, "Patch baseline current"
    label = "overdue" if health.patch_status is PatchStatus.OVERDUE else "pending"
    return False, f"Security patches {label} for this instance"


def _check_no_public_ip(resource: Resource) -> tuple[bool, str]:
    if resource.config.get("subnet_tier") == "private" and resource.config.get("public_ip"):
        return False, "Private-subnet instance has a public IP address"
    return True, "No public IP on private-subnet instance"


def _check_ssm(resource: Resource) -> tuple[bool, str]:
    if resource.config.get("ssm_managed") is True:
        return True, "Managed through SSM Session Manager"
    return False, "Instance is not SSM managed - no shell audit trail"


def _check_boundary(resource: Resource) -> tuple[bool, str]:
    if resource.config.get("permissions_boundary"):
        return True, "IAM permissions boundary attached"
    return False, "IAM role has no permissions boundary"


def _check_backup(resource: Resource) -> tuple[bool, str]:
    if resource.config.get("backup_enabled") is True:
        return True, "Backup plan applied"
    return False, "No backup plan attached"


RULES: tuple[Rule, ...] = (
    Rule(
        id="HC-SG-001",
        title="No administrative ports exposed to the internet",
        category="Network",
        severity=Severity.CRITICAL,
        description="Security groups must not allow 0.0.0.0/0 ingress on SSH (22) or RDP (3389).",
        remediation="Restrict ingress to the bastion security group or use SSM Session Manager.",
        applies=lambda r: r.kind == ResourceKind.SECURITY_GROUP,
        evaluate=_check_open_admin_ports,
    ),
    Rule(
        id="HC-EC2-001",
        title="IMDSv2 enforced on all instances",
        category="Compute",
        severity=Severity.HIGH,
        description="Instances must require session tokens for the metadata service.",
        remediation="Set metadata_options.http_tokens = \"required\" in the ec2 module.",
        applies=lambda r: r.kind == ResourceKind.EC2,
        evaluate=_check_imds,
    ),
    Rule(
        id="HC-EC2-002",
        title="EBS volumes encrypted at rest",
        category="Data Protection",
        severity=Severity.HIGH,
        description="All EBS volumes attached to an instance must be encrypted.",
        remediation="Enable the account-level EBS encryption default and re-create volumes.",
        applies=lambda r: r.kind == ResourceKind.EC2,
        evaluate=_check_ebs,
    ),
    Rule(
        id="HC-EC2-003",
        title="Security patches are current",
        category="Patch Management",
        severity=Severity.HIGH,
        description="Instances must report a compliant patch baseline from the Ansible patch playbook.",
        remediation="Run `ansible-playbook playbooks/patch.yml -e target_env=<env>`.",
        applies=lambda r: r.kind == ResourceKind.EC2,
        evaluate=_check_patching,
    ),
    Rule(
        id="HC-EC2-004",
        title="Private instances have no public IP",
        category="Network",
        severity=Severity.MEDIUM,
        description="Compute in a private subnet must egress through NAT, never a public address.",
        remediation="Set map_public_ip_on_launch = false and remove the public IP association.",
        applies=lambda r: r.kind == ResourceKind.EC2,
        evaluate=_check_no_public_ip,
    ),
    Rule(
        id="HC-EC2-005",
        title="Instances are SSM managed",
        category="Operations",
        severity=Severity.MEDIUM,
        description="Shell access must be brokered by SSM Session Manager and logged to CloudWatch.",
        remediation="Attach the SSM instance profile and ensure the agent is running.",
        applies=lambda r: r.kind == ResourceKind.EC2,
        evaluate=_check_ssm,
    ),
    Rule(
        id="HC-EC2-006",
        title="Backup plan attached",
        category="Resilience",
        severity=Severity.MEDIUM,
        description="Every instance must be covered by the AWS Backup plan.",
        remediation="Add the instance to the `hccp-backup-plan` selection.",
        applies=lambda r: r.kind == ResourceKind.EC2,
        evaluate=_check_backup,
    ),
    Rule(
        id="HC-IAM-001",
        title="No wildcard IAM statements",
        category="Identity",
        severity=Severity.CRITICAL,
        description="Inline policies must not grant Action:* on Resource:*.",
        remediation="Scope the policy actions and resources to the minimum required.",
        applies=lambda r: r.kind == ResourceKind.IAM_ROLE,
        evaluate=_check_iam_wildcard,
    ),
    Rule(
        id="HC-IAM-002",
        title="IAM roles carry a permissions boundary",
        category="Identity",
        severity=Severity.MEDIUM,
        description="Every role must be constrained by the environment permissions boundary.",
        remediation="Set permissions_boundary in the iam module.",
        applies=lambda r: r.kind == ResourceKind.IAM_ROLE,
        evaluate=_check_boundary,
    ),
    Rule(
        id="HC-TAG-001",
        title="Mandatory cost and ownership tags present",
        category="Governance",
        severity=Severity.MEDIUM,
        description="Environment, Owner, CostCenter and ManagedBy tags are mandatory.",
        remediation="Populate the tags map in the environment module call.",
        applies=lambda r: True,
        evaluate=_check_required_tags,
    ),
    Rule(
        id="HC-VPC-001",
        title="VPC flow logs enabled",
        category="Network",
        severity=Severity.HIGH,
        description="Flow logs provide the network audit trail required for incident response.",
        remediation="Set enable_flow_logs = true in the vpc module.",
        applies=lambda r: r.kind == ResourceKind.VPC,
        evaluate=_check_flow_logs,
    ),
    Rule(
        id="HC-ALB-001",
        title="Load balancer access logs enabled",
        category="Logging",
        severity=Severity.MEDIUM,
        description="ALB access logs must be delivered to the central logging bucket.",
        remediation="Set access_logs_enabled = true in the alb module.",
        applies=lambda r: r.kind == ResourceKind.LOAD_BALANCER,
        evaluate=_check_alb_logs,
    ),
    Rule(
        id="HC-ALB-002",
        title="Production load balancers are deletion protected",
        category="Resilience",
        severity=Severity.HIGH,
        description="Deletion protection prevents an accidental destroy of production ingress.",
        remediation="Set enable_deletion_protection = true in prod.",
        applies=lambda r: r.kind == ResourceKind.LOAD_BALANCER and r.environment == Environment.PROD,
        evaluate=_check_alb_deletion_protection,
    ),
    Rule(
        id="HC-ALB-003",
        title="TLS terminated on every listener",
        category="Data Protection",
        severity=Severity.HIGH,
        description="HTTP listeners must redirect to HTTPS; plaintext termination is not allowed.",
        remediation="Add a redirect action from :80 to :443 in the alb module.",
        applies=lambda r: r.kind == ResourceKind.LOAD_BALANCER,
        evaluate=_check_alb_tls,
    ),
)


@dataclass
class ScanResult:
    findings: list[ComplianceFinding]
    evaluated: int
    passed: int
    failed: int
    waived: int

    @property
    def score(self) -> float:
        """Severity-weighted pass rate (waivers excluded from the denominator)."""
        total_weight = 0
        passed_weight = 0
        for finding in self.findings:
            weight = _SEVERITY_WEIGHT[finding.severity]
            if finding.status is FindingStatus.WAIVED:
                continue
            total_weight += weight
            if finding.status is FindingStatus.PASS:
                passed_weight += weight
        if total_weight == 0:
            return 100.0
        return round(100.0 * passed_weight / total_weight, 1)


def _identity_findings(store: Store) -> list[ComplianceFinding]:
    """Identity controls are evaluated over users, not cloud resources."""
    findings: list[ComplianceFinding] = []
    for user in store.list_users():
        if not user.is_active or user.mfa_enabled:
            continue
        findings.append(
            ComplianceFinding(
                id=f"HC-ID-001-{user.id}",
                rule_id="HC-ID-001",
                title="Privileged accounts require MFA",
                category="Identity",
                severity=Severity.CRITICAL,
                status=FindingStatus.FAIL,
                resource_id=user.id,
                resource_name=user.email,
                environment=Environment.PROD,
                description=f"{user.email} is active without MFA enabled.",
                remediation="Enrol the account in the identity provider MFA policy or deactivate it.",
            )
        )
    return findings


def scan(store: Store, environment: Environment | None = None) -> ScanResult:
    """Evaluate every rule against the current inventory."""
    resources = store.list_resources()
    if environment is not None:
        target = Environment(environment)
        resources = [r for r in resources if r.environment == target]

    findings: list[ComplianceFinding] = []
    evaluated = 0
    for resource in resources:
        for rule in RULES:
            if not rule.applies(resource):
                continue
            evaluated += 1
            passed, detail = rule.evaluate(resource)
            findings.append(
                ComplianceFinding(
                    id=f"{rule.id}-{resource.id}",
                    rule_id=rule.id,
                    title=rule.title,
                    category=rule.category,
                    severity=rule.severity,
                    status=FindingStatus.PASS if passed else FindingStatus.FAIL,
                    resource_id=resource.id,
                    resource_name=resource.name,
                    environment=resource.environment,
                    description=detail if not passed else rule.description,
                    remediation=rule.remediation,
                )
            )

    if environment is None:
        findings.extend(_identity_findings(store))

    return ScanResult(
        findings=findings,
        evaluated=evaluated,
        passed=sum(1 for f in findings if f.status is FindingStatus.PASS),
        failed=sum(1 for f in findings if f.status is FindingStatus.FAIL),
        waived=sum(1 for f in findings if f.status is FindingStatus.WAIVED),
    )


def rule_catalog() -> list[dict[str, str]]:
    return [
        {
            "id": rule.id,
            "title": rule.title,
            "category": rule.category,
            "severity": rule.severity.value,
            "description": rule.description,
            "remediation": rule.remediation,
        }
        for rule in RULES
    ]
