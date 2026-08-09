import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  NOT_TRACKED,
  RunFailureReason,
  runDetailHref,
  truncateError,
} from "@/lib/projects/run-display";
import type { AgentRunOut } from "@/lib/types";

const run = (over: Partial<AgentRunOut> = {}): AgentRunOut =>
  ({
    id: "11111111-1111-7111-8111-111111111111",
    project_id: "22222222-2222-7222-8222-222222222222",
    agent_definition_id: "33333333-3333-7333-8333-333333333333",
    status: "failed",
    error_message: null,
    input_payload: {},
    created_at: new Date().toISOString(),
    ...over,
  }) as AgentRunOut;

describe("runDetailHref", () => {
  it("points at the project's run detail, not the receipt ledger", () => {
    // Regression: both run tables linked to /dashboard/ledger/{runId}, which
    // fetches a *receipt* by that id and cannot resolve a run.
    expect(runDetailHref("p1", "r1")).toBe("/dashboard/projects/p1/runs/r1");
  });
});

describe("truncateError", () => {
  it("leaves a short message intact", () => {
    expect(truncateError("boom")).toBe("boom");
  });

  it("collapses whitespace so a multi-line traceback stays one line", () => {
    expect(truncateError("line one\n   line two")).toBe("line one line two");
  });

  it("truncates with an ellipsis past the limit", () => {
    const out = truncateError("x".repeat(200));
    expect(out).toHaveLength(120);
    expect(out.endsWith("…")).toBe(true);
  });
});

describe("RunFailureReason", () => {
  it("shows the reason with the full text available on hover", () => {
    const message = "llm_step_failed: upstream returned 401 Unauthorized";
    render(<RunFailureReason run={run({ error_message: message })} />);

    const el = screen.getByTestId("run-failure-reason");
    expect(el.textContent).toContain("llm_step_failed");
    expect(el.getAttribute("title")).toBe(message);
  });

  it("renders nothing for a successful run even if a message lingers", () => {
    render(<RunFailureReason run={run({ status: "succeeded", error_message: "stale" })} />);
    expect(screen.queryByTestId("run-failure-reason")).toBeNull();
  });

  it("renders nothing when a failed run carries no message", () => {
    render(<RunFailureReason run={run({ status: "failed", error_message: null })} />);
    expect(screen.queryByTestId("run-failure-reason")).toBeNull();
  });
});

describe("NOT_TRACKED", () => {
  it("says unimplemented rather than showing a bare em-dash", () => {
    expect(NOT_TRACKED).not.toBe("—");
    expect(NOT_TRACKED.toLowerCase()).toContain("not tracked");
  });
});
