import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

const getReceiptMock = vi.fn();
const verifyReceiptMock = vi.fn();

vi.mock("@/lib/receipts-api", () => ({
  getReceipt: (...a: unknown[]) => getReceiptMock(...a),
  verifyReceipt: (...a: unknown[]) => verifyReceiptMock(...a),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { GovernanceReceiptDrawer } from "@/components/receipts/receipt-drawer";
import type { ReceiptDetail } from "@/lib/receipts-api";

beforeAll(() => {
  Object.defineProperty(globalThis.navigator, "clipboard", {
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
    configurable: true,
    writable: true,
  });
});

function makeDetail(overrides: Partial<ReceiptDetail> = {}): ReceiptDetail {
  const base: ReceiptDetail = {
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
    ml_dsa_sig_hex: "cc".repeat(100),
    merkle_leaf_hex: "aa".repeat(32),
    merkle_root_hex: "dd".repeat(32),
    merkle_proof: [],
    key_id: "test-key",
    target: "https://api.openai.com/v1/chat/completions",
    http_status: 200,
    request_hash_hex: "ee".repeat(32),
    response_hash_hex: "ff".repeat(32),
    vault_key_id: "vault-1",
    approval_status: null,
    approved_by_user_id: null,
    approved_by_email: null,
    approved_at: null,
    approval_reason: null,
    intent_created_at: new Date().toISOString(),
    executed_at_label: null,
    token_usage: { prompt_tokens: 10, completion_tokens: 166, total_tokens: 176 },
  };
  return { ...base, ...overrides };
}

describe("GovernanceReceiptDrawer", () => {
  it("renders sections when detail loads", async () => {
    getReceiptMock.mockResolvedValue(makeDetail());
    render(
      <GovernanceReceiptDrawer receiptId="e93da4dd-1788-4dd9-b888-a91bdecfd85b" projectId="p1" onClose={vi.fn()} />,
    );
    await waitFor(() => {
      expect(screen.getByText("ACTION")).toBeTruthy();
    });
    expect(screen.getByText("CRYPTOGRAPHIC PROOF")).toBeTruthy();
    expect(screen.getByText("REQUEST/RESPONSE HASHES")).toBeTruthy();
    expect(screen.getByText("TIMESTAMPS")).toBeTruthy();
  });

  it("expand toggles long hex visibility", async () => {
    const longHex = "ab".repeat(80);
    getReceiptMock.mockResolvedValue(
      makeDetail({
        receipt_hash_hex: "00",
        ed25519_sig_hex: "01",
        ml_dsa_sig_hex: longHex,
        merkle_leaf_hex: "02",
        merkle_root_hex: null,
        request_hash_hex: "03",
        response_hash_hex: "04",
      }),
    );
    render(
      <GovernanceReceiptDrawer receiptId="e93da4dd-1788-4dd9-b888-a91bdecfd85b" projectId="p1" onClose={vi.fn()} />,
    );
    await screen.findByText("ML-DSA-65 signature");
    const expand = await screen.findByRole("button", { name: "Expand" });
    fireEvent.click(expand);
    expect(screen.getByRole("button", { name: "Collapse" })).toBeTruthy();
  });

  it("copy triggers clipboard and toast", async () => {
    const write = navigator.clipboard.writeText as ReturnType<typeof vi.fn>;
    getReceiptMock.mockResolvedValue(makeDetail());
    render(
      <GovernanceReceiptDrawer receiptId="e93da4dd-1788-4dd9-b888-a91bdecfd85b" projectId="p1" onClose={vi.fn()} />,
    );
    await screen.findByText("Receipt hash (SHA-256)");
    const copyBtn = screen.getByRole("button", { name: /Copy Receipt hash/i });
    fireEvent.click(copyBtn);
    await waitFor(() => {
      expect(write).toHaveBeenCalled();
    });
  });

  it("verify button calls API and renders result", async () => {
    getReceiptMock.mockResolvedValue(makeDetail());
    verifyReceiptMock.mockResolvedValue({
      valid: true,
      ed25519_valid: true,
      ml_dsa_valid: true,
      merkle_valid: true,
      errors: [],
    });
    render(
      <GovernanceReceiptDrawer receiptId="e93da4dd-1788-4dd9-b888-a91bdecfd85b" projectId="p1" onClose={vi.fn()} />,
    );
    await screen.findByRole("button", { name: "Verify signatures" });
    fireEvent.click(screen.getByRole("button", { name: "Verify signatures" }));
    await waitFor(() => {
      expect(verifyReceiptMock).toHaveBeenCalledWith("e93da4dd-1788-4dd9-b888-a91bdecfd85b", "p1");
    });
    await waitFor(() => {
      expect(screen.getByText("All signatures valid")).toBeTruthy();
    });
  });

  it("renders approval section when approval_status set", async () => {
    getReceiptMock.mockResolvedValue(
      makeDetail({
        approval_status: "approved",
        approved_by_email: "ops@example.com",
        approved_at: "2026-05-01T12:00:00Z",
        approval_reason: "ok",
      }),
    );
    render(
      <GovernanceReceiptDrawer receiptId="e93da4dd-1788-4dd9-b888-a91bdecfd85b" projectId="p1" onClose={vi.fn()} />,
    );
    await waitFor(() => {
      expect(screen.getByText("APPROVAL")).toBeTruthy();
    });
    expect(screen.getByText(/ops@example\.com/)).toBeTruthy();
  });
});
