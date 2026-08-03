import { NextResponse } from "next/server";

import { setAuthCookies } from "@/lib/auth-cookies";
import { getApiUrl } from "@/lib/env";
import { jsonError } from "@/lib/http-errors";
import { googleCallbackBodySchema } from "@/lib/schemas";
import type { DataEnvelope, TokenPair } from "@/lib/types";

export async function POST(req: Request): Promise<NextResponse> {
  let raw: unknown;
  try {
    raw = await req.json();
  } catch {
    return jsonError("bad_request", "Invalid JSON", 400);
  }
  const parsed = googleCallbackBodySchema.safeParse(raw);
  if (!parsed.success) {
    return jsonError("validation_error", "Invalid input", 422);
  }

  const backend = await fetch(`${getApiUrl()}/api/v1/auth/google/callback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(parsed.data),
  });

  const text = await backend.text();
  if (!backend.ok) {
    return new NextResponse(text, {
      status: backend.status,
      headers: { "content-type": backend.headers.get("content-type") ?? "application/json" },
    });
  }

  const envelope = JSON.parse(text) as DataEnvelope<TokenPair>;
  const res = NextResponse.json({ data: { status: "ok" as const } });
  setAuthCookies(res, envelope.data.access_token, envelope.data.refresh_token);
  return res;
}
