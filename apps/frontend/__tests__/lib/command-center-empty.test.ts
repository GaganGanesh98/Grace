import { describe, expect, it } from "vitest";

import {
  getDurationLabel,
  isCommandCenterEmptyState,
  isRecordInLast30Days,
} from "@/lib/command-center-empty";

describe("isRecordInLast30Days", () => {
  it("is true for a timestamp 1 day ago", () => {
    const iso = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    expect(isRecordInLast30Days(iso)).toBe(true);
  });
});

describe("isCommandCenterEmptyState", () => {
  it("is true with zero agents and no recent records", () => {
    const old = new Date(Date.now() - 40 * 24 * 60 * 60 * 1000).toISOString();
    expect(isCommandCenterEmptyState(0, [old])).toBe(true);
  });

  it("is false when a record is in the last 30 days", () => {
    const recent = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString();
    expect(isCommandCenterEmptyState(0, [recent])).toBe(false);
  });

  it("is false when agent count is non-zero", () => {
    expect(isCommandCenterEmptyState(1, [])).toBe(false);
  });
});

describe("getDurationLabel", () => {
  it("returns em dash for null execution", () => {
    expect(getDurationLabel(null)).toBe("—");
  });

  it("formats duration_ms in ms", () => {
    expect(getDurationLabel({ duration_ms: 312 })).toBe("312ms");
  });
});
