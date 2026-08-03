"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";

import { getAgentRunWebSocketUrl } from "@/lib/public-api-url";

export type RunStreamEvent = Record<string, unknown> & { type?: string };

type WsState = {
  events: RunStreamEvent[];
  status: "idle" | "connecting" | "open" | "closed" | "error";
  closeCode: number | null;
  errorMessage: string | null;
};

type WsAction =
  | { type: "reset" }
  | { type: "connecting" }
  | { type: "open" }
  | { type: "message"; payload: RunStreamEvent }
  | { type: "close"; code: number }
  | { type: "error"; message: string };

function reducer(state: WsState, action: WsAction): WsState {
  switch (action.type) {
    case "reset":
      return {
        events: [],
        status: "idle",
        closeCode: null,
        errorMessage: null,
      };
    case "connecting":
      return { ...state, status: "connecting", errorMessage: null };
    case "open":
      return { ...state, status: "open" };
    case "message":
      return { ...state, events: [...state.events, action.payload] };
    case "close":
      return { ...state, status: "closed", closeCode: action.code };
    case "error":
      return { ...state, status: "error", errorMessage: action.message };
    default:
      return state;
  }
}

const initial: WsState = {
  events: [],
  status: "idle",
  closeCode: null,
  errorMessage: null,
};

/**
 * Native WebSocket to backend `/ws/agent-runs/{runId}?token=…`.
 * Server sends replay (oldest-first) then live events; we append in order.
 */
export function useRunWebSocket(
  runId: string | null,
  token: string | null,
): WsState & { reconnect: () => void } {
  const [state, dispatch] = useReducer(reducer, initial);
  const wsRef = useRef<WebSocket | null>(null);
  const tokenRef = useRef(token);
  tokenRef.current = token;

  const connect = useCallback(() => {
    if (!runId || !tokenRef.current) {
      return;
    }
    dispatch({ type: "reset" });
    dispatch({ type: "connecting" });
    const url = getAgentRunWebSocketUrl(runId, tokenRef.current);
    const ws = new WebSocket(url);
    wsRef.current = ws;
    ws.onopen = () => {
      dispatch({ type: "open" });
    };
    ws.onmessage = (ev) => {
      try {
        const parsed = JSON.parse(ev.data as string) as RunStreamEvent;
        dispatch({ type: "message", payload: parsed });
      } catch {
        dispatch({ type: "error", message: "Invalid event payload" });
      }
    };
    ws.onerror = () => {
      dispatch({ type: "error", message: "WebSocket error" });
    };
    ws.onclose = (ev) => {
      dispatch({ type: "close", code: ev.code });
      if (ev.code === 4401) {
        dispatch({ type: "error", message: "WebSocket unauthorized (4401)" });
      }
    };
  }, [runId]);

  useEffect(() => {
    if (!runId || !token) {
      dispatch({ type: "reset" });
      return;
    }
    connect();
    return () => {
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [runId, token, connect]);

  return { ...state, reconnect: connect };
}
