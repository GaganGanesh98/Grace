import { describe, expect, it } from "vitest";

import { formatDurationMs } from "@/lib/format/format-duration";

describe("formatDurationMs", () => {
  it("returns em dash for null/invalid", () => {
    expect(formatDurationMs(null)).toBe("—");
    expect(formatDurationMs(undefined)).toBe("—");
    expect(formatDurationMs(Number.NaN)).toBe("—");
  });

  it("formats under 1000ms as integer ms", () => {
    expect(formatDurationMs(312)).toBe("312ms");
    expect(formatDurationMs(999)).toBe("999ms");
  });

  it("formats 1s – 59.9s with one decimal", () => {
    expect(formatDurationMs(1000)).toBe("1.0s");
    expect(formatDurationMs(1500)).toBe("1.5s");
    expect(formatDurationMs(59_999)).toBe("60.0s");
  });

  it("formats 60s+ as minutes with one decimal", () => {
    expect(formatDurationMs(60_000)).toBe("1.0m");
    expect(formatDurationMs(90_000)).toBe("1.5m");
  });
});
