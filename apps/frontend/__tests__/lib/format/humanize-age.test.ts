import { describe, expect, it } from "vitest";

import { humanizeShortDurationSeconds } from "@/lib/format/humanize-age";

describe("humanizeShortDurationSeconds", () => {
  it("uses seconds when under 60s", () => {
    expect(humanizeShortDurationSeconds(0)).toBe("0s");
    expect(humanizeShortDurationSeconds(59.9)).toBe("59s");
  });

  it("uses minutes when 60s to under 1h", () => {
    expect(humanizeShortDurationSeconds(60)).toBe("1m");
    expect(humanizeShortDurationSeconds(59 * 60 + 30)).toBe("59m");
  });

  it("uses hours when 1h to under 24h", () => {
    expect(humanizeShortDurationSeconds(3600)).toBe("1h");
    expect(humanizeShortDurationSeconds(23 * 3600 + 1)).toBe("23h");
  });

  it("uses days at 24h and beyond", () => {
    expect(humanizeShortDurationSeconds(24 * 3600)).toBe("1d");
    expect(humanizeShortDurationSeconds(48 * 3600 + 1)).toBe("2d");
  });
});
