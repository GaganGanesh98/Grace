"use client";

import { createContext, useContext, type ReactElement, type ReactNode } from "react";

const ProjectIdContext = createContext<string | null>(null);

export function ProjectIdProvider({
  projectId,
  children,
}: {
  projectId: string;
  children: ReactNode;
}): ReactElement {
  return <ProjectIdContext.Provider value={projectId}>{children}</ProjectIdContext.Provider>;
}

export function useProjectIdFromLayout(): string {
  const v = useContext(ProjectIdContext);
  if (!v) {
    throw new Error("useProjectIdFromLayout must be used under ProjectIdProvider");
  }
  return v;
}
