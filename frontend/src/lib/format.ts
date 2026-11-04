export type Tone = "success" | "warning" | "danger" | "info" | "neutral" | "violet";

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const currencyPreciseFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const compactFormatter = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 1,
});

export function currency(value: number): string {
  return currencyFormatter.format(value);
}

export function currencyPrecise(value: number): string {
  return currencyPreciseFormatter.format(value);
}

export function compactNumber(value: number): string {
  return compactFormatter.format(value);
}

export function percent(value: number, digits = 0): string {
  return `${value.toFixed(digits)}%`;
}

export function titleCase(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "never";
  const timestamp = new Date(iso).getTime();
  if (Number.isNaN(timestamp)) return "unknown";
  const deltaSeconds = Math.round((timestamp - Date.now()) / 1000);
  const divisions: Array<{ amount: number; unit: Intl.RelativeTimeFormatUnit }> = [
    { amount: 60, unit: "second" },
    { amount: 60, unit: "minute" },
    { amount: 24, unit: "hour" },
    { amount: 7, unit: "day" },
    { amount: 4.34524, unit: "week" },
    { amount: 12, unit: "month" },
    { amount: Number.POSITIVE_INFINITY, unit: "year" },
  ];
  let duration = deltaSeconds;
  for (const division of divisions) {
    if (Math.abs(duration) < division.amount) {
      return new Intl.RelativeTimeFormat("en", { numeric: "auto" }).format(
        Math.round(duration),
        division.unit,
      );
    }
    duration /= division.amount;
  }
  return "unknown";
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
    timeZoneName: "short",
  });
}

export function shortSha(value: string, length = 8): string {
  return value.length <= length ? value : `${value.slice(0, length)}…`;
}

export function toneForSeverity(severity: string): Tone {
  switch (severity) {
    case "critical":
      return "danger";
    case "high":
      return "warning";
    case "medium":
      return "info";
    default:
      return "neutral";
  }
}

export function toneForStatus(status: string): Tone {
  switch (status) {
    case "succeeded":
    case "available":
    case "running":
    case "success":
    case "compliant":
    case "healthy":
      return "success";
    case "in_progress":
    case "pending":
    case "pending_approval":
    case "approved":
      return "info";
    case "warning":
      return "warning";
    case "failed":
    case "rejected":
    case "critical":
    case "failure":
    case "overdue":
      return "danger";
    case "rolled_back":
      return "violet";
    default:
      return "neutral";
  }
}

export function toneForHealth(status: string | null | undefined): Tone {
  switch (status) {
    case "healthy":
      return "success";
    case "warning":
      return "warning";
    case "critical":
      return "danger";
    default:
      return "neutral";
  }
}

export function healthColor(score: number): string {
  if (score >= 85) return "var(--accent)";
  if (score >= 60) return "var(--warn)";
  return "var(--danger)";
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  return "Something went wrong.";
}
