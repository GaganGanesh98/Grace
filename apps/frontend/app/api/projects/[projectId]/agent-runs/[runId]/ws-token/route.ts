import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { forwardBackendJson } from "@/lib/bff-forward";
import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";
import { getApiUrl } from "@/lib/env";

type Ctx = { params: Promise<{ projectId: string; runId: string }> };

export async function POST(req: Request, context: Ctx): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  const { projectId, runId } = await context.params;
  const target = `${getApiUrl()}/v1/agent-runs/${encodeURIComponent(runId)}/ws-token?project_id=${encodeURIComponent(projectId)}`;
  return forwardBackendJson(req, token, target, { method: "POST" }, { mapForbiddenToNotFound: true });
}
