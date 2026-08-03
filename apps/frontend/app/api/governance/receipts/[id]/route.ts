import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";
import { getApiUrl } from "@/lib/env";

type RouteContext = { params: Promise<{ id: string }> };

export async function GET(req: Request, context: RouteContext): Promise<NextResponse> {
  const { id } = await context.params;
  const url = new URL(req.url);
  const share = url.searchParams.get("share_token");
  if (share) {
    const qs = `?share_token=${encodeURIComponent(share)}`;
    const r = await fetch(`${getApiUrl()}/v1/governance/receipts/${encodeURIComponent(id)}${qs}`, {
      cache: "no-store",
    });
    const text = await r.text();
    return new NextResponse(text, {
      status: r.status,
      headers: { "content-type": r.headers.get("content-type") ?? "application/json" },
    });
  }

  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Not authenticated" } }, { status: 401 });
  }
  const projectId = url.searchParams.get("project_id");
  const qs = new URLSearchParams();
  if (projectId) {
    qs.set("project_id", projectId);
  }
  const backendQs = qs.toString();
  const cookie = req.headers.get("cookie");
  const r = await fetch(
    `${getApiUrl()}/v1/governance/receipts/${encodeURIComponent(id)}${backendQs ? `?${backendQs}` : ""}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        ...(cookie ? { Cookie: cookie } : {}),
      },
      credentials: "include",
      cache: "no-store",
    },
  );
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "content-type": r.headers.get("content-type") ?? "application/json" },
  });
}
