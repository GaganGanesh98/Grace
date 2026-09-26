import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AgentCreatePanel } from "@/components/agent-definitions/agent-create-panel";
import type { VaultKey } from "@/lib/vault-api";

const key = (over: Partial<VaultKey> = {}): VaultKey => ({
  id: "44444444-4444-7444-8444-444444444444",
  user_id: "55555555-5555-7555-8555-555555555555",
  service: "groq",
  name: "groq-prod",
  kind: "llm",
  key_prefix: "gsk_",
  key_suffix: "9f2a",
  is_active: true,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  ...over,
});

const baseProps = {
  vaultLoading: false,
  vaultError: null,
  onSubmit: vi.fn(),
  isSubmitting: false,
  submitError: null,
  onCredentialCreated: vi.fn(),
};

describe("AgentCreatePanel", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows the credential step instead of an unsubmittable form when the vault is empty", () => {
    render(<AgentCreatePanel {...baseProps} vaultKeys={[]} />);

    expect(screen.getByTestId("agent-credential-required")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /create agent/i })).toBeNull();
    expect(screen.getByRole("button", { name: /\+ add credential/i })).toBeTruthy();
    expect(screen.getByRole("link", { name: /open vault/i }).getAttribute("href")).toBe(
      "/dashboard/vault",
    );
  });

  it("treats an LLM key of an unsupported service as no usable credential", () => {
    render(<AgentCreatePanel {...baseProps} vaultKeys={[key({ service: "replicate" })]} />);

    expect(screen.getByTestId("agent-credential-required")).toBeTruthy();
  });

  it("opens the credential dialog in place, keeping typed input", async () => {
    render(<AgentCreatePanel {...baseProps} vaultKeys={[key()]} />);

    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: "researcher" } });
    fireEvent.change(screen.getByLabelText(/system prompt/i), {
      target: { value: "You verify claims." },
    });

    fireEvent.click(screen.getByRole("button", { name: /\+ add credential/i }));
    expect(await screen.findByRole("dialog")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /^close$/i }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });

    expect((screen.getByLabelText(/^name$/i) as HTMLInputElement).value).toBe("researcher");
    expect((screen.getByLabelText(/system prompt/i) as HTMLTextAreaElement).value).toBe(
      "You verify claims.",
    );
  });
});
