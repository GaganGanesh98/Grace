import { describe, expect, it } from "vitest";

import { dashboardKeys } from "@/lib/dashboard-query-keys";

describe("dashboardKeys", () => {
  it("namespaces agent resources per project", () => {
    expect(dashboardKeys.agentDefinitions("p1")).toEqual(["axiom", "agent-definitions", "p1"]);
    expect(dashboardKeys.agentDefinitionsNonArchivedCount("p1")).toEqual([
      "axiom",
      "agent-definitions-count",
      "p1",
    ]);
    expect(dashboardKeys.agentDefinition("p1", "d1")).toEqual([
      "axiom",
      "agent-definition",
      "p1",
      "d1",
    ]);
    expect(dashboardKeys.agentRuns("p1")).toEqual(["axiom", "agent-runs", "p1"]);
    expect(dashboardKeys.agentRun("p1", "r1")).toEqual(["axiom", "agent-run", "p1", "r1"]);
    expect(dashboardKeys.vaultKeys("p1")).toEqual(["axiom", "vault-keys", "p1"]);
  });

  it("namespaces command center aggregate keys", () => {
    expect(dashboardKeys.commandCenterPosture("p1", "24h")).toEqual([
      "axiom",
      "command-center",
      "posture",
      "p1",
      "24h",
    ]);
    expect(dashboardKeys.commandCenterCryptoHealth("p1")).toEqual([
      "axiom",
      "command-center",
      "crypto-health",
      "p1",
    ]);
    expect(dashboardKeys.commandCenterPolicyBreakdown("p1", "7d")).toEqual([
      "axiom",
      "command-center",
      "policy-breakdown",
      "p1",
      "7d",
    ]);
    expect(dashboardKeys.commandCenterTsa("p1")).toEqual(["axiom", "command-center", "tsa-status", "p1"]);
    expect(dashboardKeys.commandCenterAgentDefinitionsAll("p1")).toEqual([
      "axiom",
      "command-center",
      "agent-definitions-all",
      "p1",
    ]);
  });

  it("namespaces project workspace keys (Phase 7.12)", () => {
    expect(dashboardKeys.project("p1")).toEqual(["axiom", "project", "p1"]);
    expect(dashboardKeys.projectRunsListAll("p1")).toEqual(["axiom", "project-runs-list", "p1"]);
  });
});
