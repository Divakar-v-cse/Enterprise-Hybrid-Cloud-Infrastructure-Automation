export type Role = "viewer" | "operator" | "approver" | "admin";
export type Environment = "dev" | "prod";
export type Severity = "critical" | "high" | "medium" | "low";
export type HealthStatus = "healthy" | "warning" | "critical" | "unknown";
export type PatchStatus = "compliant" | "pending" | "overdue";
export type DeploymentStatus =
  | "pending_approval"
  | "approved"
  | "in_progress"
  | "succeeded"
  | "failed"
  | "rejected"
  | "rolled_back";
export type ResourceKind =
  | "vpc"
  | "subnet"
  | "route_table"
  | "security_group"
  | "iam_role"
  | "ec2"
  | "load_balancer"
  | "target_group";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  mfa_enabled: boolean;
  last_login_at: string | null;
  permissions: string[];
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginResponse extends TokenPair {
  user: User;
}

export interface HealthSnapshot {
  score: number;
  status: HealthStatus;
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  patch_status: PatchStatus;
  agent_version: string;
  uptime_hours: number;
  last_seen: string;
}

export interface Resource {
  id: string;
  name: string;
  kind: ResourceKind;
  environment: Environment;
  region: string;
  status: string;
  owner: string;
  monthly_cost_usd: number;
  created_at: string;
  tags: Record<string, string>;
  config: Record<string, unknown>;
  health: HealthSnapshot | null;
}

export interface ResourcePage {
  items: Resource[];
  total: number;
  limit: number;
  offset: number;
}

export interface Deployment {
  id: string;
  environment: Environment;
  component: "network" | "compute" | "configuration" | "application";
  version: string;
  status: DeploymentStatus;
  requested_by: string;
  requested_by_email: string;
  approved_by: string | null;
  change_summary: string;
  risk_level: Severity;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  rollback_of: string | null;
  logs: string[];
}

export interface DeploymentPage {
  items: Deployment[];
  total: number;
  limit: number;
}

export interface ComplianceFinding {
  id: string;
  rule_id: string;
  title: string;
  category: string;
  severity: Severity;
  status: "fail" | "pass" | "waived";
  resource_id: string;
  resource_name: string;
  environment: Environment;
  description: string;
  remediation: string;
  detected_at: string;
}

export interface FindingPage {
  items: ComplianceFinding[];
  total: number;
  summary: Record<string, number>;
}

export interface ComplianceRule {
  id: string;
  title: string;
  category: string;
  severity: Severity;
  description: string;
  remediation: string;
}

export interface ScanResult {
  evaluated: number;
  passed: number;
  failed: number;
  waived: number;
  score: number;
}

export interface DriftItem {
  resource_name: string;
  kind: string;
  environment: Environment;
  drift_type: "missing" | "unexpected" | "modified" | "unmanaged_tag";
  expected: string | null;
  actual: string | null;
  severity: Severity;
}

export interface DriftReport {
  generated_at: string;
  environment: Environment;
  provider: string;
  checked_resources: number;
  drift_detected: boolean;
  items: DriftItem[];
}

export interface EnvironmentSummary {
  environment: Environment;
  resources: number;
  monthly_cost_usd: number;
  servers: number;
  healthy_servers: number;
  open_findings: number;
  critical_findings: number;
  last_deployment: string | null;
  last_deployment_status: string | null;
}

export interface DashboardSummary {
  generated_at: string;
  provider: string;
  total_resources: number;
  total_monthly_cost_usd: number;
  servers_total: number;
  servers_healthy: number;
  servers_warning: number;
  servers_critical: number;
  open_findings: number;
  critical_findings: number;
  compliance_score: number;
  pending_approvals: number;
  environments: EnvironmentSummary[];
  cost_by_kind: Record<string, number>;
  findings_by_severity: Record<string, number>;
}

export interface DeploymentMetrics {
  total: number;
  success_rate: number;
  average_duration_minutes: number;
  pending_approvals: number;
  last_deployment_at: string | null;
}

export interface ServerView {
  id: string;
  name: string;
  environment: Environment;
  operating_system: string;
  instance_type: string;
  private_ip: string | null;
  status: string;
  health_score: number | null;
  health_status: HealthStatus | null;
  cpu_percent: number | null;
  memory_percent: number | null;
  disk_percent: number | null;
  patch_status: PatchStatus | null;
  agent_version: string | null;
  uptime_hours: number | null;
  last_seen: string | null;
}

export interface ServerFleetSummary {
  total: number;
  by_os: Record<string, number>;
  by_environment: Record<string, number>;
  by_health: Record<string, number>;
  by_patch_status: Record<string, number>;
  average_health_score: number;
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  actor_id: string;
  actor_email: string;
  action: string;
  target: string;
  environment: string | null;
  outcome: string;
  source_ip: string | null;
  details: Record<string, unknown>;
}

export interface AuditPage {
  items: AuditEvent[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApiErrorPayload {
  error: {
    code: string;
    message: string;
    request_id: string;
    details: Record<string, unknown>;
  };
}
