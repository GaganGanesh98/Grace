"use client";

import { createContext, useContext, useEffect, useState, type ReactElement, type ReactNode } from "react";

import { useProjectWorkspace } from "@/components/project-workspace-provider";

import { useAxiomEvents } from "./use-axiom-events";

import type { AxiomEvent, AxiomEventsStatus } from "./event-types";

type AxiomEventsValue = {
  status: AxiomEventsStatus;
  /** Muted (hidden) only during the first "connecting" after mount / project change. */
  showIndicator: boolean;
  lastEvent: AxiomEvent | null;
  connect: () => void;
  disconnect: () => void;
};

const Ctx = createContext<AxiomEventsValue | null>(null);

export function AxiomEventsProvider({ children }: { children: ReactNode }): ReactElement {
  const { activeProjectId } = useProjectWorkspace();
  const { status, lastEvent, connect, disconnect } = useAxiomEvents({ projectId: activeProjectId });
  const [leftInitial, setLeftInitial] = useState(false);

  useEffect(() => {
    setLeftInitial(false);
  }, [activeProjectId]);

  useEffect(() => {
    if (status !== "connecting") {
      setLeftInitial(true);
    }
  }, [status]);

  const hasProject = Boolean(activeProjectId);
  const st = hasProject ? status : "disconnected";
  const showIndicator = hasProject && (leftInitial || st !== "connecting");

  const v: AxiomEventsValue = {
    status: st,
    showIndicator,
    lastEvent,
    connect,
    disconnect,
  };

  return <Ctx.Provider value={v}>{children}</Ctx.Provider>;
}

export function useAxiomEventsContext(): AxiomEventsValue {
  const c = useContext(Ctx);
  if (!c) {
    throw new Error("useAxiomEventsContext must be used within AxiomEventsProvider");
  }
  return c;
}
