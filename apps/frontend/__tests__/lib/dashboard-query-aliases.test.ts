import { describe, expect, it } from "vitest";

import { dashboardKeys } from "@/lib/dashboard-query-keys";

describe("Phase 7.6 query key aliases", () => {
  it("receiptsDetailed, governanceLedgerBundle, pendingApprovals match canonical keys", () => {
    const pid = "p-1";
    expect(dashboardKeys.governanceLedgerBundle(pid)).toEqual(dashboardKeys.ledgerBundle(pid));
    expect(dashboardKeys.receiptsDetailed(pid)).toEqual(dashboardKeys.ledgerBundle(pid));
    expect(dashboardKeys.pendingApprovals(pid)).toEqual(dashboardKeys.pendingReceipts(pid));
    expect(dashboardKeys.attentionStrip(pid)).toEqual(dashboardKeys.pendingReceipts(pid));
    expect(dashboardKeys.commandCenterTsaStatus(pid)).toEqual(dashboardKeys.commandCenterTsa(pid));
  });
});
