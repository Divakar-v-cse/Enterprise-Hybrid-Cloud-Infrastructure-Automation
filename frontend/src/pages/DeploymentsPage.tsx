import { useState } from "react";

import { apiRequest } from "../api/client";
import type { Deployment, DeploymentPage } from "../api/types";
import {
  Badge,
  EmptyState,
  ErrorBanner,
  Loading,
  Modal,
  PageHeader,
} from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useApi, useMutation } from "../hooks/useApi";
import { dateTime, relativeTime, titleCase, toneForSeverity, toneForStatus } from "../lib/format";

const COMPONENTS = ["network", "compute", "configuration", "application"] as const;
const RISKS = ["low", "medium", "high", "critical"] as const;

interface CreateForm {
  environment: "dev" | "prod";
  component: (typeof COMPONENTS)[number];
  version: string;
  change_summary: string;
  risk_level: (typeof RISKS)[number];
}

const EMPTY_FORM: CreateForm = {
  environment: "dev",
  component: "application",
  version: "",
  change_summary: "",
  risk_level: "low",
};

export function DeploymentsPage() {
  const { can } = useAuth();
  const [environment, setEnvironment] = useState("");
  const path = environment ? `/deployments?environment=${environment}&limit=50` : "/deployments?limit=50";
  const { data, loading, error, reload } = useApi<DeploymentPage>(path);

  const [selected, setSelected] = useState<Deployment | null>(null);
  const [reason, setReason] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<CreateForm>(EMPTY_FORM);
  const mutation = useMutation();

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    const created = await mutation.run(() =>
      apiRequest<Deployment>("/deployments", { method: "POST", body: form }),
    );
    if (created) {
      setCreateOpen(false);
      setForm(EMPTY_FORM);
      reload();
      setSelected(created);
    }
  }

  async function runAction(action: "approve" | "reject" | "rollback") {
    if (!selected) return;
    const updated = await mutation.run(() =>
      apiRequest<Deployment>(`/deployments/${selected.id}/${action}`, {
        method: "POST",
        body: { reason },
      }),
    );
    if (updated) {
      setSelected(updated);
      setReason("");
      reload();
    }
  }

  const canApprove = selected?.status === "pending_approval" && can("deployment:approve");
  const canRollback = selected?.status === "succeeded" && can("deployment:rollback");

  return (
    <>
      <PageHeader
        title="Deployment pipeline"
        description="Every change is recorded with its requester, approver and verification output. Production rollouts require a second pair of eyes."
        actions={
          can("deployment:create") ? (
            <button type="button" className="btn btn-primary" onClick={() => setCreateOpen(true)}>
              New deployment
            </button>
          ) : null
        }
      />

      <div className="toolbar">
        <select
          className="input"
          value={environment}
          onChange={(event) => setEnvironment(event.target.value)}
          aria-label="Filter deployments by environment"
        >
          <option value="">All environments</option>
          <option value="dev">Development</option>
          <option value="prod">Production</option>
        </select>
        {data ? <span className="chip">{data.total} deployments</span> : null}
        <span className="chip">Prod gate: approver role</span>
      </div>

      {error ? <ErrorBanner message={error} /> : null}
      {loading && !data ? <Loading label="Loading deployments" /> : null}
      {mutation.error ? <ErrorBanner message={mutation.error} onDismiss={mutation.clearError} /> : null}

      {data && data.items.length === 0 ? (
        <EmptyState title="No deployments yet" hint="Trigger the pipeline from Terraform, Ansible or the button above." />
      ) : null}

      {data && data.items.length > 0 ? (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Version</th>
                <th>Component</th>
                <th>Environment</th>
                <th>Risk</th>
                <th>Status</th>
                <th>Requested by</th>
                <th>When</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((deployment) => (
                <tr
                  key={deployment.id}
                  className="row-clickable"
                  onClick={() => {
                    setSelected(deployment);
                    setReason("");
                  }}
                >
                  <td>
                    <div className="cell-strong mono">{deployment.version}</div>
                    <div className="cell-sub">{deployment.id}</div>
                  </td>
                  <td>{titleCase(deployment.component)}</td>
                  <td style={{ textTransform: "capitalize" }}>{deployment.environment}</td>
                  <td>
                    <Badge tone={toneForSeverity(deployment.risk_level)}>{deployment.risk_level}</Badge>
                  </td>
                  <td>
                    <Badge tone={toneForStatus(deployment.status)}>{titleCase(deployment.status)}</Badge>
                  </td>
                  <td className="small dim">{deployment.requested_by_email}</td>
                  <td className="small muted">{relativeTime(deployment.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <Modal
        open={Boolean(selected)}
        title={selected ? `${selected.version} → ${selected.environment}` : "Deployment"}
        subtitle={selected ? `${titleCase(selected.component)} · ${selected.id}` : undefined}
        onClose={() => setSelected(null)}
        wide
        footer={
          selected ? (
            <>
              {canApprove ? (
                <>
                  <button
                    type="button"
                    className="btn btn-danger"
                    onClick={() => runAction("reject")}
                    disabled={mutation.busy}
                  >
                    Reject
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => runAction("approve")}
                    disabled={mutation.busy}
                  >
                    {mutation.busy ? "Approving…" : "Approve and run"}
                  </button>
                </>
              ) : null}
              {canRollback ? (
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={() => runAction("rollback")}
                  disabled={mutation.busy}
                >
                  Roll back
                </button>
              ) : null}
              <button type="button" className="btn btn-ghost" onClick={() => setSelected(null)}>
                Close
              </button>
            </>
          ) : null
        }
      >
        {selected ? (
          <div className="stack">
            <dl className="detail-list">
              <dt>Status</dt>
              <dd>
                <Badge tone={toneForStatus(selected.status)}>{titleCase(selected.status)}</Badge>
              </dd>
              <dt>Requested by</dt>
              <dd>{selected.requested_by_email}</dd>
              <dt>Approved by</dt>
              <dd>{selected.approved_by ?? "—"}</dd>
              <dt>Requested</dt>
              <dd>{dateTime(selected.created_at)}</dd>
              <dt>Started</dt>
              <dd>{dateTime(selected.started_at)}</dd>
              <dt>Completed</dt>
              <dd>{dateTime(selected.completed_at)}</dd>
              <dt>Rollback of</dt>
              <dd className="mono">{selected.rollback_of ?? "—"}</dd>
              <dt>Summary</dt>
              <dd>{selected.change_summary}</dd>
            </dl>

            {canApprove || canRollback ? (
              <div className="field">
                <label htmlFor="reason">Decision note {canRollback ? "(rollback reason)" : ""}</label>
                <input
                  id="reason"
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  placeholder="Change request id, incident reference or justification"
                />
              </div>
            ) : null}

            <strong style={{ fontSize: 12.5 }}>Pipeline output</strong>
            <pre className="code-block">{selected.logs.length ? selected.logs.join("\n") : "No output yet."}</pre>
          </div>
        ) : null}
      </Modal>

      <Modal
        open={createOpen}
        title="Request a deployment"
        subtitle="Production requests pause at the approval gate; development runs immediately."
        onClose={() => setCreateOpen(false)}
        footer={
          <>
            <button type="button" className="btn btn-ghost" onClick={() => setCreateOpen(false)}>
              Cancel
            </button>
            <button type="submit" form="deployment-form" className="btn btn-primary" disabled={mutation.busy}>
              {mutation.busy ? "Submitting…" : "Submit request"}
            </button>
          </>
        }
      >
        <form id="deployment-form" className="form-grid" onSubmit={handleCreate}>
          <div className="field">
            <label htmlFor="dep-env">Environment</label>
            <select
              id="dep-env"
              value={form.environment}
              onChange={(event) =>
                setForm({ ...form, environment: event.target.value as CreateForm["environment"] })
              }
            >
              <option value="dev">Development</option>
              <option value="prod">Production</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="dep-component">Component</label>
            <select
              id="dep-component"
              value={form.component}
              onChange={(event) =>
                setForm({ ...form, component: event.target.value as CreateForm["component"] })
              }
            >
              {COMPONENTS.map((component) => (
                <option key={component} value={component}>
                  {titleCase(component)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="dep-version">Version or commit</label>
            <input
              id="dep-version"
              value={form.version}
              onChange={(event) => setForm({ ...form, version: event.target.value })}
              placeholder="v2.15.0 or terraform-4b81c0d"
              required
              minLength={3}
              pattern="[A-Za-z0-9._/-]+"
            />
          </div>
          <div className="field">
            <label htmlFor="dep-risk">Risk</label>
            <select
              id="dep-risk"
              value={form.risk_level}
              onChange={(event) =>
                setForm({ ...form, risk_level: event.target.value as CreateForm["risk_level"] })
              }
            >
              {RISKS.map((risk) => (
                <option key={risk} value={risk}>
                  {titleCase(risk)}
                </option>
              ))}
            </select>
          </div>
          <div className="field full">
            <label htmlFor="dep-summary">Change summary</label>
            <textarea
              id="dep-summary"
              rows={3}
              value={form.change_summary}
              onChange={(event) => setForm({ ...form, change_summary: event.target.value })}
              placeholder="What is changing, why, and what is the rollback plan?"
              required
              minLength={10}
              maxLength={500}
            />
          </div>
        </form>
      </Modal>
    </>
  );
}
