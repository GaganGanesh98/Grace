import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AgentList } from "@/components/agent-definitions/agent-list";
import type { AgentDefinitionOut } from "@/lib/types";

const def = (over: Partial<AgentDefinitionOut> = {}): AgentDefinitionOut => ({
  id: "11111111-1111-7111-8111-111111111111",
  project_id: "22222222-2222-7222-8222-222222222222",
  agent_id: "33333333-3333-7333-8333-333333333333",
  name: "agent1",
  description: null,
  system_prompt: null,
  model: "groq/x",
  vault_key_id: "44444444-4444-7444-8444-444444444444",
  tools_config: {},
  max_iterations: 10,
  max_tokens_per_run: 1000,
  is_archived: false,
  created_by: "55555555-5555-7555-8555-555555555555",
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  ...over,
});

describe("AgentList", () => {
  it("wraps each row in a link to the detail page", () => {
    render(
      <AgentList
        projectId="proj-a"
        definitions={[def()]}
        onArchive={vi.fn()}
        archivingId={null}
      />,
    );
    const link = screen.getByRole("link", { name: "agent1" });
    expect(link.getAttribute("href")).toBe(
      "/dashboard/projects/proj-a/agent-definitions/11111111-1111-7111-8111-111111111111",
    );
  });

  it("archive does not navigate; calls handler", () => {
    const onArchive = vi.fn();
    render(
      <AgentList projectId="proj-a" definitions={[def()]} onArchive={onArchive} archivingId={null} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Archive" }));
    expect(onArchive).toHaveBeenCalledWith("11111111-1111-7111-8111-111111111111");
  });
});
