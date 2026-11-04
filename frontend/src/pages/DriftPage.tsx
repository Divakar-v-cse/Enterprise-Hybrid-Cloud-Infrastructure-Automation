import { apiRequest } from "../api/client";
import type { DriftReport } from "../api/types";
import { Badge, EmptyState, ErrorBanner, Loading, PageHeader, StatCard } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useApi, useMutation } from "../hooks/useApi";
import { dateTime, titleCase, toneForSeverity } from "../lib/format";

export function DriftPage() {
  const { can } = useAuth();
  const reports = useApi<DriftReport[]>("/drift");
  const mutation = useMutation();

  async function runDetection() {
    const result = await mutation.run(() =>
      apiRequest<DriftReport[]>("/drift/run", { method: "POST" }),
    );
    if (result) reports.reload();
  }

  const totalItems = (reports.data ?? []).reduce((sum, report) => sum + report.items.length, 0);

  return (
    <>
      <PageHeader
        title="Configuration drift"
        description="The committed desired-state contract compared with what the provider actually reports. Terraform apply proves intent; this proves reality."
        actions={
          can("drift:run") ? (
            <button type="button" className="btn btn-primary" onClick={runDetection} disabled={mutation.busy}>
              {mutation.busy ? "Detecting…" : "Run detection"}
            </button>
          ) : null
        }
      />

      {mutation.error ? <ErrorBanner message={mutation.error} onDismiss={mutation.clearError} /> : null}
      {reports.error ? <ErrorBanner message={reports.error} /> : null}
      {reports.loading && !reports.data ? <Loading label="Comparing desired state" /> : null}

      {reports.data ? (
        <>
          <div className="kpi-grid">
            <StatCard
              label="Drift items"
              value={totalItems}
              hint="Any non-zero total should block a production apply"
              tone={totalItems > 0 ? "danger" : "accent"}
            />
            {reports.data.map((report) => (
              <StatCard
                key={report.environment}
                label={`${titleCase(report.environment)} resources checked`}
                value={report.checked_resources}
                hint={`${report.items.length} drift item(s)`}
                tone={report.items.length > 0 ? "warn" : "accent"}
              />
            ))}
          </div>

          <div className="stack" style={{ gap: 18 }}>
            {reports.data.map((report) => (
              <div className="card" key={`${report.environment}-detail`}>
                <div className="card-header">
                  <div>
                    <div className="card-title" style={{ textTransform: "capitalize" }}>
                      {report.environment} environment
                    </div>
                    <div className="card-subtitle">
                      Generated {dateTime(report.generated_at)} · contract provider {report.provider}
                    </div>
                  </div>
                  <Badge tone={report.drift_detected ? "danger" : "success"}>
                    {report.drift_detected ? "Drift detected" : "In sync"}
                  </Badge>
                </div>

                {report.items.length === 0 ? (
                  <EmptyState title="No drift" hint="Live state matches the committed contract." />
                ) : (
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Resource</th>
                          <th>Type</th>
                          <th>Change</th>
                          <th>Expected</th>
                          <th>Actual</th>
                          <th>Severity</th>
                        </tr>
                      </thead>
                      <tbody>
                        {report.items.map((item, index) => (
                          <tr key={`${item.resource_name}-${item.drift_type}-${index}`}>
                            <td className="cell-strong mono">{item.resource_name}</td>
                            <td>{titleCase(item.kind)}</td>
                            <td>{titleCase(item.drift_type)}</td>
                            <td className="small mono">{item.expected ?? "—"}</td>
                            <td className="small mono">{item.actual ?? "—"}</td>
                            <td>
                              <Badge tone={toneForSeverity(item.severity)}>{item.severity}</Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      ) : null}
    </>
  );
}
