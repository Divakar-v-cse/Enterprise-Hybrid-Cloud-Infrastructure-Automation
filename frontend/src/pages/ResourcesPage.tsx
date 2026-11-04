import { useEffect, useMemo, useState } from "react";

import type { Resource, ResourcePage } from "../api/types";
import {
  Badge,
  EmptyState,
  ErrorBanner,
  Loading,
  Modal,
  PageHeader,
  Pagination,
} from "../components/ui";
import { useApi } from "../hooks/useApi";
import { currencyPrecise, dateTime, titleCase, toneForStatus } from "../lib/format";

const PAGE_SIZE = 20;
const KINDS = [
  "vpc",
  "subnet",
  "route_table",
  "security_group",
  "iam_role",
  "ec2",
  "load_balancer",
  "target_group",
];

export function ResourcesPage() {
  const [environment, setEnvironment] = useState("");
  const [kind, setKind] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Resource | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(0);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const path = useMemo(() => {
    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(page * PAGE_SIZE),
    });
    if (environment) params.set("environment", environment);
    if (kind) params.set("kind", kind);
    if (search) params.set("search", search);
    return `/resources?${params.toString()}`;
  }, [environment, kind, page, search]);

  const { data, loading, error } = useApi<ResourcePage>(path);

  return (
    <>
      <PageHeader
        title="Infrastructure inventory"
        description="Everything Terraform manages in the account, grouped by environment. Data is read-only: mutations flow through the pipeline, never the console."
      />

      <div className="toolbar">
        <input
          className="input search"
          type="search"
          placeholder="Search name, id, owner or tag…"
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
          aria-label="Search resources"
        />
        <select
          className="input"
          value={environment}
          onChange={(event) => {
            setEnvironment(event.target.value);
            setPage(0);
          }}
          aria-label="Filter by environment"
        >
          <option value="">All environments</option>
          <option value="dev">Development</option>
          <option value="prod">Production</option>
        </select>
        <select
          className="input"
          value={kind}
          onChange={(event) => {
            setKind(event.target.value);
            setPage(0);
          }}
          aria-label="Filter by resource type"
        >
          <option value="">All types</option>
          {KINDS.map((value) => (
            <option key={value} value={value}>
              {titleCase(value)}
            </option>
          ))}
        </select>
        {data ? <span className="chip">{data.total} resources</span> : null}
      </div>

      {error ? <ErrorBanner message={error} /> : null}
      {loading && !data ? <Loading label="Loading inventory" /> : null}

      {data && data.items.length === 0 ? (
        <EmptyState title="No resources match those filters" hint="Clear the search or pick another environment." />
      ) : null}

      {data && data.items.length > 0 ? (
        <>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Resource</th>
                  <th>Type</th>
                  <th>Environment</th>
                  <th>Status</th>
                  <th>Owner</th>
                  <th className="numeric">Monthly cost</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((resource) => (
                  <tr
                    key={resource.id}
                    className="row-clickable"
                    onClick={() => setSelected(resource)}
                    tabIndex={0}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") setSelected(resource);
                    }}
                  >
                    <td>
                      <div className="cell-strong">{resource.name}</div>
                      <div className="cell-sub mono">{resource.id}</div>
                    </td>
                    <td>{titleCase(resource.kind)}</td>
                    <td style={{ textTransform: "capitalize" }}>{resource.environment}</td>
                    <td>
                      <Badge tone={toneForStatus(resource.status)}>{titleCase(resource.status)}</Badge>
                    </td>
                    <td className="small dim">{resource.owner}</td>
                    <td className="numeric mono">{currencyPrecise(resource.monthly_cost_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={data.total}
            onPage={(next) => setPage(next)}
          />
        </>
      ) : null}

      <Modal
        open={Boolean(selected)}
        title={selected?.name ?? "Resource"}
        subtitle={selected ? `${titleCase(selected.kind)} · ${selected.id}` : undefined}
        onClose={() => setSelected(null)}
        wide
      >
        {selected ? (
          <div className="stack">
            <dl className="detail-list">
              <dt>Environment</dt>
              <dd style={{ textTransform: "capitalize" }}>{selected.environment}</dd>
              <dt>Region</dt>
              <dd className="mono">{selected.region}</dd>
              <dt>Status</dt>
              <dd>
                <Badge tone={toneForStatus(selected.status)}>{titleCase(selected.status)}</Badge>
              </dd>
              <dt>Owner</dt>
              <dd>{selected.owner}</dd>
              <dt>Created</dt>
              <dd>{dateTime(selected.created_at)}</dd>
              <dt>Monthly cost</dt>
              <dd className="mono">{currencyPrecise(selected.monthly_cost_usd)}</dd>
            </dl>

            {selected.health ? (
              <>
                <div className="divider" />
                <div className="row row--between">
                  <strong style={{ fontSize: 12.5 }}>Health telemetry</strong>
                  <Badge tone={toneForStatus(selected.health.status)}>{selected.health.score}/100</Badge>
                </div>
                <dl className="detail-list">
                  <dt>CPU / Memory / Disk</dt>
                  <dd className="mono">
                    {selected.health.cpu_percent}% / {selected.health.memory_percent}% /{" "}
                    {selected.health.disk_percent}%
                  </dd>
                  <dt>Patch status</dt>
                  <dd style={{ textTransform: "capitalize" }}>{selected.health.patch_status}</dd>
                  <dt>Agent version</dt>
                  <dd className="mono">{selected.health.agent_version}</dd>
                  <dt>Uptime</dt>
                  <dd>{selected.health.uptime_hours} hours</dd>
                </dl>
              </>
            ) : null}

            <div className="divider" />
            <div className="row row--between">
              <strong style={{ fontSize: 12.5 }}>Tags</strong>
            </div>
            <div className="row" style={{ flexWrap: "wrap" }}>
              {Object.entries(selected.tags).map(([key, value]) => (
                <span className="chip" key={key}>
                  {key}={value || "∅"}
                </span>
              ))}
            </div>

            <div className="divider" />
            <strong style={{ fontSize: 12.5 }}>Configuration</strong>
            <pre className="code-block">{JSON.stringify(selected.config, null, 2)}</pre>
          </div>
        ) : null}
      </Modal>
    </>
  );
}
