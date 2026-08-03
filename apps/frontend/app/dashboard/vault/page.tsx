"use client";

import { MoreHorizontal } from "lucide-react";
import { type ReactElement, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { AddCredentialModal } from "@/components/vault/add-credential-modal";
import { VaultEmptyState } from "@/components/vault/empty-state";
import {
  deactivateVaultKey,
  deleteVaultKey,
  listVaultKeys,
  type VaultKey,
  type VaultKind,
} from "@/lib/vault-api";
import { cn } from "@/lib/utils";

type KindFilter = "all" | "llm" | "tool";

const FILTERS: Array<{ id: KindFilter; label: string }> = [
  { id: "all", label: "All" },
  { id: "llm", label: "LLM" },
  { id: "tool", label: "Tool" },
];

function formatRelativeTime(value: string): string {
  const then = new Date(value).getTime();
  const now = Date.now();
  const seconds = Math.max(0, Math.round((now - then) / 1000));
  if (seconds < 60) {
    return "now";
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes}m ago`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours}h ago`;
  }
  const days = Math.floor(hours / 24);
  return `${days} ${days === 1 ? "day" : "days"} ago`;
}

function formatKeyPreview(row: VaultKey): string {
  const prefix = row.key_prefix.replace(/\.+$/g, "");
  const suffix = row.key_suffix.replace(/^\.+/g, "");
  return `${prefix}…${suffix}`;
}

