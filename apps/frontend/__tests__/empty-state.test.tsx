import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { VaultEmptyState } from "@/components/vault/empty-state";

describe("VaultEmptyState", () => {
  it("renders icon, heading, description, and add button", () => {
    const onAddCredential = vi.fn();

    render(<VaultEmptyState onAddCredential={onAddCredential} />);

    expect(screen.getByRole("heading", { name: "No credentials yet" })).toBeTruthy();
    expect(screen.getByText(/Add an LLM provider key or tool credential/i)).toBeTruthy();
    const button = screen.getByRole("button", { name: /add credential/i });
    expect(button).toBeTruthy();

    fireEvent.click(button);
    expect(onAddCredential).toHaveBeenCalledTimes(1);
  });
});
