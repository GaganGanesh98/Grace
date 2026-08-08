"use client";

import Link from "next/link";
import { type ReactElement } from "react";

import { cn } from "@/lib/utils";

/**
 * Real dependency chain for a first run. The quickstart used to skip
 * CREDENTIAL, which sent new users into an agent form they could not submit.
 */
export type QuickstartState = {
  hasProject: boolean;
  hasCredential: boolean;
  hasAgent: boolean;
  /** Agent-definitions route for the active project, when there is one. */
  agentsHref: string | null;
};

const DEFAULT_STATE: QuickstartState = {
  hasProject: false,
  hasCredential: false,
  hasAgent: false,
  agentsHref: null,
};

type Step = {
  num: string;
  title: string;
  body: string;
  done: boolean;
  cta: { label: string; href: string } | null;
};

function buildSteps(state: QuickstartState): Step[] {
  return [
    {
      num: "01",
      title: "PROJECT",
      body: "Create a workspace. Everything — agents, tools, and receipts — stays scoped to this project.",
      done: state.hasProject,
      cta: { label: "+ CREATE FIRST PROJECT", href: "/dashboard/projects" },
    },
    {
      num: "02",
      title: "CREDENTIAL",
      body: "Add an LLM provider key to the vault. Agents need one to run — it is encrypted at rest and never displayed again.",
      done: state.hasCredential,
      cta: { label: "+ ADD CREDENTIAL", href: "/dashboard/vault" },
    },
    {
      num: "03",
      title: "AGENT",
      body: "Register an agent definition, then run it through Grace so every action is governed and signed.",
      done: state.hasAgent,
      cta: state.agentsHref ? { label: "+ NEW AGENT", href: state.agentsHref } : null,
    },
    {
      num: "04",
      title: "RUN",
      body: "Submit a run. Every governed action returns a verifiable receipt you can trace in the ledger.",
      done: false,
      cta: state.agentsHref ? { label: "GO TO AGENTS", href: state.agentsHref } : null,
    },
  ];
}

export function EmptyStateCommandCenter({
  className,
  state = DEFAULT_STATE,
}: {
  className?: string;
  state?: QuickstartState;
}): ReactElement {
  const steps = buildSteps(state);
  const currentIndex = steps.findIndex((s) => !s.done);
  const current = currentIndex === -1 ? steps[steps.length - 1] : steps[currentIndex];
  const primaryCta = current.cta ?? steps[0].cta!;

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
          Grace signs and governs every action your AI agents take. To start, create a project, add a
          provider credential, register an agent, and submit your first run. Every action will produce
          a cryptographically signed receipt.
        </p>
      </div>
      <div className="flex flex-col items-center gap-2">
        <Link
          className="inline-flex min-h-10 items-center justify-center rounded-sm border border-transparent bg-neutral-100 px-4 font-mono text-axiom-12 font-semibold tracking-wide text-text-inverse outline-none transition-colors hover:bg-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-neutral-100 focus-visible:outline-offset-2"
          href={primaryCta.href}
        >
          {primaryCta.label}
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
      <ol
        className="mt-8 grid w-full max-w-3xl gap-4 text-left sm:grid-cols-2"
        aria-label="Quickstart steps"
      >
        {steps.map((s, i) => {
          const isCurrent = s === current;
          return (
            <li
              key={s.num}
              data-testid={`quickstart-step-${s.num}`}
              data-state={s.done ? "done" : isCurrent ? "current" : "pending"}
              className={cn(
                "flex gap-3 rounded-lg border bg-[var(--axiom-bg-card)] p-4",
                isCurrent
                  ? "border-[var(--axiom-electric)]"
                  : "border-[var(--axiom-border)]",
                s.done ? "opacity-70" : null,
              )}
            >
              <span className="font-mono text-axiom-14 text-[var(--axiom-electric)]" aria-hidden>
                {s.done ? "✓" : s.num}
              </span>
              <div className="min-w-0">
                <h3 className="flex flex-wrap items-center gap-2 text-axiom-13 font-medium text-[var(--axiom-text-label)]">
                  <span data-testid="quickstart-title">{s.title}</span>
                  <span className="font-mono text-axiom-10 uppercase tracking-[1px] text-[var(--axiom-text-dim)]">
                    {s.done ? "Done" : isCurrent ? "You are here" : `Step ${i + 1}`}
                  </span>
                </h3>
                <p className="mt-1.5 text-axiom-13 text-[var(--axiom-text-muted)]">{s.body}</p>
                {isCurrent && s.cta ? (
                  <Link
                    href={s.cta.href}
                    className="mt-2 inline-block font-mono text-axiom-11 uppercase tracking-wide text-[var(--axiom-electric)] hover:underline"
                  >
                    {s.cta.label} →
                  </Link>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
