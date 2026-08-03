import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { useRunWebSocket } from "@/hooks/use-run-websocket";

vi.mock("@/lib/public-api-url", () => ({
  getAgentRunWebSocketUrl: (runId: string, token: string) =>
    `ws://test/ws/agent-runs/${runId}?token=${encodeURIComponent(token)}`,
}));

function Probe({
  runId,
  token,
  onState,
}: {
  runId: string | null;
  token: string | null;
  onState: (s: ReturnType<typeof useRunWebSocket>) => void;
}): null {
  const s = useRunWebSocket(runId, token);
  onState(s);
  return null;
}

describe("useRunWebSocket", () => {
  const origWS = globalThis.WebSocket;

  beforeEach(() => {
    class MockWS {
      static instances: MockWS[] = [];
      onopen: (() => void) | null = null;
      onmessage: ((ev: { data: string }) => void) | null = null;
      onerror: (() => void) | null = null;
      onclose: ((ev: { code: number }) => void) | null = null;
      url: string;
      constructor(url: string) {
        this.url = url;
        MockWS.instances.push(this);
        queueMicrotask(() => {
          this.onopen?.();
        });
      }
      close(): void {
        this.onclose?.({ code: 1000 });
      }
    }
    globalThis.WebSocket = MockWS as unknown as typeof WebSocket;
    (globalThis.WebSocket as unknown as { instances: MockWS[] }).instances = MockWS.instances;
  });

  afterEach(() => {
    globalThis.WebSocket = origWS;
  });

  it("appends live events in order", async () => {
    let last: ReturnType<typeof useRunWebSocket> | null = null;
    render(
      <Probe
        runId="r1"
        token="tok"
        onState={(s) => {
          last = s;
        }}
      />,
    );
    await waitFor(() => {
      const Ctor = globalThis.WebSocket as unknown as { instances: { onmessage?: (e: { data: string }) => void }[] };
      expect(Ctor.instances[0]).toBeTruthy();
    });
    const Ctor = globalThis.WebSocket as unknown as { instances: { onmessage?: (e: { data: string }) => void }[] };
    Ctor.instances[0].onmessage?.({ data: JSON.stringify({ type: "a", n: 1 }) });
    Ctor.instances[0].onmessage?.({ data: JSON.stringify({ type: "b", n: 2 }) });
    await waitFor(() => {
      expect(last?.events.length).toBe(2);
      expect(last?.events[0]).toMatchObject({ type: "a" });
      expect(last?.events[1]).toMatchObject({ type: "b" });
    });
  });
});
