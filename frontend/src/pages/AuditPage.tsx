import { useEffect, useMemo, useState } from "react";

import type { AuditPage as AuditPageType } from "../api/types";
import { Badge, EmptyState, ErrorBanner, Loading, PageHeader, Pagination } from "../components/ui";
import { useApi } from "../hooks/useApi";
import { dateTime, titleCase, toneForStatus } from "../lib/format";

const PAGE_SIZE = 25;

export function AuditPage() {
  const [action, setAction] = useState("");
  const [actorInput, setActorInput] = useState("");
  const [actor, setActor] = useState("");
  const [page, setPage] = useState(0);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setActor(actorInput.trim());
      setPage(0);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [actorInput]);

  const path = useMemo(() => {
    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(page * PAGE_SIZE),
    });
    if (action) params.set("action", action);
    if (actor) params.set("actor", actor);
    return `/audit?${params.toString()}`;
  }, [action, actor, page]);

  const { data, loading, error } = useApi<AuditPageType>(path);

  return (
    <>
      <PageHeader
        title="Audit trail"
        description="Append-only record of authentication, deployment, compliance and drift events, with the originating address and correlation id."
      />

      <div className="toolbar">
        <input
          className="input search"
          type="search"
          placeholder="Filter by actor email…"
          value={actorInput}
          onChange={(event) => setActorInput(event.target.value)}
          aria-label="Filter by actor"
        />
        <select
          className="input"
          value={action}
          onChange={(event) => {
            setAction(event.target.value);
            setPage(0);
          }}
          aria-label="Filter by action"
        >
          <option value="">All actions</option>
          <option value="auth">Authentication</option>
          <option value="deployment">Deployments</option>
          <option value="compliance">Compliance</option>
          <option value="drift">Drift</option>
        </select>
        {data ? <span className="chip">{data.total} events</span> : null}
      </div>

      {error ? <ErrorBanner message={error} /> : null}
      {loading && !data ? <Loading label="Loading audit trail" /> : null}
      {data && data.items.length === 0 ? <EmptyState title="No audit events match" /> : null}

      {data && data.items.length > 0 ? (
        <>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Actor</th>
                  <th>Action</th>
                  <th>Target</th>
                  <th>Environment</th>
                  <th>Outcome</th>
                  <th>Source IP</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((event) => (
                  <tr key={event.id}>
                    <td className="small mono">{dateTime(event.timestamp)}</td>
                    <td className="small">{event.actor_email}</td>
                    <td>
                      <span className="mono small">{event.action}</span>
                    </td>
                    <td className="small dim mono">{event.target}</td>
                    <td style={{ textTransform: "capitalize" }}>{event.environment ?? "—"}</td>
                    <td>
                      <Badge
                        tone={toneForStatus(
                          event.outcome === "success"
                            ? "success"
                            : event.outcome === "failure"
                              ? "failure"
                              : event.outcome,
                        )}
                      >
                        {titleCase(event.outcome)}
                      </Badge>
                    </td>
                    <td className="small mono muted">{event.source_ip ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} />
        </>
      ) : null}
    </>
  );
}
