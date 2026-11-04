import { useMemo, useState } from "react";

import { apiRequest } from "../api/client";
import type { ComplianceFinding, DashboardSummary, FindingPage, ScanResult } from "../api/types";
import {
  Badge,
  EmptyState,
  ErrorBanner,
  Loading,
  PageHeader,
  ScoreRing,
  StatCard,
} from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useApi, useMutation } from "../hooks/useApi";
import { percent, relativeTime, titleCase, toneForSeverity, toneForStatus } from "../lib/format";

export function CompliancePage() {
  const { can } = useAuth();
  const [severity, setSeverity] = useState("");
  const [environment, setEnvironment] = useState("");
  const [showAll, setShowAll] = useState(false);

  const path = useMemo(() => {
    const params = new URLSearchParams({ limit: "200" });
    if (severity) params.set("severity", severity);
    if (environment) params.set("environment", environment);
    if (!showAll) params.set("status", "fail");
    return `/compliance/findings?${params.toString()}`;
  }, [severity, environment, showAll]);

  const findings = useApi<FindingPage>(path);
  const summary = useApi<DashboardSummary>("/dashboard/summary");
  const mutation = useMutation();
  const [lastScan, setLastScan] = useState<ScanResult | null>(null);

  async function runScan() {
    const result = await mutation.run(() =>
      apiRequest<ScanResult>("/compliance/scan", { method: "POST" }),
    );
    if (result) {
      setLastScan(result);
      findings.reload();
      summary.reload();
    }
  }

  async function waive(finding: ComplianceFinding) {
    const updated = await mutation.run(() =>
      apiRequest<ComplianceFinding>(`/compliance/findings/${finding.id}/waive`, { method: "POST" }),
    );
    if (updated) {
      findings.reload();
      summary.reload();
    }
  }

  const counts = findings.data?.summary ?? { fail: 0, pass: 0, waived: 0 };
  const score = summary.data?.compliance_score ?? 0;

  return (
    <>
      <PageHeader
        title="Compliance posture"
        description="Policy-as-code controls evaluated against live inventory: network exposure, identity scope, encryption, patching and governance tags."
        actions={
          can("compliance:scan") ? (
            <button type="button" className="btn btn-primary" onClick={runScan} disabled={mutation.busy}>
              {mutation.busy ? "Scanning…" : "Run scan"}
            </button>
          ) : null
        }
      />

      {mutation.error ? <ErrorBanner message={mutation.error} onDismiss={mutation.clearError} /> : null}

      <div className="grid grid--sidebar" style={{ marginBottom: 16 }}>
        <div className="kpi-grid" style={{ marginBottom: 0 }}>
          <StatCard
            label="Compliance score"
            value={percent(score, 1)}
            hint="Severity weighted, waivers excluded"
            tone={score >= 90 ? "accent" : score >= 75 ? "warn" : "danger"}
          />
          <StatCard label="Failing controls" value={counts.fail} hint="Require remediation or a waiver" tone={counts.fail > 0 ? "danger" : "accent"} />
          <StatCard label="Passing controls" value={counts.pass} hint="Evaluated against live state" tone="accent" />
          <StatCard
            label="Waived"
            value={counts.waived}
            hint={lastScan ? `Last scan: ${lastScan.evaluated} checks` : "Documented exceptions"}
          />
        </div>

        <div className="card" style={{ display: "grid", placeItems: "center" }}>
          <ScoreRing score={score} label="current score" />
          <div className="small muted" style={{ textAlign: "center", marginTop: 10 }}>
            {summary.data
              ? `${summary.data.open_findings} open · ${summary.data.critical_findings} critical`
              : "Loading posture…"}
          </div>
        </div>
      </div>

      <div className="toolbar">
        <div className="segmented" role="group" aria-label="Finding status filter">
          <button type="button" className={!showAll ? "active" : ""} onClick={() => setShowAll(false)}>
            Failing
          </button>
          <button type="button" className={showAll ? "active" : ""} onClick={() => setShowAll(true)}>
            All controls
          </button>
        </div>
        <select
          className="input"
          value={severity}
          onChange={(event) => setSeverity(event.target.value)}
          aria-label="Filter by severity"
        >
          <option value="">All severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <select
          className="input"
          value={environment}
          onChange={(event) => setEnvironment(event.target.value)}
          aria-label="Filter by environment"
        >
          <option value="">All environments</option>
          <option value="dev">Development</option>
          <option value="prod">Production</option>
        </select>
        {findings.data ? <span className="chip">{findings.data.total} controls</span> : null}
      </div>

      {findings.error ? <ErrorBanner message={findings.error} /> : null}
      {findings.loading && !findings.data ? <Loading label="Evaluating controls" /> : null}
      {findings.data && findings.data.items.length === 0 ? (
        <EmptyState title="No findings for this filter" hint="The estate is compliant for the selected scope." />
      ) : null}

      {findings.data && findings.data.items.length > 0 ? (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Control</th>
                <th>Resource</th>
                <th>Environment</th>
                <th>Severity</th>
                <th>Status</th>
                <th>Detected</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {findings.data.items.map((finding) => (
                <tr key={finding.id}>
                  <td style={{ maxWidth: 340 }}>
                    <div className="cell-strong">{finding.title}</div>
                    <div className="cell-sub">
                      {finding.rule_id} · {finding.category}
                    </div>
                    <div className="small muted" style={{ marginTop: 4 }}>{finding.description}</div>
                  </td>
                  <td>
                    <div className="mono small">{finding.resource_name}</div>
                    <div className="cell-sub">{finding.remediation}</div>
                  </td>
                  <td style={{ textTransform: "capitalize" }}>{finding.environment}</td>
                  <td>
                    <Badge tone={toneForSeverity(finding.severity)}>{finding.severity}</Badge>
                  </td>
                  <td>
                    <Badge tone={toneForStatus(finding.status === "fail" ? "failed" : finding.status === "pass" ? "succeeded" : "pending")}>
                      {titleCase(finding.status)}
                    </Badge>
                  </td>
                  <td className="small muted">{relativeTime(finding.detected_at)}</td>
                  <td>
                    {finding.status === "fail" && can("compliance:scan") ? (
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={() => waive(finding)}
                        disabled={mutation.busy}
                      >
                        Waive
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </>
  );
}
