"use client";

import Link from "next/link";
import { useState, type ReactElement } from "react";

import { AgentForm } from "@/components/agent-definitions/agent-form";
import { Button } from "@/components/ui/button";
import { AddCredentialModal } from "@/components/vault/add-credential-modal";
import { SUPPORTED_LLM_SERVICES_LABEL, supportedLlmKeys } from "@/lib/llm-providers";
import type { LlmProvider } from "@/lib/providers-api";
import type { VaultKey } from "@/lib/vault-api";

type AgentCreatePanelProps = {
  vaultKeys: VaultKey[];
  /** Provider catalog from the backend registry; drives the model options. */
  providers?: LlmProvider[];
  vaultLoading: boolean;
  vaultError: string | null;
  onSubmit: (values: Record<string, unknown>) => Promise<void>;
  isSubmitting: boolean;
  submitError: string | null;
  /** Called after the inline dialog stores a new credential, so the caller can refetch. */
  onCredentialCreated: (key: VaultKey) => void;
};

/**
 * Agent creation entry point.
 *
 * A project with an empty vault cannot produce an agent, so the credential step
 * is presented *before* the form rather than as a disabled submit button below
 * it. The credential dialog opens over this panel — the form stays mounted, so
 * a half-typed name and system prompt survive the detour.
 */
export function AgentCreatePanel({
  vaultKeys,
  providers,
  vaultLoading,
  vaultError,
  onSubmit,
  isSubmitting,
  submitError,
  onCredentialCreated,
}: AgentCreatePanelProps): ReactElement {
  const [credentialModalOpen, setCredentialModalOpen] = useState(false);
  const usableKeys = supportedLlmKeys(vaultKeys);

  const modal = (
    <AddCredentialModal
      open={credentialModalOpen}
      onClose={() => {
        setCredentialModalOpen(false);
      }}
      onCreated={onCredentialCreated}
    />
  );

  if (vaultLoading) {
    return (
      <div
        className="h-56 animate-pulse rounded-lg border border-border-subtle bg-surface-card"
        role="status"
        aria-label="Loading vault credentials"
      />
    );
  }

  if (vaultError) {
    return (
      <div
        className="rounded-lg border border-border-subtle bg-surface-card p-6 text-axiom-14 text-red-400"
        role="alert"
      >
        Could not load your vault credentials: {vaultError}
      </div>
    );
  }

  if (usableKeys.length === 0) {
    return (
      <>
        <div
          className="space-y-4 rounded-lg border border-border-subtle bg-surface-card p-6"
          data-testid="agent-credential-required"
        >
          <div className="space-y-2">
            <p className="font-mono text-axiom-11 uppercase tracking-[2px] text-amber-400">
              Step 1 of 2 — credential required
            </p>
            <h3 className="text-axiom-16 font-medium text-text-primary">
              Add an LLM provider key before creating an agent
            </h3>
            <p className="max-w-prose text-axiom-14 text-text-secondary">
              An agent runs against a provider credential from your vault, so there is nothing to
              create until one exists. Add a key from {SUPPORTED_LLM_SERVICES_LABEL} — it is
              encrypted at rest and never displayed again.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="button"
              onClick={() => {
                setCredentialModalOpen(true);
              }}
            >
              + ADD CREDENTIAL
            </Button>
            <Link
              href="/dashboard/vault"
              className="font-mono text-axiom-12 uppercase tracking-wide text-[var(--axiom-electric)] hover:underline"
            >
              Open vault →
            </Link>
          </div>
        </div>
        {modal}
      </>
    );
  }

  return (
    <div className="space-y-3">
      <AgentForm
        vaultKeys={vaultKeys}
        providers={providers}
        onSubmit={onSubmit}
        isSubmitting={isSubmitting}
        submitError={submitError}
      />
      <div className="flex items-center gap-3">
        <Button
          type="button"
          variant="secondary"
          onClick={() => {
            setCredentialModalOpen(true);
          }}
        >
          + Add credential
        </Button>
        <span className="text-axiom-13 text-text-tertiary">
          Adding one here keeps everything you have typed.
        </span>
      </div>
      {modal}
    </div>
  );
}
