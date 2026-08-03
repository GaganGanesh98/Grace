import { NextResponse } from "next/server";
import { cookies } from "next/headers";

import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";
import { getApiUrl } from "@/lib/env";
import { jsonError } from "@/lib/http-errors";
import { createProjectBodySchema } from "@/lib/schemas";

export async function GET(req: Request): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  if (!token) {
    return jsonError("unauthorized", "Not authenticated", 401);
  }
  const cookie = req.headers.get("cookie");
  const r = await fetch(`${getApiUrl()}/api/v1/projects`, {
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

export async function POST(req: Request): Promise<NextResponse> {
  let raw: unknown;
  try {
    raw = await req.json();
  } catch {
    return jsonError("bad_request", "Invalid JSON", 400);
  }
  const parsed = createProjectBodySchema.safeParse(raw);
  if (!parsed.success) {
    return jsonError("validation_error", "Invalid input", 422);
  }
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  if (!token) {
    return jsonError("unauthorized", "Not authenticated", 401);
  }
  const cookie = req.headers.get("cookie");
  const r = await fetch(`${getApiUrl()}/api/v1/projects`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(cookie ? { Cookie: cookie } : {}),
    },
    body: JSON.stringify(parsed.data),
    credentials: "include",
  });
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "content-type": r.headers.get("content-type") ?? "application/json" },
  });
}
