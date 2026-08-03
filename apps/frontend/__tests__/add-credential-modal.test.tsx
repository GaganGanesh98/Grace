import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AddCredentialModal } from "@/components/vault/add-credential-modal";
import { createVaultKey, detectCredential } from "@/lib/vault-api";

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("@/lib/vault-api", () => ({
  createVaultKey: vi.fn(),
  detectCredential: vi.fn(),
}));

const createdKey = {
  id: "11111111-1111-4111-8111-111111111111",
  user_id: "user-1",
  service: "anthropic",
  name: "anthropic-prod",
  kind: "llm" as const,
  key_prefix: "sk-ant-",
  key_suffix: "12345",
  is_active: true,
  created_at: "2026-05-04T00:00:00Z",
  updated_at: "2026-05-04T00:00:00Z",
};

describe("AddCredentialModal", () => {
  beforeEach(() => {
    vi.mocked(detectCredential).mockResolvedValue({ service: "anthropic", kind: "llm" });
    vi.mocked(createVaultKey).mockResolvedValue(createdKey);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("blocks invalid credential names", () => {
    render(<AddCredentialModal open onClose={vi.fn()} />);

    const input = screen.getByLabelText("NAME") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "Bad Name" } });

    expect(input.value).toBe("");
    expect(screen.getByText("Name can only contain lowercase letters, numbers, and dashes")).toBeTruthy();
  });

  it("debounces credential detection after paste", async () => {
    render(<AddCredentialModal open onClose={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("CREDENTIAL"), { target: { value: "sk-ant-test12345" } });

    await waitFor(() => {
      expect(detectCredential).toHaveBeenCalledWith("sk-ant-test12345");
      expect(screen.getByText("anthropic")).toBeTruthy();
      expect(screen.getByText("(LLM)")).toBeTruthy();
    });
  });

  it("expands manual overrides from the detection chip", async () => {
    render(<AddCredentialModal open onClose={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("CREDENTIAL"), { target: { value: "sk-ant-test12345" } });
    await screen.findByText("change");

    fireEvent.click(screen.getByText("change"));

    expect(screen.getByLabelText("SERVICE")).toBeTruthy();
    expect(screen.getByText("KIND")).toBeTruthy();
  });

  it("submits createVaultKey with overrides", async () => {
    const onClose = vi.fn();
    const onCreated = vi.fn();
    render(<AddCredentialModal open onClose={onClose} onCreated={onCreated} />);

    fireEvent.change(screen.getByLabelText("NAME"), { target: { value: "anthropic-prod" } });
    fireEvent.change(screen.getByLabelText("CREDENTIAL"), { target: { value: "sk-ant-test12345" } });
    await screen.findByText("change");
    fireEvent.click(screen.getByText("change"));
    fireEvent.change(screen.getByLabelText("SERVICE"), { target: { value: "anthropic" } });
    fireEvent.click(screen.getByRole("button", { name: /llm/i }));

    fireEvent.click(screen.getByRole("button", { name: /^add credential$/i }));

    await waitFor(() => {
      expect(createVaultKey).toHaveBeenCalledWith({
        name: "anthropic-prod",
        raw_key: "sk-ant-test12345",
        service_override: "anthropic",
        kind_override: "llm",
      });
      expect(onCreated).toHaveBeenCalledWith(createdKey);
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });
});
