import { describe, expect, it } from "vitest";

import { eventsBackoffMs } from "@/lib/events/use-axiom-events";

describe("eventsBackoffMs", () => {
  it("returns 1s,2s,4s,8s,16s then 30s cap", () => {
    expect(eventsBackoffMs(0)).toBe(1_000);
    expect(eventsBackoffMs(1)).toBe(2_000);
    expect(eventsBackoffMs(2)).toBe(4_000);
    expect(eventsBackoffMs(3)).toBe(8_000);
    expect(eventsBackoffMs(4)).toBe(16_000);
    expect(eventsBackoffMs(5)).toBe(30_000);
    expect(eventsBackoffMs(50)).toBe(30_000);
  });
});
