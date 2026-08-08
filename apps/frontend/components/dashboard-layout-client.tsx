"use client";

import type { ReactElement, ReactNode } from "react";

import { FontScaleProvider } from "@/components/font-scale-provider";
import { GraceEventsProvider } from "@/lib/events/grace-events-context";
import { ProjectWorkspaceProvider } from "@/components/project-workspace-provider";
import { Sidebar } from "@/components/sidebar";

export function DashboardLayoutClient({ children }: { children: ReactNode }): ReactElement {
  return (
    <FontScaleProvider>
      <ProjectWorkspaceProvider>
        <GraceEventsProvider>
          <div
            data-axiom-dashboard
            className="flex min-h-screen min-w-0 max-w-full overflow-x-hidden bg-[var(--axiom-bg)] font-[family-name:var(--font-sans)] text-[var(--axiom-text)]"
          >
            <Sidebar />
            <main className="min-w-0 flex-1 overflow-x-hidden overflow-y-auto px-4 py-6 sm:px-6 md:px-8 md:py-7">
              <div className="mx-auto max-w-[min(100%,1400px)] pt-10 md:pt-0">{children}</div>
            </main>
          </div>
        </GraceEventsProvider>
      </ProjectWorkspaceProvider>
    </FontScaleProvider>
  );
}
