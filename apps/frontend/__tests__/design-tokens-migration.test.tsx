import fs from "node:fs";
import path from "node:path";
import React from "react";
import { render, screen, within } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Button } from "@/components/ui/button";

// Phase 8.0: UI sans moved from IBM Plex Sans to Inter; IBM Plex Mono stays
// for cryptographic material. Both exports are kept mocked so the layout can
// be swapped back without editing this mock again.
vi.mock("next/font/google", () => ({
  Inter: () => ({ variable: "__font_sans_variable" }),
  IBM_Plex_Sans: () => ({ variable: "__font_sans_variable" }),
  IBM_Plex_Mono: () => ({ variable: "__font_mono_variable" }),
}));

vi.mock("@/app/providers", () => ({
  Providers: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/projects",
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: { email: "operator@example.com" } }),
}));

vi.mock("@/components/project-workspace-provider", () => ({
  useProjectWorkspace: () => ({
    projects: [],
    projectsLoading: false,
    activeProjectId: null,
    activeProject: null,
    setActiveProjectId: vi.fn(),
  }),
}));

vi.mock("@/lib/api", () => ({
  apiLogout: vi.fn(),
  apiMe: vi.fn(),
}));

vi.mock("@/components/command-center/connection-indicator", () => ({
  ConnectionIndicator: () => <div data-testid="connection-indicator" />,
}));

afterEach(() => {
  document.head.innerHTML = "";
  document.body.innerHTML = "";
});

describe("Phase 7.7.0 design tokens migration", () => {
  it("applies the sans + mono font variables to the root layout html", async () => {
    const { default: RootLayout } = await import("@/app/layout");

    const html = renderToStaticMarkup(
      <RootLayout>
        <main>AXIOM</main>
      </RootLayout>,
    );

    expect(html).toContain("__font_sans_variable");
    expect(html).toContain("__font_mono_variable");
  });

  // Phase 8.3: primary actions use the violet --primary token in both themes.
  it("renders primary buttons with the primary token background", () => {
    render(<Button variant="primary">Create project</Button>);

    const className = screen.getByRole("button", { name: /create project/i }).className;
    expect(className).toContain("bg-primary");
    expect(className).toContain("text-primary-foreground");
  });

  it("marks the active sidebar item with aria-current and the accent tokens", async () => {
    const { AppShell } = await import("@/components/shell/app-shell");

    render(<AppShell>content</AppShell>);

    const nav = screen.getByRole("navigation", { name: "Main" });
    const active = within(nav).getByRole("link", { name: /^projects$/i });
    expect(active.getAttribute("aria-current")).toBe("page");
    expect(active.className).toContain("bg-accent");
    expect(within(nav).getByRole("link", { name: /^receipts$/i }).getAttribute("aria-current")).toBeNull();
  });

  it("defines live-dot as the live-breath animation", () => {
    const css = fs.readFileSync(path.join(process.cwd(), "app/globals.css"), "utf8");
    expect(css).toContain("@keyframes live-breath");
    expect(css).toContain("animation: live-breath 2s ease-in-out infinite");

    const style = document.createElement("style");
    style.textContent = ".live-dot { animation-name: live-breath; animation-duration: 2s; }";
    document.head.append(style);

    const dot = document.createElement("span");
    dot.className = "live-dot";
    document.body.append(dot);

    expect(getComputedStyle(dot).animationName).toBe("live-breath");
  });
});
