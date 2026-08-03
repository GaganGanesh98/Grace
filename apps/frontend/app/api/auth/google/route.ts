import { NextResponse } from "next/server";

import { getApiUrl } from "@/lib/env";
import { jsonError } from "@/lib/http-errors";
import type { DataEnvelope } from "@/lib/types";

type AuthorizeData = {
  url: string;
  state: string;
};

export async function GET(): Promise<NextResponse> {
  const backend = await fetch(`${getApiUrl()}/api/v1/auth/google/authorize`, {
    cache: "no-store",
  });
  const text = await backend.text();
  if (!backend.ok) {
    return new NextResponse(text, {
      status: backend.status,
      headers: { "content-type": backend.headers.get("content-type") ?? "application/json" },
    });
  }
  try {
    const envelope = JSON.parse(text) as DataEnvelope<AuthorizeData>;
    return NextResponse.redirect(envelope.data.url);
  } catch {
    return jsonError("bad_request", "Invalid authorize response", 502);
  }
}
