import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import LoginPage from "@/app/login/page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    refresh: vi.fn(),
  }),
}));

vi.mock("@/lib/api", () => ({
  apiLogin: vi.fn(),
  startGoogleOAuth: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe("LoginPage", () => {
  it("renders V1b chrome, form fields, actions, and live indicator", () => {
    render(<LoginPage />);

    expect(screen.getByText("GRACE")).toBeTruthy();
    expect(screen.getByText("V0.2.4")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Resume session." })).toBeTruthy();
    expect(screen.getByText("VERIFICATION LAYER · AUTONOMOUS SYSTEMS")).toBeTruthy();

    expect(screen.getByRole("textbox", { name: "EMAIL" })).toBeTruthy();
    expect(screen.getByLabelText("PASSWORD")).toBeTruthy();

    expect(screen.getByRole("button", { name: "CONTINUE →" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Continue with Google/i })).toBeTruthy();

    expect(screen.getByText("LIVE · NETWORK VERIFIED")).toBeTruthy();
  });
});
