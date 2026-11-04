import { useEffect } from "react";

import type { Tone } from "../lib/format";
import { healthColor, percent } from "../lib/format";

/* ------------------------------------------------------------------ badge */
export function Badge({ tone = "neutral", children }: { tone?: Tone; children: React.ReactNode }) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}

/* -------------------------------------------------------------------- kpi */
export function StatCard({
  label,
  value,
  hint,
  tone = "info",
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  tone?: "info" | "accent" | "warn" | "danger";
}) {
  return (
    <div className={`kpi kpi--${tone}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {hint ? <div className="kpi-hint">{hint}</div> : null}
    </div>
  );
}

/* --------------------------------------------------------------- page head */
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        <h1 className="page-title">{title}</h1>
        {description ? <p className="page-description">{description}</p> : null}
      </div>
      {actions ? <div className="actions">{actions}</div> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ states */
export function Loading({ label = "Loading data" }: { label?: string }) {
  return (
    <div className="loading-block" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{label}…</span>
    </div>
  );
}

export function ErrorBanner({ message, onDismiss }: { message: string; onDismiss?: () => void }) {
  return (
    <div className="error-banner" role="alert">
      <span>{message}</span>
      {onDismiss ? (
        <button type="button" className="btn-link" onClick={onDismiss} aria-label="Dismiss error">
          Dismiss
        </button>
      ) : null}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {hint ? <div className="small" style={{ marginTop: 6 }}>{hint}</div> : null}
    </div>
  );
}

/* ------------------------------------------------------------------- modal */
export function Modal({
  open,
  title,
  subtitle,
  onClose,
  children,
  footer,
  wide = false,
}: {
  open: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div
        className={`modal${wide ? " modal--wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 style={{ fontSize: 16 }}>{title}</h2>
            {subtitle ? <div className="card-subtitle">{subtitle}</div> : null}
          </div>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close dialog">
            Close
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer ? <div className="modal-footer">{footer}</div> : null}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------- chart */
export interface ChartSegment {
  label: string;
  value: number;
  color: string;
}

export function DonutChart({
  segments,
  size = 168,
  thickness = 14,
  centerValue,
  centerLabel,
}: {
  segments: ChartSegment[];
  size?: number;
  thickness?: number;
  centerValue?: React.ReactNode;
  centerLabel?: string;
}) {
  const total = segments.reduce((sum, segment) => sum + segment.value, 0);
  const radius = (size - thickness) / 2;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  const denominator = total || 1;

  return (
    <div
      style={{ position: "relative", width: size, height: size, flex: "0 0 auto" }}
      role="img"
      aria-label={segments.map((segment) => `${segment.label}: ${segment.value}`).join(", ")}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--surface-3)"
          strokeWidth={thickness}
        />
        {segments.map((segment) => {
          const length = (segment.value / denominator) * circumference;
          const circle = (
            <circle
              key={segment.label}
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={segment.color}
              strokeWidth={thickness}
              strokeDasharray={`${length} ${circumference - length}`}
              strokeDashoffset={-offset}
              transform={`rotate(-90 ${size / 2} ${size / 2})`}
            />
          );
          offset += length;
          return circle;
        })}
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "grid",
          placeItems: "center",
          textAlign: "center",
        }}
      >
        <div>
          <div style={{ fontSize: 24, fontWeight: 650, letterSpacing: "-0.02em" }}>
            {centerValue ?? total}
          </div>
          {centerLabel ? <div className="small muted">{centerLabel}</div> : null}
        </div>
      </div>
    </div>
  );
}

export function Legend({ segments }: { segments: ChartSegment[] }) {
  return (
    <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 8 }}>
      {segments.map((segment) => (
        <li key={segment.label} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
          <span
            aria-hidden="true"
            style={{
              width: 8,
              height: 8,
              borderRadius: 2,
              background: segment.color,
              display: "inline-block",
            }}
          />
          <span style={{ color: "var(--text-dim)", flex: 1 }}>{segment.label}</span>
          <span className="mono" style={{ color: "var(--text)" }}>{segment.value}</span>
        </li>
      ))}
    </ul>
  );
}

export function BarChart({
  items,
  formatValue = (value: number) => String(value),
}: {
  items: Array<{ label: string; value: number; color?: string }>;
  formatValue?: (value: number) => string;
}) {
  const max = Math.max(...items.map((item) => item.value), 1);
  return (
    <div style={{ display: "grid", gap: 12 }}>
      {items.map((item) => (
        <div key={item.label}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              fontSize: 11.5,
              marginBottom: 5,
              color: "var(--text-dim)",
            }}
          >
            <span style={{ textTransform: "capitalize" }}>{item.label.replace(/_/g, " ")}</span>
            <span className="mono">{formatValue(item.value)}</span>
          </div>
          <div style={{ height: 6, background: "var(--surface-3)", borderRadius: 999 }}>
            <div
              style={{
                width: `${Math.max((item.value / max) * 100, item.value > 0 ? 3 : 0)}%`,
                height: "100%",
                borderRadius: 999,
                background: item.color ?? "linear-gradient(90deg, #38bdf8, #34d399)",
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ health */
export function HealthBar({ score }: { score: number }) {
  return (
    <div className="meter-row">
      <div className="health-bar" role="progressbar" aria-valuenow={score} aria-valuemin={0} aria-valuemax={100}>
        <span style={{ width: `${score}%`, background: healthColor(score) }} />
      </div>
      <span className="mono" style={{ minWidth: 32 }}>{percent(score)}</span>
    </div>
  );
}

export function ScoreRing({ score, label }: { score: number; label: string }) {
  return (
    <DonutChart
      size={150}
      thickness={12}
      centerValue={<span style={{ color: healthColor(score) }}>{score.toFixed(1)}</span>}
      centerLabel={label}
      segments={[
        { label: "Passing", value: score, color: healthColor(score) },
        { label: "Failing", value: Math.max(100 - score, 0), color: "#1e2c42" },
      ]}
    />
  );
}

/* -------------------------------------------------------------- pagination */
export function Pagination({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
}) {
  const pages = Math.max(Math.ceil(total / pageSize), 1);
  return (
    <div className="pagination">
      <span className="muted">
        Page {page + 1} of {pages} · {total} records
      </span>
      <button type="button" className="btn btn-ghost btn-sm" disabled={page === 0} onClick={() => onPage(page - 1)}>
        Previous
      </button>
      <button
        type="button"
        className="btn btn-ghost btn-sm"
        disabled={page + 1 >= pages}
        onClick={() => onPage(page + 1)}
      >
        Next
      </button>
    </div>
  );
}
