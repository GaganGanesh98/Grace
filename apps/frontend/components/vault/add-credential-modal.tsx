"use client";

import { X } from "lucide-react";
import { type FormEvent, type ReactElement, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  createVaultKey,
  detectCredential,
  type DetectResult,
  type VaultKind,
  type VaultKey,
} from "@/lib/vault-api";
import { cn } from "@/lib/utils";

const NAME_ALLOWED = /^[a-z0-9-]*$/;
const NAME_VALID = /^[a-z0-9-]{2,64}$/;

type AddCredentialModalProps = {
  open: boolean;
  onClose: () => void;
  onCreated?: (key: VaultKey) => void;
};

export function AddCredentialModal({ open, onClose, onCreated }: AddCredentialModalProps): ReactElement | null {
  const [name, setName] = useState("");
  const [rawKey, setRawKey] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);
  const [detected, setDetected] = useState<DetectResult | null>(null);
  const [detecting, setDetecting] = useState(false);
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [serviceOverride, setServiceOverride] = useState("");
  const [kindOverride, setKindOverride] = useState<VaultKind>("llm");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const nameValid = useMemo(() => NAME_VALID.test(name), [name]);
  const canSubmit = nameValid && rawKey.trim().length > 0 && !submitting;
  const couldNotDetect = detected?.kind === "custom" && detected.service === "custom";

  useEffect(() => {
    if (!open) {
      setName("");
      setRawKey("");
      setNameError(null);
      setDetected(null);
      setDetecting(false);
      setOverrideOpen(false);
      setServiceOverride("");
      setKindOverride("llm");
      setSubmitError(null);
      setSubmitting(false);
    }
  }, [open]);

  useEffect(() => {
    const value = rawKey.trim();
    if (!value) {
      setDetected(null);
      setDetecting(false);
      setOverrideOpen(false);
      return;
    }

    let cancelled = false;
    setDetecting(true);
    const timer = window.setTimeout(() => {
      void detectCredential(value)
        .then((result) => {
          if (cancelled) {
            return;
          }
          setDetected(result);
          setServiceOverride((current) => current || result.service);
          setKindOverride(result.kind);
          if (result.kind === "custom" && result.service === "custom") {
            setOverrideOpen(true);
          }
        })
        .catch(() => {
          if (!cancelled) {
            setDetected({ kind: "custom", service: "custom" });
            setOverrideOpen(true);
          }
        })
        .finally(() => {
          if (!cancelled) {
            setDetecting(false);
          }
        });
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [rawKey]);

  if (!open) {
    return null;
  }

  function close(): void {
    if (!submitting) {
      onClose();
    }
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    if (!canSubmit) {
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const key = await createVaultKey({
        name,
        raw_key: rawKey.trim(),
        ...(overrideOpen && serviceOverride.trim() ? { service_override: serviceOverride.trim() } : {}),
        ...(overrideOpen ? { kind_override: kindOverride } : {}),
      });
      toast.success("Credential added");
      onCreated?.(key);
      onClose();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Failed to add credential");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-[var(--surface-overlay)] p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-credential-title"
        className="w-full max-w-[480px] animate-in fade-in slide-in-from-bottom-2 rounded-lg border border-border-subtle bg-surface-card p-6 shadow-md duration-base ease-out"
      >
        <div className="flex items-center justify-between gap-4">
          <h2 id="add-credential-title" className="text-heading text-text-primary">
            Add credential
          </h2>
          <button
            type="button"
            className="rounded-sm p-1 text-text-secondary transition-colors duration-fast hover:bg-surface-elevated hover:text-text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-neutral-100 focus-visible:outline-offset-2"
            aria-label="Close"
            onClick={close}
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        <form className="mt-6 space-y-4" onSubmit={onSubmit}>
          <div>
            <Label htmlFor="credential-name" className="text-micro uppercase tracking-[0.06em] text-text-secondary">
              NAME
            </Label>
            <Input
              id="credential-name"
              className="mt-2"
              value={name}
              autoComplete="off"
              aria-invalid={Boolean(nameError)}
              onChange={(e) => {
                const next = e.target.value;
                if (!NAME_ALLOWED.test(next)) {
                  setNameError("Name can only contain lowercase letters, numbers, and dashes");
                  return;
                }
                setName(next);
                setNameError(null);
              }}
            />
            <p className="mt-1 text-caption text-text-tertiary">Lowercase letters, numbers, dashes only</p>
            {nameError ? <p className="mt-1 text-caption text-status-denied-fg">{nameError}</p> : null}
          </div>

          <div>
            <Label htmlFor="credential-raw-key" className="text-micro uppercase tracking-[0.06em] text-text-secondary">
              CREDENTIAL
            </Label>
            <Input
              id="credential-raw-key"
              type="password"
              className="mt-2 font-mono"
              value={rawKey}
              autoComplete="off"
              onChange={(e) => {
                setRawKey(e.target.value);
              }}
            />
            <p className="mt-1 text-caption text-text-tertiary">
              Pasted credentials are encrypted at rest. Never displayed after save.
            </p>
            {detecting ? <p className="mt-2 text-caption text-text-tertiary">Detecting credential…</p> : null}
            {detected && !couldNotDetect ? (
              <p className="mt-2 inline-flex items-center gap-1 rounded-xs border border-border-subtle bg-surface-elevated px-2 py-1 text-caption text-text-secondary">
                <span>Detected:</span>
                <span className="text-text-primary">{detected.service}</span>
                <span className="text-text-tertiary">({detected.kind.toUpperCase()})</span>
                <button
                  type="button"
                  className="ml-1 border-b border-transparent text-text-secondary hover:border-border-strong"
                  onClick={() => setOverrideOpen(true)}
                >
                  change
                </button>
              </p>
            ) : null}
            {couldNotDetect ? (
              <p className="mt-2 text-caption text-text-tertiary">Could not detect — please specify</p>
            ) : null}
          </div>

          {overrideOpen ? (
            <div className="grid gap-4 rounded-md border border-border-subtle bg-surface-input p-4">
              <div>
                <Label htmlFor="credential-service" className="text-micro uppercase tracking-[0.06em] text-text-secondary">
                  SERVICE
                </Label>
                <Input
                  id="credential-service"
                  className="mt-2"
                  value={serviceOverride}
                  placeholder="anthropic"
                  onChange={(e) => setServiceOverride(e.target.value)}
                />
              </div>
              <div>
                <p className="text-micro uppercase tracking-[0.06em] text-text-secondary">KIND</p>
                <div className="mt-2 grid grid-cols-3 rounded-sm border border-border">
                  {(["llm", "tool", "custom"] as const).map((kind) => (
                    <button
                      key={kind}
                      type="button"
                      className={cn(
                        "border-r border-border px-3 py-2 text-micro uppercase tracking-[0.06em] transition-colors last:border-r-0",
                        kindOverride === kind
                          ? "bg-neutral-100 text-text-inverse"
                          : "bg-transparent text-text-secondary hover:bg-surface-elevated hover:text-text-primary",
                      )}
                      onClick={() => setKindOverride(kind)}
                    >
                      {kind}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : null}

          <div className="pt-2">
            {submitError ? <p className="mb-3 text-caption text-status-denied-fg">{submitError}</p> : null}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={close}>
                Cancel
              </Button>
              <Button type="submit" disabled={!canSubmit}>
                {submitting ? "Adding…" : "Add credential"}
              </Button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
