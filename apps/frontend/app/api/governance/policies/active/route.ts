import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";
import { getApiUrl } from "@/lib/env";

export async function GET(req: Request): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Not authenticated" } }, { status: 401 });
  }
  const url = new URL(req.url);
  const qs = url.searchParams.toString();
  const target = `${getApiUrl()}/v1/governance/policies/active${qs ? `?${qs}` : ""}`;
  const cookie = req.headers.get("cookie");
  const r = await fetch(target, {
    headers: {
      Authorization: `Bearer ${token}`,
      ...(cookie ? { Cookie: cookie } : {}),
    },
    credentials: "include",
    cache: "no-store",
  });
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "content-type": r.headers.get("content-type") ?? "application/json" },
  });
}
