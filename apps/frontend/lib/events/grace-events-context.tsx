"use client";

import { createContext, useContext, useEffect, useState, type ReactElement, type ReactNode } from "react";

import { useProjectWorkspace } from "@/components/project-workspace-provider";

import { useGraceEvents } from "./use-grace-events";

import type { GraceEvent, GraceEventsStatus } from "./event-types";

type GraceEventsValue = {
  status: GraceEventsStatus;
  /** Muted (hidden) only during the first "connecting" after mount / project change. */
  showIndicator: boolean;
  lastEvent: GraceEvent | null;
  connect: () => void;
  disconnect: () => void;
};

const Ctx = createContext<GraceEventsValue | null>(null);

export function GraceEventsProvider({ children }: { children: ReactNode }): ReactElement {
  const { activeProjectId } = useProjectWorkspace();
  const { status, lastEvent, connect, disconnect } = useGraceEvents({ projectId: activeProjectId });
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

  const v: GraceEventsValue = {
    status: st,
    showIndicator,
    lastEvent,
    connect,
    disconnect,
  };

  return <Ctx.Provider value={v}>{children}</Ctx.Provider>;
}

export function useGraceEventsContext(): GraceEventsValue {
  const c = useContext(Ctx);
  if (!c) {
    throw new Error("useGraceEventsContext must be used within GraceEventsProvider");
  }
  return c;
}
