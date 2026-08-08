import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactElement, type ReactNode } from "react";

import { useGraceEvents } from "@/lib/events/use-grace-events";

const qc = new QueryClient();
function w({ children }: { children: ReactNode }): ReactElement {
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("useGraceEvents basics", () => {
  it("keeps status disconnected for null projectId", () => {
    const { result } = renderHook(() => useGraceEvents({ projectId: null }), { wrapper: w });
    expect(result.current.status).toBe("disconnected");
  });
});