function KindPill({ kind }: { kind: VaultKind }): ReactElement {
  const info = kind === "llm";
  return (
    <span
      className={cn(
        "inline-flex min-w-16 items-center gap-1.5 rounded-xs border px-2 py-0.5 text-micro uppercase tracking-[0.06em]",
        info
          ? "border-status-info-border bg-status-info-bg text-status-info-fg"
          : "border-status-neutral-border bg-status-neutral-bg text-status-neutral-fg",
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-pill", info ? "bg-status-info-fg" : "bg-status-neutral-fg")} />
      {kind}
    </span>
  );
}

function RowActions({
  row,
  onDeactivate,
  onDelete,
}: {
  row: VaultKey;
  onDeactivate: (keyId: string) => Promise<void>;
  onDelete: (keyId: string) => Promise<void>;
}): ReactElement {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDocClick(e: MouseEvent): void {
      if (!ref.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  return (
    <div ref={ref} className="relative flex justify-end">
      <button
        type="button"
        aria-label={`Actions for ${row.name}`}
        className="flex h-7 w-7 items-center justify-center rounded-sm text-text-secondary transition-colors duration-fast hover:bg-surface-elevated hover:text-text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-neutral-100 focus-visible:outline-offset-2"
        onClick={() => setOpen((value) => !value)}
      >
        <MoreHorizontal className="h-4 w-4" aria-hidden />
      </button>
      {open ? (
        <div className="absolute right-0 top-8 z-20 w-36 rounded-md border border-border-subtle bg-surface-card py-1 shadow-sm">
          <button
            type="button"
            disabled
            title="Coming in v0.9"
            className="block w-full px-3 py-2 text-left text-body-s text-text-disabled"
          >
            Rotate
          </button>
          <button
            type="button"
            className="block w-full px-3 py-2 text-left text-body-s text-text-secondary hover:bg-surface-elevated hover:text-text-primary"
            onClick={() => {
              setOpen(false);
              void onDeactivate(row.id);
            }}
          >
            Deactivate
          </button>
          <button
            type="button"
            className="block w-full px-3 py-2 text-left text-body-s text-status-denied-fg hover:bg-status-denied-bg"
            onClick={() => {
              setOpen(false);
              if (window.confirm(`Delete ${row.name}?`)) {
                void onDelete(row.id);
              }
            }}
          >
            Delete
          </button>
        </div>
      ) : null}
    </div>
  );
}

export default function DashboardVaultIndexPage(): ReactElement {
  const [keys, setKeys] = useState<VaultKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [filter, setFilter] = useState<KindFilter>("all");
  const [search, setSearch] = useState("");

  async function loadKeys(): Promise<void> {
    setError(null);
    try {
      const rows = await listVaultKeys();
      setKeys(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load vault");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadKeys();
  }, []);

  const visibleKeys = useMemo(() => {
    const q = search.trim().toLowerCase();
    return keys.filter((row) => {
      const kindOk = filter === "all" || row.kind === filter;
      const searchOk = !q || row.name.toLowerCase().includes(q);
      return kindOk && searchOk;
    });
  }, [filter, keys, search]);

  async function deactivate(keyId: string): Promise<void> {
    try {
      const updated = await deactivateVaultKey(keyId);
      setKeys((rows) => rows.map((row) => (row.id === keyId ? updated : row)));
      toast.success("Credential deactivated");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Deactivate failed");
    }
  }

  async function remove(keyId: string): Promise<void> {
    try {
      await deleteVaultKey(keyId);
      setKeys((rows) => rows.filter((row) => row.id !== keyId));
      toast.success("Credential deleted");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    }
  }

  return (
    <div className="min-h-full px-8 pt-6">
      <div className="flex items-start justify-between gap-6">
        <div>
          <h1 className="text-display text-text-primary">Vault</h1>
          <p className="mt-1 text-body text-text-secondary">
            Encrypted credentials for LLM providers and tools. Auto-detected on add.
          </p>
        </div>
        <Button type="button" onClick={() => setModalOpen(true)}>
          Add credential
        </Button>
      </div>

      <div className="mt-6 flex items-end justify-between gap-4">
        <div className="flex gap-4" role="tablist" aria-label="Vault credential type">
          {FILTERS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={filter === item.id}
              className={cn(
                "border-b-2 px-0 pb-3 pt-2 text-body font-medium transition-colors duration-fast",
                filter === item.id
                  ? "border-text-primary font-semibold text-text-primary"
                  : "border-transparent text-text-secondary hover:border-border hover:text-text-primary",
              )}
              onClick={() => setFilter(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <input
          type="search"
          aria-label="Search credentials"
          placeholder="Search by name…"
          className="h-8 w-[240px] rounded-sm border border-border bg-surface-input px-3 text-body text-text-primary placeholder:text-text-tertiary transition-colors duration-fast hover:border-border-strong focus-visible:outline focus-visible:outline-2 focus-visible:outline-neutral-100 focus-visible:outline-offset-2"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <main className="mt-6">
        {error ? <p className="text-body text-status-denied-fg">{error}</p> : null}
        {loading ? (
          <div className="rounded-md border border-border-subtle bg-surface-card">
            <div className="h-8 bg-surface-elevated" />
            {[0, 1, 2].map((row) => (
              <div key={row} className="h-9 animate-pulse border-t border-border-subtle px-4 py-2">
                <div className="h-3 w-full max-w-[520px] rounded-sm bg-surface-elevated" />
              </div>
            ))}
          </div>
        ) : keys.length === 0 ? (
          <VaultEmptyState onAddCredential={() => setModalOpen(true)} />
        ) : (
          <div className="overflow-visible rounded-md border border-border-subtle bg-surface-card">
            <table className="w-full table-fixed border-collapse">
              <thead>
                <tr className="h-8 bg-surface-elevated text-left text-micro uppercase tracking-[0.06em] text-text-secondary">
                  <th className="w-6 px-4 font-semibold"> </th>
                  <th className="min-w-[200px] px-4 font-semibold">Name</th>
                  <th className="w-20 px-4 font-semibold">Type</th>
                  <th className="w-[120px] px-4 font-semibold">Service</th>
                  <th className="w-40 px-4 font-semibold">Key preview</th>
                  <th className="w-[100px] px-4 font-semibold">Created</th>
                  <th className="w-10 px-2 font-semibold"> </th>
                </tr>
              </thead>
              <tbody>
                {visibleKeys.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="h-20 px-4 text-body text-text-secondary">
                      No matching credentials.
                    </td>
                  </tr>
                ) : (
                  visibleKeys.map((row) => (
                    <tr
                      key={row.id}
                      className="h-9 border-b border-border-subtle text-body transition-colors duration-instant last:border-b-0 hover:bg-surface-elevated"
                    >
                      <td className="px-4">
                        <span
                          className={cn(
                            "block h-1.5 w-1.5 rounded-pill",
                            row.is_active ? "bg-status-ok-fg" : "bg-text-tertiary",
                          )}
                          aria-label={row.is_active ? "Active" : "Inactive"}
                        />
                      </td>
                      <td className="min-w-[200px] truncate px-4 font-medium text-text-primary">{row.name}</td>
                      <td className="px-4">
                        <KindPill kind={row.kind} />
                      </td>
                      <td className="truncate px-4 font-mono text-body-s text-text-secondary">{row.service}</td>
                      <td className="truncate px-4 font-mono text-mono-caption text-text-tertiary [font-variant-numeric:tabular-nums]">
                        {formatKeyPreview(row)}
                      </td>
                      <td className="px-4 text-body-s text-text-secondary [font-variant-numeric:tabular-nums]">
                        {formatRelativeTime(row.created_at)}
                      </td>
                      <td className="px-2">
                        <RowActions row={row} onDeactivate={deactivate} onDelete={remove} />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </main>

      <AddCredentialModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={() => {
          setLoading(true);
          void loadKeys();
        }}
      />
    </div>
  );
}
