import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";

export function middleware(request: NextRequest): NextResponse {
  // Dev only: Next blocks its dev scripts for the 127.0.0.1 origin, so the page
  // never hydrates (login looks dead, and a native form submit is all that is
  // left), and Google OAuth is registered for localhost. Send 127.0.0.1 to
  // localhost before anything else happens. A Location header cannot do this:
  // the dev server rewrites Locations on its own origin (localhost) into
  // relative paths, which would loop back to 127.0.0.1. A meta refresh needs no
  // JavaScript and is not rewritten.
  const host = request.headers.get("host") ?? "";
  if (process.env.NODE_ENV === "development" && host.startsWith("127.0.0.1")) {
    const target = new URL(
      `${request.nextUrl.pathname}${request.nextUrl.search}`,
      `http://${host.replace("127.0.0.1", "localhost")}`,
    ).href.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
    return new NextResponse(
      `<!doctype html><meta http-equiv="refresh" content="0;url=${target}"><a href="${target}">Continue to localhost</a>`,
      { status: 200, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } },
    );
  }

  const path = request.nextUrl.pathname;
  const token = request.cookies.get(ACCESS_TOKEN_COOKIE)?.value;

  if (path.startsWith("/dashboard")) {
    if (!token) {
      return NextResponse.redirect(new URL("/login", request.url));
    }
    return NextResponse.next();
  }

  if (path === "/login" || path === "/signup") {
    // Do not redirect to /dashboard just because a cookie exists: the token may be
    // expired or invalid, and /dashboard will send users here on 401 — redirecting
    // back would create an infinite 307 loop.
    return NextResponse.next();
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/dashboard/:path*", "/login", "/signup"],
};
