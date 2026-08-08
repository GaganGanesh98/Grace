import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AgentForm } from "@/components/agent-definitions/agent-form";
import type { LlmProvider } from "@/lib/providers-api";
import type { VaultKey } from "@/lib/vault-api";

const PROVIDERS: LlmProvider[] = [
  {
    service: "groq",
    label: "Groq",
    protocol: "openai_compatible",
    models: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
    default_model: "llama-3.3-70b-versatile",
  },
  {
    service: "anthropic",
    label: "Anthropic",
    protocol: "anthropic_messages",
    models: ["claude-sonnet-5", "claude-haiku-4-5"],
    default_model: "claude-sonnet-5",
  },
];

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

/** Name is always free text; Model is only free text when the catalog has no entry. */
function fillRequiredFields(): void {
  fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: "researcher" } });
  const model = screen.getByLabelText(/^model$/i);
  if (model.tagName === "INPUT") {
    fireEvent.change(model, { target: { value: "llama-3.3-70b-versatile" } });
  }
}

describe("AgentForm", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("disables submit and explains why when the vault is empty", () => {
    render(<AgentForm vaultKeys={[]} onSubmit={vi.fn()} isSubmitting={false} submitError={null} />);

    const button = screen.getByRole("button", { name: /create agent/i });
    expect((button as HTMLButtonElement).disabled).toBe(true);

    const describedBy = button.getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();
    expect(document.getElementById(describedBy!)?.textContent).toMatch(/no llm credentials in vault/i);
    expect(button.getAttribute("title")).toMatch(/credential/i);
  });

  it("renders a placeholder option when the vault key list is empty", () => {
    render(<AgentForm vaultKeys={[]} onSubmit={vi.fn()} isSubmitting={false} submitError={null} />);

    const select = screen.getByLabelText(/vault key/i) as HTMLSelectElement;
    expect(select.options.length).toBe(1);
    expect(select.options[0].value).toBe("");
    expect(select.disabled).toBe(true);
  });

  it("shows a field error and makes no network call for an unsupported service", async () => {
    const onSubmit = vi.fn();
    render(
      <AgentForm
        vaultKeys={[key({ service: "tavily", name: "tavily-search" })]}
        onSubmit={onSubmit}
        isSubmitting={false}
        submitError={null}
      />,
    );

    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: /create agent/i }));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("tavily");
    expect(alert.textContent).toContain("OpenAI, Anthropic, Google, Groq, or xAI");
    expect(onSubmit).not.toHaveBeenCalled();
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it("submits once with the expected payload for a supported key", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <AgentForm
        vaultKeys={[key()]}
        providers={PROVIDERS}
        onSubmit={onSubmit}
        isSubmitting={false}
        submitError={null}
      />,
    );

    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: /create agent/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      name: "researcher",
      vault_key_id: "44444444-4444-7444-8444-444444444444",
      model: "groq/llama-3.3-70b-versatile",
    });
  });

  it("offers the selected provider's models plus a free-text escape hatch", async () => {
    render(
      <AgentForm
        vaultKeys={[key()]}
        providers={PROVIDERS}
        onSubmit={vi.fn()}
        isSubmitting={false}
        submitError={null}
      />,
    );

    const select = (await screen.findByLabelText(/^model$/i)) as HTMLSelectElement;
    expect(Array.from(select.options).map((o) => o.value)).toEqual([
      "groq/llama-3.3-70b-versatile",
      "groq/llama-3.1-8b-instant",
      "__custom__",
    ]);
    expect(screen.queryByLabelText(/custom model id/i)).toBeNull();

    fireEvent.change(select, { target: { value: "__custom__" } });
    expect(await screen.findByLabelText(/custom model id/i)).toBeTruthy();
  });

  it("resets the model to the new provider's default when the credential changes", async () => {
    render(
      <AgentForm
        vaultKeys={[
          key(),
          key({ id: "22222222-2222-7222-8222-222222222222", service: "anthropic", name: "claude" }),
        ]}
        providers={PROVIDERS}
        onSubmit={vi.fn()}
        isSubmitting={false}
        submitError={null}
      />,
    );

    await waitFor(() => {
      expect((screen.getByLabelText(/^model$/i) as HTMLSelectElement).value).toBe(
        "groq/llama-3.3-70b-versatile",
      );
    });

    fireEvent.change(screen.getByLabelText(/vault key/i), {
      target: { value: "22222222-2222-7222-8222-222222222222" },
    });

    await waitFor(() => {
      expect((screen.getByLabelText(/^model$/i) as HTMLSelectElement).value).toBe(
        "anthropic/claude-sonnet-5",
      );
    });
  });

  it("blocks a custom model whose provider prefix contradicts the credential", async () => {
    const onSubmit = vi.fn();
    render(
      <AgentForm
        vaultKeys={[key()]}
        providers={PROVIDERS}
        onSubmit={onSubmit}
        isSubmitting={false}
        submitError={null}
      />,
    );

    fillRequiredFields();
    fireEvent.change(await screen.findByLabelText(/^model$/i), {
      target: { value: "__custom__" },
    });
    fireEvent.change(await screen.findByLabelText(/custom model id/i), {
      target: { value: "openai/gpt-4o" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create agent/i }));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("openai");
    expect(alert.textContent).toContain("groq");
    expect(onSubmit).not.toHaveBeenCalled();
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it("falls back to free-text model entry when the catalog has no entry", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <AgentForm
        vaultKeys={[key({ service: "xai", name: "grok" })]}
        providers={PROVIDERS}
        onSubmit={onSubmit}
        isSubmitting={false}
        submitError={null}
      />,
    );

    fillRequiredFields();
    const model = screen.getByLabelText(/^model$/i) as HTMLInputElement;
    expect(model.tagName).toBe("INPUT");
    fireEvent.change(model, { target: { value: "xai/grok-4" } });
    fireEvent.click(screen.getByRole("button", { name: /create agent/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });
    expect(onSubmit.mock.calls[0][0]).toMatchObject({ model: "xai/grok-4" });
  });

  it("defaults the selection to the first supported key", async () => {
    render(
      <AgentForm
        vaultKeys={[
          key({ id: "11111111-1111-7111-8111-111111111111", service: "tavily", name: "tool-key" }),
          key({ id: "22222222-2222-7222-8222-222222222222", service: "anthropic", name: "claude" }),
        ]}
        onSubmit={vi.fn()}
        isSubmitting={false}
        submitError={null}
      />,
    );

    const select = screen.getByLabelText(/vault key/i) as HTMLSelectElement;
    await waitFor(() => {
      expect(select.value).toBe("22222222-2222-7222-8222-222222222222");
    });
  });
});
