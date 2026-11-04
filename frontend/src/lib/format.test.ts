import { describe, expect, it } from "vitest";

import {
  currency,
  currencyPrecise,
  errorMessage,
  healthColor,
  percent,
  relativeTime,
  titleCase,
  toneForHealth,
  toneForSeverity,
  toneForStatus,
} from "./format";

describe("format helpers", () => {
  it("formats currency at the right precision", () => {
    expect(currency(1234.56)).toBe("$1,235");
    expect(currencyPrecise(1234.5)).toBe("$1,234.50");
  });

  it("formats percentages", () => {
    expect(percent(93.456, 1)).toBe("93.5%");
    expect(percent(100)).toBe("100%");
  });

  it("title-cases snake_case values", () => {
    expect(titleCase("pending_approval")).toBe("Pending Approval");
    expect(titleCase("load_balancer")).toBe("Load Balancer");
  });

  it("maps severities and statuses to tones", () => {
    expect(toneForSeverity("critical")).toBe("danger");
    expect(toneForSeverity("high")).toBe("warning");
    expect(toneForSeverity("low")).toBe("neutral");
    expect(toneForStatus("succeeded")).toBe("success");
    expect(toneForStatus("pending_approval")).toBe("info");
    expect(toneForStatus("failed")).toBe("danger");
    expect(toneForHealth("warning")).toBe("warning");
    expect(toneForHealth(null)).toBe("neutral");
  });

  it("colours health scores consistently", () => {
    expect(healthColor(95)).toBe("var(--accent)");
    expect(healthColor(70)).toBe("var(--warn)");
    expect(healthColor(20)).toBe("var(--danger)");
  });

  it("renders relative times", () => {
    const hourAgo = new Date(Date.now() - 60 * 60 * 1000).toISOString();
    expect(relativeTime(hourAgo)).toMatch(/hour/);
    expect(relativeTime(null)).toBe("never");
  });

  it("extracts a message from unknown errors", () => {
    expect(errorMessage(new Error("boom"))).toBe("boom");
    expect(errorMessage("plain")).toBe("plain");
    expect(errorMessage(42)).toBe("Something went wrong.");
  });
});
