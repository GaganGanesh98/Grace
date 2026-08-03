import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DashboardVaultIndexPage from "@/app/dashboard/vault/page";
import { listVaultKeys } from "@/lib/vault-api";

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("@/lib/vault-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/vault-api")>("@/lib/vault-api");
  return {
    ...actual,
    listVaultKeys: vi.fn(),
    deactivateVaultKey: vi.fn(),
    deleteVaultKey: vi.fn(),
    createVaultKey: vi.fn(),
    detectCredential: vi.fn(),
  };
});

const vaultKey = {
  id: "11111111-1111-4111-8111-111111111111",
  user_id: "user-1",
  service: "anthropic",
  name: "anthropic-prod",
  kind: "llm" as const,
  key_prefix: "sk-ant-",
  key_suffix: "12345",
  is_active: true,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

describe("DashboardVaultIndexPage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the empty state when the vault list is empty", async () => {
    vi.mocked(listVaultKeys).mockResolvedValue([]);

    render(<DashboardVaultIndexPage />);

    await waitFor(() => expect(screen.getByRole("heading", { name: "No credentials yet" })).toBeTruthy());
    expect(screen.getByText(/Add an LLM provider key or tool credential/i)).toBeTruthy();
  });

  it("renders a table with vault rows", async () => {
    vi.mocked(listVaultKeys).mockResolvedValue([vaultKey]);

    render(<DashboardVaultIndexPage />);

    await waitFor(() => expect(screen.getByText("anthropic-prod")).toBeTruthy());
    expect(screen.getByText("LLM")).toBeTruthy();
    expect(screen.getByText("anthropic")).toBeTruthy();
    expect(screen.getByText("sk-ant-…12345")).toBeTruthy();
    expect(screen.getByRole("button", { name: /actions for anthropic-prod/i })).toBeTruthy();
  });

  it("opens the add credential modal from the page button", async () => {
    vi.mocked(listVaultKeys).mockResolvedValue([]);

    render(<DashboardVaultIndexPage />);

    await waitFor(() => expect(screen.getByRole("heading", { name: "Vault" })).toBeTruthy());
    fireEvent.click(screen.getAllByRole("button", { name: /add credential/i })[0]);

    expect(screen.getByRole("dialog", { name: "Add credential" })).toBeTruthy();
  });
});
