"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { dashboardKeys } from "@/lib/dashboard-query-keys";

import type { AxiomEvent, AxiomEventsStatus } from "./event-types";

const DEFAULT_WINDOWS = ["24h", "1h", "7d"] as const;

const NAMED = [
  "connected",
  "ping",
  "receipt.sealed",
  "approval.created",
  "approval.resolved",
  "run.started",
  "run.completed",
  "policy.activated",
] as const;

export function eventsBackoffMs(attempt: number): number {
  if (attempt >= 5) {
    return 30_000;
  }
  return 1000 * 2 ** attempt;
}

type Qk = readonly unknown[];

export function keysForType(type: string, projectId: string, w: readonly string[]): Qk[] {
  switch (type) {
    case "receipt.sealed":
      return [
        ...w.map((win) => dashboardKeys.commandCenterPosture(projectId, win)),
        dashboardKeys.commandCenterCryptoHealth(projectId),
        ...w.map((win) => dashboardKeys.commandCenterPolicyBreakdown(projectId, win)),
        dashboardKeys.commandCenterTsaStatus(projectId),
        dashboardKeys.governanceLedgerBundle(projectId),
        dashboardKeys.receiptsDetailed(projectId),
        dashboardKeys.projectHeader(projectId),
        dashboardKeys.projectMetrics(projectId),
      ];
    case "approval.created":
      return [
        ...w.map((win) => dashboardKeys.commandCenterPosture(projectId, win)),
        dashboardKeys.pendingApprovals(projectId),
        dashboardKeys.attentionStrip(projectId),
      ];
    case "approval.resolved":
      return [
        ...w.map((win) => dashboardKeys.commandCenterPosture(projectId, win)),
        ...w.map((win) => dashboardKeys.commandCenterPolicyBreakdown(projectId, win)),
        dashboardKeys.pendingApprovals(projectId),
        dashboardKeys.attentionStrip(projectId),
        dashboardKeys.receiptsDetailed(projectId),
      ];
    case "run.started":
      return [
        dashboardKeys.agentRuns(projectId),
        dashboardKeys.governanceLedgerBundle(projectId),
        dashboardKeys.recentProjectRuns(projectId),
        dashboardKeys.projectRunsListAll(projectId),
        dashboardKeys.projectMetrics(projectId),
        dashboardKeys.projectHeader(projectId),
      ];
    case "run.completed":
      return [
        dashboardKeys.agentRuns(projectId),
        ...w.map((win) => dashboardKeys.commandCenterPosture(projectId, win)),
        dashboardKeys.governanceLedgerBundle(projectId),
        dashboardKeys.recentProjectRuns(projectId),
        dashboardKeys.projectRunsListAll(projectId),
        dashboardKeys.projectMetrics(projectId),
        dashboardKeys.projectHeader(projectId),
        dashboardKeys.agentDefinitions(projectId),
        dashboardKeys.commandCenterAgentDefinitionsAll(projectId),
        dashboardKeys.agentDefinitionsNonArchivedCount(projectId),
      ];
    case "policy.activated":
      return [
        dashboardKeys.activePolicy(projectId),
        ...w.map((win) => dashboardKeys.commandCenterPolicyBreakdown(projectId, win)),
        dashboardKeys.projectPolicies(projectId),
        dashboardKeys.project(projectId),
      ];
    default:
      return [];
  }
}

function uniqueKeys(keys: Qk[]): Qk[] {
  const s = new Set<string>();
  const o: Qk[] = [];
  for (const k of keys) {
    const j = JSON.stringify(k);
    if (s.has(j)) {
      continue;
    }
    s.add(j);
    o.push(k);
  }
  return o;
}

export type UseAxiomEventsOptions = {
  projectId: string | null | undefined;
  onEvent?: (event: AxiomEvent) => void;
  windows?: readonly string[];
};

