import { Link } from "react-router-dom";

import type {
  DashboardSummary,
  DeploymentMetrics,
  DeploymentPage,
  DriftReport,
  FindingPage,
} from "../api/types";
import {
  Badge,
  BarChart,
  DonutChart,
  ErrorBanner,
  Legend,
  Loading,
  PageHeader,
  ScoreRing,
  StatCard,
} from "../components/ui";
import { useApi } from "../hooks/useApi";
import { currency, percent, relativeTime, titleCase, toneForSeverity, toneForStatus } from "../lib/format";

export function DashboardPage() {
  const summary = useApi<DashboardSummary>("/dashboard/summary");
  const metrics = useApi<DeploymentMetrics>("/dashboard/deployment-metrics");
  const deployments = useApi<DeploymentPage>("/deployments?limit=5");
  const findings = useApi<FindingPage>("/compliance/findings?status=fail&limit=5");
  const drift = useApi<DriftReport[]>("/drift");

  if (summary.loading && !summary.data) return <Loading label="Loading platform posture" />;
  if (summary.error) return <ErrorBanner message={summary.error} />;
  if (!summary.data) return null;

  const data = summary.data;
  const healthSegments = [
    { label: "Healthy", value: data.servers_healthy, color: "#34d399" },
    { label: "Warning", value: data.servers_warning, color: "#fbbf24" },
    { label: "Critical", value: data.servers_critical, color: "#f87171" },
  ];
  const costItems = Object.entries(data.cost_by_kind)
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 6);

  const drifted = (drift.data ?? []).reduce((total, report) => total + report.items.length, 0);
  const healthyShare =
    data.servers_total > 0 ? Math.round((data.servers_healthy / data.servers_total) * 100) : 0;

  return (
    <>
      <PageHeader
        title="Platform overview"
        description="Live inventory, fleet health, compliance posture and delivery activity across the development and production estates."
        actions={
          <span className="chip">
            <span className="status-dot" aria-hidden="true" />
            Provider: {data.provider}
          </span>
        }
      />

      {drifted > 0 ? (
        <div className="notice">
          <strong>{drifted} drift item(s) detected.</strong> Live infrastructure no longer matches the
          committed desired-state contract. <Link to="/drift">Review drift</Link>
        </div>
      ) : null}

      <div className="kpi-grid">
        <StatCard
          label="Managed resources"
          value={data.total_resources}
          hint={`${data.environments.length} environments · ap-south-1`}
        />
        <StatCard
          label="Monthly run rate"
          value={currency(data.total_monthly_cost_usd)}
          hint="On-demand estimate, excludes data transfer"
          tone="accent"
        />
        <StatCard
          label="Fleet health"
          value={`${healthyShare}%`}
          hint={`${data.servers_healthy}/${data.servers_total} servers healthy`}
          tone={healthyShare >= 85 ? "accent" : healthyShare >= 60 ? "warn" : "danger"}
        />
        <StatCard
          label="Compliance score"
          value={percent(data.compliance_score, 1)}
          hint={`${data.open_findings} open findings · ${data.critical_findings} critical`}
          tone={data.critical_findings > 0 ? "danger" : "accent"}
        />
        <StatCard
          label="Pending approvals"
          value={data.pending_approvals}
          hint={metrics.data ? `${metrics.data.success_rate}% delivery success` : "Production gates"}
          tone={data.pending_approvals > 0 ? "warn" : "info"}
        />
      </div>

      <div className="grid grid--sidebar" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Server health distribution</div>
              <div className="card-subtitle">Derived from CPU, memory, disk and patch telemetry</div>
            </div>
            <Link to="/servers" className="btn-link">View fleet</Link>
          </div>
          <div style={{ display: "flex", gap: 28, alignItems: "center", flexWrap: "wrap" }}>
            <DonutChart
              segments={healthSegments}
              centerValue={data.servers_total}
              centerLabel="servers"
              size={176}
            />
            <div style={{ flex: 1, minWidth: 180 }}>
              <Legend segments={healthSegments} />
              <div className="divider" />
              <div className="small muted">
                {data.servers_critical > 0
                  ? `${data.servers_critical} server(s) need attention before the next deployment window.`
                  : "No critical servers. Patch compliance is the leading risk signal."}
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Cost by resource type</div>
              <div className="card-subtitle">Monthly estimate, USD</div>
            </div>
          </div>
          <BarChart items={costItems} formatValue={(value) => currency(value)} />
        </div>
      </div>

      <div className="grid grid--3" style={{ marginBottom: 16 }}>
        {data.environments.map((environment) => (
          <div className="card" key={environment.environment}>
            <div className="card-header">
              <div>
                <div className="card-title" style={{ textTransform: "capitalize" }}>
                  {environment.environment}
                </div>
                <div className="card-subtitle">
                  {environment.resources} resources · {environment.servers} servers
                </div>
              </div>
              <Badge tone={environment.environment === "prod" ? "info" : "neutral"}>
                {environment.environment === "prod" ? "guarded" : "auto-deploy"}
              </Badge>
            </div>
            <div className="stack small">
              <div className="row row--between">
                <span className="muted">Monthly cost</span>
                <span className="mono">{currency(environment.monthly_cost_usd)}</span>
              </div>
              <div className="row row--between">
                <span className="muted">Healthy servers</span>
                <span className="mono">
                  {environment.healthy_servers}/{environment.servers}
                </span>
              </div>
              <div className="row row--between">
                <span className="muted">Open findings</span>
                <span className="mono">
                  {environment.open_findings}
                  {environment.critical_findings > 0 ? (
                    <Badge tone="danger">{environment.critical_findings} critical</Badge>
                  ) : null}
                </span>
              </div>
              <div className="divider" style={{ margin: "8px 0" }} />
              <div className="row row--between">
                <span className="muted">Last deployment</span>
                <span>
                  {environment.last_deployment_status ? (
                    <Badge tone={toneForStatus(environment.last_deployment_status)}>
                      {titleCase(environment.last_deployment_status)}
                    </Badge>
                  ) : (
                    "—"
                  )}
                </span>
              </div>
              <div className="small muted">{relativeTime(environment.last_deployment)}</div>
            </div>
          </div>
        ))}

        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Compliance posture</div>
              <div className="card-subtitle">Severity-weighted pass rate</div>
            </div>
            <Link to="/compliance" className="btn-link">Details</Link>
          </div>
          <div style={{ display: "grid", placeItems: "center" }}>
            <ScoreRing score={data.compliance_score} label="score" />
          </div>
          <div className="stack small" style={{ marginTop: 12 }}>
            {Object.entries(data.findings_by_severity).map(([severity, count]) => (
              <div className="row row--between" key={severity}>
                <Badge tone={toneForSeverity(severity)}>{severity}</Badge>
                <span className="mono">{count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid--2">
        <div className="card">
          <div className="card-header">
            <div className="card-title">Recent deployments</div>
            <Link to="/deployments" className="btn-link">Open pipeline</Link>
          </div>
          {deployments.data?.items.length ? (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Version</th>
                    <th>Environment</th>
                    <th>Status</th>
                    <th>When</th>
                  </tr>
                </thead>
                <tbody>
                  {deployments.data.items.map((deployment) => (
                    <tr key={deployment.id}>
                      <td>
                        <div className="cell-strong mono">{deployment.version}</div>
                        <div className="cell-sub">{titleCase(deployment.component)}</div>
                      </td>
                      <td style={{ textTransform: "capitalize" }}>{deployment.environment}</td>
                      <td>
                        <Badge tone={toneForStatus(deployment.status)}>
                          {titleCase(deployment.status)}
                        </Badge>
                      </td>
                      <td className="small muted">{relativeTime(deployment.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted small">No deployments recorded yet.</p>
          )}
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">Top failing controls</div>
            <Link to="/compliance" className="btn-link">All findings</Link>
          </div>
          {findings.data?.items.length ? (
            <div className="stack">
              {findings.data.items.map((finding) => (
                <div key={finding.id} className="row row--between" style={{ alignItems: "flex-start" }}>
                  <div>
                    <div style={{ fontSize: 12.5, fontWeight: 600 }}>{finding.title}</div>
                    <div className="small muted">
                      {finding.resource_name} · {finding.rule_id}
                    </div>
                  </div>
                  <Badge tone={toneForSeverity(finding.severity)}>{finding.severity}</Badge>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted small">No failing controls. Nice.</p>
          )}
        </div>
      </div>
    </>
  );
}
