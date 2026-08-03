import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { CryptoFooter } from "@/components/command-center/crypto-footer";
import { useTsaStatusQuery } from "@/lib/queries/command-center";

vi.mock("@/lib/queries/command-center", () => ({
  useTsaStatusQuery: vi.fn(),
}));

const mockTsa = vi.mocked(useTsaStatusQuery);

describe("CryptoFooter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows static fallback when tsa is pending (skeleton, not static text yet)", () => {
    mockTsa.mockReturnValue({ isPending: true, data: undefined } as ReturnType<typeof useTsaStatusQuery>);
    const { container } = render(
      <CryptoFooter projectId="p1" merkleDepth={3} policyLabel="P (v1)" />,
    );
    expect(container.querySelector('[aria-hidden="true"]')).toBeTruthy();
  });

  it("uses TSA NOT YET ANCHORED when last_anchor_age_seconds is null", () => {
    mockTsa.mockReturnValue({
      isPending: false,
      data: { kind: "ok", data: { last_anchor_age_seconds: null, tsa_authority_url: null } },
    } as ReturnType<typeof useTsaStatusQuery>);
    render(<CryptoFooter projectId="p1" merkleDepth="—" policyLabel="P" />);
    expect(screen.getByText(/TSA NOT YET ANCHORED/)).toBeTruthy();
  });

  it("falls back to static line when tsa result is fallback", () => {
    mockTsa.mockReturnValue({
      isPending: false,
      data: { kind: "fallback" },
    } as ReturnType<typeof useTsaStatusQuery>);
    const { container } = render(
      <CryptoFooter projectId="p1" merkleDepth={2} policyLabel="P" />,
    );
    expect(container.textContent).toContain("POLICY: P");
    expect(container.textContent).toContain("MERKLE DEPTH 2");
  });
});
