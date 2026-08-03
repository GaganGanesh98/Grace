import { NextResponse } from "next/server";
import { cookies } from "next/headers";

import { ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE, clearAuthCookies } from "@/lib/auth-cookies";
import { getApiUrl } from "@/lib/env";

export async function POST(): Promise<NextResponse> {
  const jar = await cookies();
  const access = jar.get(ACCESS_TOKEN_COOKIE)?.value;
  const refresh = jar.get(REFRESH_TOKEN_COOKIE)?.value;

  if (!refresh) {
    const res = NextResponse.json({ data: { status: "ok" as const } });
    clearAuthCookies(res);
    return res;
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (access) {
    headers.Authorization = `Bearer ${access}`;
  }

  const backend = await fetch(`${getApiUrl()}/api/v1/auth/logout`, {
    method: "POST",
    headers,
    body: JSON.stringify({ refresh_token: refresh }),
  });

  const text = await backend.text();
  const res = backend.ok
    ? NextResponse.json({ data: { status: "ok" as const } })
    : new NextResponse(text, {
        status: backend.status,
        headers: { "content-type": backend.headers.get("content-type") ?? "application/json" },
      });

  if (backend.ok) {
    clearAuthCookies(res);
  }
  return res;
}
