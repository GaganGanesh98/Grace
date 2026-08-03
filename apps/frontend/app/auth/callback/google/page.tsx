import { Suspense } from "react";

import { GoogleCallbackInner } from "./google-callback-inner";

export default function GoogleCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center p-6">
          <p className="text-sm text-muted-foreground">Loading…</p>
        </div>
      }
    >
      <GoogleCallbackInner />
    </Suspense>
  );
}
