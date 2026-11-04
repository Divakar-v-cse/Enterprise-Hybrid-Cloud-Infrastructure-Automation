import { useMemo, useState } from "react";

import type { ServerFleetSummary, ServerView } from "../api/types";
import {
  Badge,
  EmptyState,
  ErrorBanner,
  HealthBar,
  Loading,
  PageHeader,
  StatCard,
} from "../components/ui";
import { useApi } from "../hooks/useApi";
import { percent, relativeTime, titleCase, toneForHealth, toneForStatus } from "../lib/format";

export function ServersPage() {
  const [environment, setEnvironment] = useState("");
  const [os, setOs] = useState("");

  const path = useMemo(() => {
    const params = new URLSearchParams();
    if (environment) params.set("environment", environment);
    const query = params.toString();
    return `/servers${query ? `?${query}` : ""}`;
  }, [environment]);

  const servers = useApi<ServerView[]>(path);
  const summary = useApi<ServerFleetSummary>("/servers/summary");

  const visible = (servers.data ?? []).filter((server) =>
    os ? server.operating_system.toLowerCase().includes(os.toLowerCase()) : true,
  );

  return (
    <>
      <PageHeader
        title="Server fleet"
        description="Linux and Windows instances with live CPU, memory, disk and patch telemetry gathered by the Ansible baseline."
      />

      {summary.error ? <ErrorBanner message={summary.error} /> : null}
      {summary.data ? (
        <div className="kpi-grid">
          <StatCard label="Servers" value={summary.data.total} hint={Object.entries(summary.data.by_os).map(([key, value]) => `${value} ${key}`).join(" · ")} />
          <StatCard
            label="Average health"
            value={percent(summary.data.average_health_score, 1)}
            hint="Weighted by CPU, memory, disk and patching"
            tone="accent"
          />
          <StatCard
            label="Patch compliant"
            value={`${summary.data.by_patch_status.compliant ?? 0}/${summary.data.total}`}
            hint={`${summary.data.by_patch_status.overdue ?? 0} overdue · ${summary.data.by_patch_status.pending ?? 0} pending`}
            tone={(summary.data.by_patch_status.overdue ?? 0) > 0 ? "danger" : "accent"}
          />
          <StatCard
            label="Needs attention"
            value={(summary.data.by_health.critical ?? 0) + (summary.data.by_health.warning ?? 0)}
            hint="Warning and critical hosts"
            tone={(summary.data.by_health.critical ?? 0) > 0 ? "danger" : "warn"}
          />
        </div>
      ) : null}

      <div className="toolbar">
        <select
          className="input"
          value={environment}
          onChange={(event) => setEnvironment(event.target.value)}
          aria-label="Filter servers by environment"
        >
          <option value="">All environments</option>
          <option value="dev">Development</option>
          <option value="prod">Production</option>
        </select>
        <select
          className="input"
          value={os}
          onChange={(event) => setOs(event.target.value)}
          aria-label="Filter servers by operating system"
        >
          <option value="">All operating systems</option>
          <option value="Linux">Linux</option>
          <option value="Windows">Windows Server</option>
        </select>
      </div>

      {servers.error ? <ErrorBanner message={servers.error} /> : null}
      {servers.loading && !servers.data ? <Loading label="Loading fleet" /> : null}

      {servers.data && visible.length === 0 ? (
        <EmptyState title="No servers match those filters" hint="Adjust the environment or operating system filter." />
      ) : null}

      {visible.length > 0 ? (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Server</th>
                <th>Environment</th>
                <th>OS</th>
                <th>Type</th>
                <th>Health</th>
                <th>CPU</th>
                <th>Memory</th>
                <th>Disk</th>
                <th>Patch</th>
                <th>Last seen</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((server) => (
                <tr key={server.id}>
                  <td>
                    <div className="cell-strong">{server.name}</div>
                    <div className="cell-sub mono">{server.private_ip ?? server.id}</div>
                  </td>
                  <td style={{ textTransform: "capitalize" }}>{server.environment}</td>
                  <td className="small">{server.operating_system}</td>
                  <td className="mono small">{server.instance_type}</td>
                  <td>
                    {server.health_score !== null ? <HealthBar score={server.health_score} /> : <span className="muted">—</span>}
                  </td>
                  <td className="mono">{server.cpu_percent !== null ? percent(server.cpu_percent, 1) : "—"}</td>
                  <td className="mono">{server.memory_percent !== null ? percent(server.memory_percent, 1) : "—"}</td>
                  <td className="mono">{server.disk_percent !== null ? percent(server.disk_percent, 1) : "—"}</td>
                  <td>
                    {server.patch_status ? (
                      <Badge tone={toneForStatus(server.patch_status)}>{titleCase(server.patch_status)}</Badge>
                    ) : (
                      <Badge tone={toneForHealth(server.health_status)}>Unknown</Badge>
                    )}
                  </td>
                  <td className="small muted">{relativeTime(server.last_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </>
  );
}
