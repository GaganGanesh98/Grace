import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";
import { getApiUrl } from "@/lib/env";
import { jsonError } from "@/lib/http-errors";

type RouteContext = { params: Promise<{ id: string }> };

export async function POST(req: Request, context: RouteContext): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  if (!token) {
    return jsonError("unauthorized", "Not authenticated", 401);
  }
  const { id } = await context.params;
  let body = "";
  try {
    body = await req.text();
  } catch {
    return jsonError("bad_request", "Invalid body", 400);
  }
  const cookie = req.headers.get("cookie");
  const r = await fetch(
    `${getApiUrl()}/v1/governance/receipts/${encodeURIComponent(id)}/extend-hold`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        ...(cookie ? { Cookie: cookie } : {}),
      },
      body: body || "{}",
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