export function useAxiomEvents(options: UseAxiomEventsOptions): {
  status: AxiomEventsStatus;
  lastEvent: AxiomEvent | null;
  connect: () => void;
  disconnect: () => void;
} {
  const { projectId, onEvent, windows = DEFAULT_WINDOWS } = options;
  const queryClient = useQueryClient();
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const [lastEvent, setLastEvent] = useState<AxiomEvent | null>(null);
  const [status, setStatus] = useState<AxiomEventsStatus>(
    !projectId ? "disconnected" : "connecting",
  );
  const [userPaused, setUserPaused] = useState(false);
  const userPausedRef = useRef(false);
  userPausedRef.current = userPaused;

  useEffect(() => {
    if (!projectId) {
      setUserPaused(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (!projectId || userPaused) {
      setStatus("disconnected");
      return;
    }

    const attemptRef = { n: 0 };
    const hasOpenedRef = { v: false };
    let source: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const handlers: { ev: string; fn: (e: Event) => void }[] = [];
    let onErrorHandler: ((e: Event) => void) | null = null;

    const clearTimer = () => {
      if (timer != null) {
        clearTimeout(timer);
        timer = null;
      }
    };

    const removeAllListeners = (s: EventSource) => {
      if (onErrorHandler) {
        s.removeEventListener("error", onErrorHandler, false);
        onErrorHandler = null;
      }
      for (const h of handlers) {
        s.removeEventListener(h.ev, h.fn, false);
      }
      handlers.length = 0;
    };

    const scheduleReconnect = () => {
      if (userPausedRef.current) {
        return;
      }
      const d = eventsBackoffMs(attemptRef.n);
      attemptRef.n += 1;
      setStatus(hasOpenedRef.v ? "reconnecting" : "connecting");
      clearTimer();
      timer = setTimeout(attach, d);
    };

    const attach = () => {
      if (userPausedRef.current) {
        return;
      }
      if (!hasOpenedRef.v) {
        setStatus("connecting");
      } else {
        setStatus("reconnecting");
      }
      if (source) {
        try {
          removeAllListeners(source);
          source.close();
        } catch {
          /* ignore */
        }
        source = null;
      }
      const s = new EventSource(
        `/api/events/stream?project_id=${encodeURIComponent(projectId)}`,
      );
      source = s;

      const namedHandler = (name: string) => (ev: Event) => {
        const d = (ev as MessageEvent).data;
        if (d == null) {
          return;
        }
        if (name === "connected") {
          hasOpenedRef.v = true;
          attemptRef.n = 0;
          setStatus("connected");
          return;
        }
        if (name === "ping") {
          return;
        }
        let parsed: AxiomEvent;
        try {
          parsed = JSON.parse(String(d)) as AxiomEvent;
        } catch {
          return;
        }
        setLastEvent(parsed);
        onEventRef.current?.(parsed);
        const inv = uniqueKeys(keysForType(parsed.type, projectId, windows));
        for (const qk of inv) {
          void queryClient.invalidateQueries({ queryKey: [...qk] as unknown[] });
        }
        if (inv.length === 0) {
          // eslint-disable-next-line no-console
          console.warn("[useAxiomEvents] unmapped event type:", parsed.type);
        }
      };

      for (const name of NAMED) {
        const fn = namedHandler(name);
        s.addEventListener(name, fn, false);
        handlers.push({ ev: name, fn });
      }

      const onErr: (e: Event) => void = () => {
        if (s.readyState === EventSource.CLOSED) {
          removeAllListeners(s);
          if (s === source) {
            try {
              s.close();
            } catch {
              /* ignore */
            }
            source = null;
          }
          if (!userPausedRef.current) {
            scheduleReconnect();
          }
        }
      };
      onErrorHandler = onErr;
      s.addEventListener("error", onErr, false);
    };

    attach();

    return () => {
      clearTimer();
      if (source) {
        try {
          removeAllListeners(source);
          source.close();
        } catch {
          /* ignore */
        }
        source = null;
      }
    };
  }, [projectId, userPaused, queryClient, windows]);

  return {
    status: !projectId ? "disconnected" : status,
    lastEvent,
    connect: useCallback(() => {
      setUserPaused(false);
    }, []),
    disconnect: useCallback(() => {
      setUserPaused(true);
    }, []),
  };
}
