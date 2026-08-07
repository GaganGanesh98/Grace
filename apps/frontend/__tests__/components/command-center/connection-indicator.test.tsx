import { render, screen } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";

import { ConnectionIndicator } from "@/components/command-center/connection-indicator";

// Mirror context without importing the provider's internal hook (mock module)
const mockCtx = vi.hoisted(() => ({
  value: {
    status: "connected" as const,
    showIndicator: true,
    lastEvent: null,
    connect: () => {},
    disconnect: () => {},
  },
}));

vi.mock("@/lib/events/grace-events-context", () => ({
  useGraceEventsContext: () => mockCtx.value,
}));

describe("ConnectionIndicator", () => {
  beforeEach(() => {
    mockCtx.value = {
      status: "connected",
      showIndicator: true,
      lastEvent: null,
      connect: () => {},
      disconnect: () => {},
    };
  });

  it("hides when showIndicator is false", () => {
    mockCtx.value.showIndicator = false;
    const { container } = render(<ConnectionIndicator />);
    const btn = container.querySelector("button[aria-label]");
    expect(btn).toBeNull();
  });

  it("shows green (Live updates) when connected", () => {
    mockCtx.value = { ...mockCtx.value, status: "connected", showIndicator: true };
    render(<ConnectionIndicator />);
    expect(screen.getByRole("button", { name: /Live updates connected/i })).toBeTruthy();
  });

  it("shows Reconnecting when status is reconnecting", () => {
    mockCtx.value = { ...mockCtx.value, status: "reconnecting", showIndicator: true };
    render(<ConnectionIndicator />);
    expect(screen.getByRole("button", { name: /Reconnecting/i })).toBeTruthy();
  });

  it("shows click to retry when disconnected", () => {
    mockCtx.value = { ...mockCtx.value, status: "disconnected", showIndicator: true };
    render(<ConnectionIndicator />);
    const b = screen.getByRole("button", { name: /Disconnected/ });
    expect(b).toBeTruthy();
  });
});
