"use client";

import type { ReactElement } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { apiGoogleCallback } from "@/lib/api";

/** OAuth return handler; `useRef` guard avoids Strict Mode double `useEffect` consuming single-use CSRF state (ADR-024). */
export function GoogleCallbackInner(): ReactElement {
  const router = useRouter();
  const searchParams = useSearchParams();
  const hasFiredRef = useRef(false);
  const [message, setMessage] = useState("Completing sign-in…");

  useEffect(() => {
    if (hasFiredRef.current) {
      return;
    }
    hasFiredRef.current = true;

    const code = searchParams.get("code");
    const state = searchParams.get("state");
    if (!code || !state) {
      setMessage("Missing OAuth parameters.");
      return;
    }

    void (async () => {
      try {
        await apiGoogleCallback(code, state);
        router.replace("/dashboard");
        router.refresh();
      } catch (e: unknown) {
        setMessage(e instanceof Error ? e.message : "Google sign-in failed.");
      }
    })();
  }, [router, searchParams]);

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}
