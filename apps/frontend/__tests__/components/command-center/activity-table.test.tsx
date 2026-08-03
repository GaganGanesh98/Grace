import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ActivityTable } from "@/components/command-center/activity-table";
import type { GovernanceReceiptRecord } from "@/lib/governance-types";

function makeRecord(id: string, overrides: Partial<GovernanceReceiptRecord> = {}): GovernanceReceiptRecord {
  const base: GovernanceReceiptRecord = {
    id,
    intent: {
      id: "i1",
      project_id: "p1",
      agent_id: "agent-1",
      action_type: "tool.llm.groq",
      target: "https://api.example",
      parameters: {},
      risk_declared: "low",
      mode: "sync",
      metadata: {},
      created_at: new Date().toISOString(),
    },
    verdict: {
      id: "v1",
      verdict: "allow",
      reason: null,
      policy_version: "1",
      rules_evaluated: [],
      risk_assessed: "low",
      context: {},
      created_at: new Date().toISOString(),
    },
    execution: { duration_ms: 99 },
    verification: { status: "pass", mismatches: [] },
    signatures: { ed25519: "a", ml_dsa_65: "b", key_id: "k" },
    merkle: { leaf: "l", root: "r", depth: 3, path: [] },
    policy_version: "1",
    sealed_at: new Date().toISOString(),
    status: "sealed",
    signer_public: null,
  };
  return { ...base, ...overrides };
}

describe("ActivityTable", () => {
  it("invokes onRowSelect when a row is clicked", () => {
    const onSelect = vi.fn();
    const qc = new QueryClient();
    const row = makeRecord("rcpt_abcdefgh_test0001");
    render(
      <QueryClientProvider client={qc}>
        <ActivityTable
          rows={[row]}
          onRowSelect={onSelect}
          agentsLinkHref="/dashboard/agents"
        />
      </QueryClientProvider>,
    );
    const r = document.querySelector(`[data-receipt-row="${row.id}"]`);
    expect(r).toBeTruthy();
    fireEvent.click(r!);
    expect(onSelect).toHaveBeenCalledWith(row.id);
  });

  it("invokes onRowSelect on Enter from the row", () => {
    const onSelect = vi.fn();
    const qc = new QueryClient();
    const row = makeRecord("rcpt_z");
    render(
      <QueryClientProvider client={qc}>
        <ActivityTable
          rows={[row]}
          onRowSelect={onSelect}
          agentsLinkHref="/dashboard/agents"
        />
      </QueryClientProvider>,
    );
    const r = document.querySelector(`[data-receipt-row="${row.id}"]`) as HTMLElement;
    r.focus();
    fireEvent.keyDown(r, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith(row.id);
  });

  it("formats Dur from duration_ms when set", () => {
    const qc = new QueryClient();
    const row = makeRecord("r-dur", {
      duration_ms: 1500,
      execution: null,
    });
    const { getByText } = render(
      <QueryClientProvider client={qc}>
        <ActivityTable
          rows={[row]}
          onRowSelect={vi.fn()}
          agentsLinkHref="/dashboard/agents"
        />
      </QueryClientProvider>,
    );
    expect(getByText("1.5s")).toBeTruthy();
  });

  it("shows agent name from map when ready", () => {
    const qc = new QueryClient();
    const id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
    const base = makeRecord("r-n");
    const row: GovernanceReceiptRecord = {
      ...base,
      intent: { ...base.intent, agent_id: id },
    };
    const m = new Map<string, string>([[id, "My Bot"]]);
    const { getByText } = render(
      <QueryClientProvider client={qc}>
        <ActivityTable
          rows={[row]}
          onRowSelect={vi.fn()}
          agentsLinkHref="/dashboard/agents"
          agentNameById={m}
          agentNameLoadState="ready"
        />
      </QueryClientProvider>,
    );
    expect(getByText("My Bot")).toBeTruthy();
  });

  it("shows (deleted) when id missing from map and ready", () => {
    const qc = new QueryClient();
    const id = "bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee";
    const base = makeRecord("r-x");
    const row: GovernanceReceiptRecord = { ...base, intent: { ...base.intent, agent_id: id } };
    const m = new Map<string, string>();
    const { getByText } = render(
      <QueryClientProvider client={qc}>
        <ActivityTable
          rows={[row]}
          onRowSelect={vi.fn()}
          agentsLinkHref="/dashboard/agents"
          agentNameById={m}
          agentNameLoadState="ready"
        />
      </QueryClientProvider>,
    );
    expect(getByText("(deleted)")).toBeTruthy();
  });
});
