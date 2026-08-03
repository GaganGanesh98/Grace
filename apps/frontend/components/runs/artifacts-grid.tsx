"use client";

import type { ReactElement } from "react";

type ArtifactsGridProps = {
  paths: string[];
};

export function ArtifactsGrid({ paths }: ArtifactsGridProps): ReactElement {
  if (paths.length === 0) {
    return (
      <p className="font-mono text-axiom-13 uppercase tracking-wide text-[#6B7490]">No artifact paths recorded.</p>
    );
  }

  return (
    <ul className="grid gap-2 sm:grid-cols-2">
      {paths.map((p) => (
        <li
          key={p}
          className="rounded-md border border-[rgba(255,255,255,0.08)] bg-[#080810] px-3 py-2 font-mono text-axiom-13 text-[#F0F2F8]"
        >
          {p}
        </li>
      ))}
    </ul>
  );
}
