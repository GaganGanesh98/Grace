/**
 * Server envelope for project-scoped events (GET /v1/events/stream, BFF /api/events/stream).
 */
export type AxiomEvent = {
  type: string;
  project_id: string;
  ts: string;
  payload: Record<string, unknown>;
};

export type AxiomEventsStatus = "connecting" | "connected" | "disconnected" | "reconnecting";
