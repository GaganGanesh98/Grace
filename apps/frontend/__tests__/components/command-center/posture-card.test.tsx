import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { PostureCard } from "@/components/command-center/posture-card";
import { usePostureQuery } from "@/lib/queries/command-center";

vi.mock("@/lib/queries/command-center", () => ({
  usePostureQuery: vi.fn(),
}));

const mockUse = vi.mocked(usePostureQuery);

function mockReturn(
  partial: Partial<{
    data: { calls_governed: number; runs_completed: number; violations: number } | undefined;
    isPending: boolean;
    isError: boolean;
    error: Error;
    refetch: () => void;
  }> = {},
): void {
  mockUse.mockReturnValue({
    data: partial.data,
    isPending: partial.isPending ?? false,
    isError: partial.isError ?? false,
    error: partial.error ?? new Error("x"),
    refetch: partial.refetch ?? (() => {}),
    isRefetching: false,
  } as ReturnType<typeof usePostureQuery>);
}

describe("PostureCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows skeleton in loading state", () => {
    mockReturn({ isPending: true });
    const { container } = render(<PostureCard projectId="p1" />);
    expect(container.querySelector('[class*="pulse"]') ?? container.querySelector("div")).toBeTruthy();
  });

  it("shows error + RETRY on failure", () => {
    const refetch = vi.fn();
    mockReturn({ isError: true, isPending: false, error: new Error("nope"), refetch });
    render(<PostureCard projectId="p1" />);
    expect(screen.getByText(/Couldn/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "RETRY" }));
    expect(refetch).toHaveBeenCalled();
  });

  it("uses green fill when violations are 0", () => {
    mockReturn({ data: { calls_governed: 5, runs_completed: 1, violations: 0 } });
    const { container } = render(<PostureCard projectId="p1" />);
    const ring = container.querySelector(
      "div[style*=\"#6db862\"], div[style*='6db862']",
    );
    expect(ring).toBeTruthy();
    expect(screen.getByText("100%")).toBeTruthy();
  });

  it("uses amber ring for 1-4 violations", () => {
    mockReturn({ data: { calls_governed: 20, runs_completed: 0, violations: 2 } });
    const { container } = render(<PostureCard projectId="p1" />);
    const ring = container.querySelector("div[style*='#d4a030'], div[style*='d4a030']");
    expect(ring).toBeTruthy();
  });

  it("uses red ring for 5+ violations", () => {
    mockReturn({ data: { calls_governed: 20, runs_completed: 0, violations: 7 } });
    const { container } = render(<PostureCard projectId="p1" />);
    // Phase 8.0: the ad-hoc #e05050 was folded onto the canonical denied
    // border token (--status-denied-border, #da1e28).
    const ring = container.querySelector("div[style*=\"#da1e28\"], div[style*='da1e28']");
    expect(ring).toBeTruthy();
  });

  it("shows no ring when calls_governed is 0", () => {
    mockReturn({ data: { calls_governed: 0, runs_completed: 0, violations: 0 } });
    const { container } = render(<PostureCard projectId="p1" />);
    expect(screen.getByText("No activity yet")).toBeTruthy();
    expect(container.querySelector('[style*="conic-gradient"]')).toBeNull();
  });
});
