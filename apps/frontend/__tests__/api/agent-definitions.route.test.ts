import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (name: string) => (name === "access_token" ? { value: "jwt-test" } : undefined),
  })),
}));

vi.mock("@/lib/env", () => ({
  getApiUrl: () => "http://backend.test",
}));

describe("BFF agent-definitions", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("forwards Authorization Bearer from cookie on GET", async () => {
    const { GET } = await import("@/app/api/projects/[projectId]/agent-definitions/route");
    const fetchMock = globalThis.fetch as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ data: [], meta: { total: 0, page: 1, per_page: 20, has_more: false } }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const req = new Request("http://localhost/api/projects/p1/agent-definitions");
    const res = await GET(req, { params: Promise.resolve({ projectId: "p1" }) });
    expect(res.status).toBe(200);
    expect(fetchMock).toHaveBeenCalled();
    const call = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(call[1].headers).toMatchObject({
      Authorization: "Bearer jwt-test",
    });
    expect(String(call[0])).toContain("/v1/agent-definitions");
    expect(String(call[0])).toContain("project_id=p1");
  });

  it("maps backend 403 to 404 when flag set", async () => {
    const { GET } = await import("@/app/api/projects/[projectId]/agent-definitions/route");
    const fetchMock = globalThis.fetch as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue(new Response("{}", { status: 403 }));
    const req = new Request("http://localhost/api/projects/p1/agent-definitions");
    const res = await GET(req, { params: Promise.resolve({ projectId: "p1" }) });
    expect(res.status).toBe(404);
  });
});
