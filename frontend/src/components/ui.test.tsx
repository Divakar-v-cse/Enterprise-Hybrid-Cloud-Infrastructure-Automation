import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Badge, DonutChart, EmptyState, HealthBar, PageHeader, StatCard } from "./ui";

describe("UI primitives", () => {
  it("renders a badge with its tone class", () => {
    render(<Badge tone="danger">Critical</Badge>);
    const badge = screen.getByText("Critical");
    expect(badge).toHaveClass("badge", "badge--danger");
  });

  it("renders KPI values and hints", () => {
    render(<StatCard label="Managed resources" value={37} hint="2 environments" />);
    expect(screen.getByText("Managed resources")).toBeInTheDocument();
    expect(screen.getByText("37")).toBeInTheDocument();
    expect(screen.getByText("2 environments")).toBeInTheDocument();
  });

  it("renders a page header with actions", () => {
    render(
      <PageHeader
        title="Compliance posture"
        description="Policy as code"
        actions={<button type="button">Scan</button>}
      />,
    );
    expect(screen.getByRole("heading", { name: "Compliance posture" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Scan" })).toBeInTheDocument();
  });

  it("exposes health as an accessible progress bar", () => {
    render(<HealthBar score={72} />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "72");
  });

  it("describes donut segments for screen readers", () => {
    render(
      <DonutChart
        segments={[
          { label: "Healthy", value: 5, color: "#34d399" },
          { label: "Critical", value: 1, color: "#f87171" },
        ]}
        centerValue={6}
        centerLabel="servers"
      />,
    );
    expect(screen.getByRole("img")).toHaveAttribute("aria-label", "Healthy: 5, Critical: 1");
    expect(screen.getByText("servers")).toBeInTheDocument();
  });

  it("renders an empty state", () => {
    render(<EmptyState title="Nothing here" hint="Adjust the filters" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.getByText("Adjust the filters")).toBeInTheDocument();
  });
});
