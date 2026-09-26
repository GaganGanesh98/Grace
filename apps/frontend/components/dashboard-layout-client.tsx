"use client";

import type { ReactElement, ReactNode } from "react";

import { FontScaleProvider } from "@/components/font-scale-provider";
import { GraceEventsProvider } from "@/lib/events/grace-events-context";
import { ProjectWorkspaceProvider } from "@/components/project-workspace-provider";
import { AppShell } from "@/components/shell/app-shell";

export function DashboardLayoutClient({ children }: { children: ReactNode }): ReactElement {
  return (
    <FontScaleProvider>
      <ProjectWorkspaceProvider>
        <GraceEventsProvider>
          <div data-axiom-dashboard className="min-w-0 max-w-full overflow-x-clip">
            <AppShell>{children}</AppShell>
          </div>
        </GraceEventsProvider>
      </ProjectWorkspaceProvider>
    </FontScaleProvider>
  );
}
