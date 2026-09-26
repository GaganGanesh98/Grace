"use client";

import type { ReactElement } from "react";

type ArtifactsGridProps = {
  paths: string[];
};

export function ArtifactsGrid({ paths }: ArtifactsGridProps): ReactElement {
  if (paths.length === 0) {
    return (
      <p className="font-mono text-axiom-13 uppercase tracking-wide text-text-tertiary">No artifact paths recorded.</p>
    );
  }

  return (
    <ul className="grid gap-2 sm:grid-cols-2">
      {paths.map((p) => (
        <li
          key={p}
          className="rounded-md border border-border bg-[var(--surface-muted)] px-3 py-2 font-mono text-axiom-13 text-text-primary"
        >
          {p}
        </li>
      ))}
    </ul>
  );
}
