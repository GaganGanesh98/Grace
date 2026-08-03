import { render, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GoogleCallbackInner } from "@/app/auth/callback/google/google-callback-inner";

const replace = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace,
    refresh,
  }),
  useSearchParams: () => new URLSearchParams("code=test-code&state=test-state"),
}));

describe("GoogleCallbackInner", () => {
  beforeEach(() => {
    replace.mockClear();
    refresh.mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls fetch exactly once when Strict Mode double-invokes useEffect", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: { status: "ok" } }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    render(
      <StrictMode>
        <GoogleCallbackInner />
      </StrictMode>,
    );

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledTimes(1);
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/auth/google/callback",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: "test-code", state: "test-state" }),
      }),
    );
  });
});
