import { describe, expect, it, vi, beforeEach } from "vitest";
import { keysForType } from "@/lib/events/use-axiom-events";
import { dashboardKeys } from "@/lib/dashboard-query-keys";

beforeEach(() => {
  vi.resetAllMocks();
});

describe("Project workspace (Phase 7.12)", () => {
  it("exposes project workspace query key helpers", () => {
    expect(dashboardKeys.project("p1")).toEqual(["axiom", "project", "p1"]);
    expect(dashboardKeys.recentProjectRuns("p1")).toEqual(["axiom", "recent-project-runs", "p1"]);
    expect(dashboardKeys.projectRunsList("p1", "all:q")).toEqual([
      "axiom",
      "project-runs-list",
      "p1",
      "all:q",
    ]);
  });
});

describe("useAxiomEvents invalidation map (extract)", () => {
  it("run.started includes recent and project list prefixes", () => {
    const k = keysForType("run.started", "p1", ["24h"]);
    const sk = k.map((x) => JSON.stringify(x));
    expect(sk.some((s) => s.includes("recent-project-runs"))).toBe(true);
    expect(sk.some((s) => s.includes("project-runs-list") && s.includes("p1"))).toBe(true);
  });
});
