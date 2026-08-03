import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { CryptoHealthCard } from "@/components/command-center/crypto-health-card";
import { useCryptoHealthQuery } from "@/lib/queries/command-center";

vi.mock("@/lib/queries/command-center", () => ({
  useCryptoHealthQuery: vi.fn(),
}));

const mockUse = vi.mocked(useCryptoHealthQuery);

describe("CryptoHealthCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders skeleton when loading", () => {
    mockUse.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      error: null,
      refetch: () => {},
    } as ReturnType<typeof useCryptoHealthQuery>);
    const { container } = render(<CryptoHealthCard projectId="p1" />);
    expect(container.querySelector('[aria-hidden="true"]')).toBeTruthy();
  });

  it("shows error + RETRY on failure", () => {
    const refetch = vi.fn();
    mockUse.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: new Error("nope"),
      refetch,
    } as ReturnType<typeof useCryptoHealthQuery>);
    render(<CryptoHealthCard projectId="p1" />);
    expect(screen.getByText(/Couldn/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "RETRY" }));
    expect(refetch).toHaveBeenCalled();
  });

  it("renders no_data as muted dash and no sealed receipts yet", () => {
    mockUse.mockReturnValue({
      data: {
        ed25519_status: "no_data",
        mldsa65_status: "no_data",
        merkle_status: "no_data",
        next_rotation_days: null,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: () => {},
    } as ReturnType<typeof useCryptoHealthQuery>);
    render(<CryptoHealthCard projectId="p1" />);
    expect(screen.getAllByText("no sealed receipts yet").length).toBe(2);
  });
});
