"use client";

import Link from "next/link";
import { type ReactElement } from "react";

import { cn } from "@/lib/utils";

const steps: Array<{ num: string; title: string; body: string }> = [
  {
    num: "01",
    title: "PROJECT",
    body: "Create a workspace. Everything — agents, tools, and receipts — stays scoped to this project.",
  },
  {
    num: "02",
    title: "AGENT",
    body: "Register an agent definition, then run it through Grace so every action is governed and signed.",
  },
  {
    num: "03",
    title: "RUN",
    body: "Submit a run. Every governed action returns a verifiable receipt you can trace in the ledger.",
  },
];

export function EmptyStateCommandCenter({ className }: { className?: string }): ReactElement {
  return (
    <div
      className={cn("mx-auto w-full max-w-2xl space-y-8 text-center", className)}
      data-testid="cc-empty-state"
    >
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full border-2 border-[var(--axiom-electric)] bg-[var(--axiom-bg)]">
        <div className="flex h-6 w-6 items-center justify-center" aria-hidden>
          <div className="h-3 w-3 rotate-45 border border-[var(--axiom-electric)] bg-[var(--axiom-bg)]" />
        </div>
      </div>
      <div className="space-y-2">
        <h2 className="text-axiom-20 font-medium text-[var(--axiom-text)]">
          Nothing here yet — let&apos;s change that.
        </h2>
        <p className="text-axiom-15 leading-relaxed text-[var(--axiom-text-muted)]">
          Grace signs and governs every action your AI agents take. To start, create a project, add an agent, and
          submit your first run. Every action will produce a cryptographically signed receipt.
        </p>
      </div>
      <div className="flex flex-col items-center gap-2">
        <Link
          className="inline-flex min-h-10 items-center justify-center rounded-sm border border-transparent bg-neutral-100 px-4 font-mono text-axiom-12 font-semibold tracking-wide text-text-inverse outline-none transition-colors hover:bg-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-neutral-100 focus-visible:outline-offset-2"
          href="/dashboard/projects"
        >
          + CREATE FIRST PROJECT
        </Link>
        <p className="text-axiom-14 text-[var(--axiom-text-dim)]">
          or read the{" "}
          <Link
            className="text-[var(--axiom-electric)] underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--axiom-electric)]"
            href="/docs/quickstart"
          >
            5-minute quickstart →
          </Link>
        </p>
      </div>
      <ol className="mt-8 grid w-full max-w-3xl gap-4 text-left sm:grid-cols-3">
        {steps.map((s) => (
          <li
            key={s.num}
            className="flex gap-3 rounded-lg border border-[var(--axiom-border)] bg-[var(--axiom-bg-card)] p-4"
          >
            <span
              className="font-mono text-axiom-14 text-[var(--axiom-electric)]"
              aria-hidden
            >
              {s.num}
            </span>
            <div>
              <h3 className="text-axiom-13 font-medium text-[var(--axiom-text-label)]">{s.title}</h3>
              <p className="mt-1.5 text-axiom-13 text-[var(--axiom-text-muted)]">{s.body}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
