import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { listReceiptsMock, getReceiptMock } = vi.hoisted(() => ({
  listReceiptsMock: vi.fn(),
  getReceiptMock: vi.fn(),
}));

vi.mock("@/lib/receipts-api", () => ({
  listReceipts: (...a: unknown[]) => listReceiptsMock(...a),
  getReceipt: (...a: unknown[]) => getReceiptMock(...a),
  verifyReceipt: vi.fn(),
}));

vi.mock("@/components/project-workspace-provider", () => ({
  useProjectWorkspace: () => ({
    projects: [
      { id: "p1", name: "Project One", created_at: "2026-01-01T00:00:00Z" },
      { id: "p2", name: "Project Two", created_at: "2026-01-02T00:00:00Z" },
    ],
    projectsLoading: false,
    projectsError: null,
    activeProjectId: "p1",
    activeProject: { id: "p1", name: "Project One", created_at: "2026-01-01T00:00:00Z" },
    setActiveProjectId: vi.fn(),
    refreshProjects: vi.fn(),
    keysByProject: {},
    keysLoading: false,
    activeProjectKeysLoading: false,
    invalidateProjectKeys: vi.fn(),
    governanceKeyEpoch: 0,
    bumpGovernanceKeyEpoch: vi.fn(),
    projectsListTotal: 2,
  }),
}));

import ReceiptsPage from "@/app/dashboard/receipts/page";
import type { ReceiptDetail } from "@/lib/receipts-api";

function minimalDetail(): ReceiptDetail {
  return {
    id: "e93da4dd-1788-4dd9-b888-a91bdecfd85b",
    project_id: "p1",
    status: "sealed",
    verdict: "AUTHORIZED",
    action_type: "tool.llm.openai",
    upstream_provider: "openai",
    upstream_model: "gpt-4o",
    upstream_status: 200,
    total_tokens: 176,
    sealed_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    upstream_latency_ms: 650,
    receipt_hash_hex: "aa".repeat(32),
    ed25519_sig_hex: "bb".repeat(64),
    ml_dsa_sig_hex: "cc".repeat(200),
    merkle_leaf_hex: "aa".repeat(32),
    merkle_root_hex: "dd".repeat(32),
    merkle_proof: [],
    key_id: "k",
    target: "https://api.openai.com/v1/chat/completions",
    http_status: 200,
    request_hash_hex: "ee".repeat(32),
    response_hash_hex: "ff".repeat(32),
    vault_key_id: "v",
    approval_status: null,
    approved_by_user_id: null,
    approved_by_email: null,
    approved_at: null,
    approval_reason: null,
    intent_created_at: new Date().toISOString(),
    executed_at_label: null,
    token_usage: null,
  };
}

function renderPage(): ReturnType<typeof render> {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ReceiptsPage />
    </QueryClientProvider>,
  );
}

describe("ReceiptsPage", () => {
  it("renders empty state when there are no receipts", async () => {
    listReceiptsMock.mockResolvedValue({ items: [], total: 0 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("No receipts yet")).toBeTruthy();
    });
    const link = screen.getByRole("link", { name: /create an agent/i });
    expect(link.getAttribute("href")).toBe("/dashboard/projects");
  });

  it("renders table when data exists", async () => {
    listReceiptsMock.mockResolvedValue({
      items: [
        {
          id: "e93da4dd-1788-4dd9-b888-a91bdecfd85b",
          project_id: "p1",
          status: "sealed",
          verdict: "AUTHORIZED",
          action_type: "tool.llm.openai",
          upstream_provider: "openai",
          upstream_model: "gpt-4o",
          upstream_status: 200,
          total_tokens: 176,
          sealed_at: new Date().toISOString(),
          created_at: new Date().toISOString(),
          upstream_latency_ms: 650,
        },
      ],
      total: 1,
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole("table", { name: /governance receipts/i })).toBeTruthy();
    });
    expect(screen.getByText(/tool\.llm\.openai/)).toBeTruthy();
    expect(screen.getByText("gpt-4o")).toBeTruthy();
    expect(screen.getByText("176")).toBeTruthy();
  });

  it("opens drawer on row click", async () => {
    listReceiptsMock.mockResolvedValue({
      items: [
        {
          id: "e93da4dd-1788-4dd9-b888-a91bdecfd85b",
          project_id: "p1",
          status: "sealed",
          verdict: "AUTHORIZED",
          action_type: "tool.llm.openai",
          upstream_provider: "openai",
          upstream_model: "gpt-4o",
          upstream_status: 200,
          total_tokens: 176,
          sealed_at: new Date().toISOString(),
          created_at: new Date().toISOString(),
          upstream_latency_ms: 650,
        },
      ],
      total: 1,
    });
    getReceiptMock.mockResolvedValue(minimalDetail());
    renderPage();
    await waitFor(() => {
      expect(document.querySelector("[data-receipt-row]")).toBeTruthy();
    });
    fireEvent.click(document.querySelector("[data-receipt-row]")!);
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeTruthy();
    });
  });

  it("applies verdict filter for DENIED", async () => {
    listReceiptsMock.mockResolvedValue({
      items: [
        {
          id: "a1111111-1111-4111-8111-111111111111",
          project_id: "p1",
          status: "sealed",
          verdict: "AUTHORIZED",
          action_type: "x",
          upstream_provider: "",
          upstream_model: "",
          upstream_status: 200,
          total_tokens: null,
          sealed_at: null,
          created_at: new Date().toISOString(),
          upstream_latency_ms: 0,
        },
        {
          id: "b2222222-2222-4222-8222-222222222222",
          project_id: "p1",
          status: "sealed",
          verdict: "DENIED",
          action_type: "y",
          upstream_provider: "",
          upstream_model: "",
          upstream_status: 403,
          total_tokens: null,
          sealed_at: null,
          created_at: new Date().toISOString(),
          upstream_latency_ms: 0,
        },
      ],
      total: 2,
    });
    renderPage();
    await screen.findByText("y");
    fireEvent.click(screen.getByRole("button", { name: "DENIED" }));
    await waitFor(() => {
      expect(screen.queryByText("x")).toBeNull();
    });
    expect(screen.getByText("y")).toBeTruthy();
  });
});
