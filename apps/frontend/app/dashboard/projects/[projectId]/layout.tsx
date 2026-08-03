import { Suspense, type ReactElement, type ReactNode } from "react";

import { ProjectWorkspaceShell } from "@/components/project-workspace/project-workspace-shell";
import { ProjectIdProvider } from "@/lib/projects/project-id-context";

function WorkspaceTabSuspenseFallback(): ReactElement {
  return (
    <div
      className="min-h-[32vh] animate-pulse rounded-lg border border-[var(--axiom-border)] bg-[var(--axiom-bg-card)]"
      role="status"
      aria-label="Loading tab"
    />
  );
}

export default async function ProjectWorkspaceLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ projectId: string }>;
}): Promise<ReactElement> {
  const { projectId } = await params;
  return (
    <ProjectIdProvider projectId={projectId}>
      <ProjectWorkspaceShell>
        <Suspense fallback={<WorkspaceTabSuspenseFallback />}>{children}</Suspense>
      </ProjectWorkspaceShell>
    </ProjectIdProvider>
  );
}
