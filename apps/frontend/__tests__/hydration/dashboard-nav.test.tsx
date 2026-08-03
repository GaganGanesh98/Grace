import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";

import { AxiomEventsProvider } from "@/lib/events/axiom-events-context";
import {
  ProjectWorkspaceProvider,
  useProjectWorkspace,
} from "@/components/project-workspace-provider";
import { Sidebar } from "@/components/sidebar";

vi.mock("next/navigation", () => ({
  usePathname: (): string => "/dashboard",
  useRouter: (): { push: ReturnType<typeof vi.fn> } => ({ push: vi.fn() }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const mod = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...mod,
    apiListProjects: vi.fn().mockResolvedValue({
      data: [],
      meta: { total: 0, page: 1, per_page: 20, has_more: false },
    }),
    apiMe: vi.fn().mockResolvedValue({
      id: "u1",
      email: "t@example.com",
      full_name: null,
      avatar_url: null,
      email_verified_at: null,
      last_login_at: null,
      is_active: true,
    }),
  };
});

function shell(): ReactElement {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={qc}>
      <ProjectWorkspaceProvider>
        <AxiomEventsProvider>
          <Sidebar />
        </AxiomEventsProvider>
      </ProjectWorkspaceProvider>
    </QueryClientProvider>
  );
}

describe("dashboard nav hydration", () => {
  it("server HTML matches between two renderToString passes (stable sidebar markup)", () => {
    const a = renderToString(shell());
    const b = renderToString(shell());
    expect(a).toBe(b);
  });

  it("ProjectWorkspaceProvider first paint has null active project (matches SSR)", () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    function Probe(): ReactElement {
      const { activeProjectId } = useProjectWorkspace();
      return <span data-testid="apid">{activeProjectId === null ? "null" : activeProjectId}</span>;
    }
    render(
      <QueryClientProvider client={qc}>
        <ProjectWorkspaceProvider>
          <Probe />
        </ProjectWorkspaceProvider>
      </QueryClientProvider>,
    );
    expect(screen.getByTestId("apid").textContent).toBe("null");
  });
});
