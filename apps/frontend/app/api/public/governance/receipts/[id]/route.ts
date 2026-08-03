import { NextResponse } from "next/server";

import { getApiUrl } from "@/lib/env";

type RouteContext = { params: Promise<{ id: string }> };

/** Public proxy for GET /v1/governance/receipts/{id} when share_token matches intent metadata (no auth). */
export async function GET(req: Request, context: RouteContext): Promise<NextResponse> {
  const { id } = await context.params;
  const url = new URL(req.url);
  const token = url.searchParams.get("share_token") ?? url.searchParams.get("token");
  if (!token) {
    return NextResponse.json(
      {
        error: {
          code: "share_token_required",
          message: "A share token is required to view this record publicly.",
          details: { field_errors: [] as unknown[] },
        },
      },
      { status: 400 },
    );
  }
  const r = await fetch(
    `${getApiUrl()}/v1/governance/receipts/${encodeURIComponent(id)}?share_token=${encodeURIComponent(token)}`,
    { cache: "no-store" },
  );
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "content-type": r.headers.get("content-type") ?? "application/json" },
  });
}
