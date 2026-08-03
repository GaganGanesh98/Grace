"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import type { ReactElement } from "react";
import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DEFAULT_AGENT_TOOLS_CONFIG } from "@/lib/default-agent-tools";
import type { VaultKey } from "@/lib/vault-api";

const schema = z.object({
  name: z.string().min(1),
  model: z.string().min(1),
  vault_key_id: z.string().uuid(),
  system_prompt: z.string().min(1),
});

type FormValues = z.infer<typeof schema>;

type AgentFormProps = {
  vaultKeys: VaultKey[];
  onSubmit: (values: Record<string, unknown>) => Promise<void>;
  isSubmitting: boolean;
  submitError: string | null;
};

export function AgentForm({
  vaultKeys,
  onSubmit,
  isSubmitting,
  submitError,
}: AgentFormProps): ReactElement {
  const {
    control,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "",
      model: "groq/llama-3.3-70b-versatile",
      vault_key_id: "",
      system_prompt: "You are a helpful assistant.",
    },
  });

  useEffect(() => {
    const id = vaultKeys[0]?.id;
    if (id) {
      setValue("vault_key_id", id, { shouldValidate: true });
    }
  }, [vaultKeys, setValue]);

  return (
    <form
      className="space-y-4 rounded-lg border border-[rgba(255,255,255,0.08)] bg-[#0A0A14] p-6"
      onSubmit={handleSubmit(async (vals) => {
        const vk = vaultKeys.find((x) => x.id === vals.vault_key_id);
        const unsupported = vk && !["openai", "anthropic", "google", "groq", "xai"].includes(vk.service);
        if (unsupported) {
          return;
        }
        await onSubmit({
          name: vals.name,
          model: vals.model,
          vault_key_id: vals.vault_key_id,
          system_prompt: vals.system_prompt,
          tools_config: DEFAULT_AGENT_TOOLS_CONFIG,
        });
      })}
    >
      {vaultKeys.length === 0 ? (
        <p className="text-axiom-14 text-amber-400">
          No LLM credentials in vault.{" "}
          <Link href="/dashboard/vault" className="border-b border-border-strong text-text-secondary">
            Add one in Vault →
          </Link>
        </p>
      ) : null}

      <div>
        <Label className="font-mono text-axiom-11 uppercase text-[#6B7490]">Name</Label>
        <Controller
          name="name"
          control={control}
          render={({ field }) => (
            <Input {...field} className="mt-1 border-[rgba(255,255,255,0.1)] bg-[#080810]" />
          )}
        />
        {errors.name ? <p className="mt-1 text-axiom-13 text-red-400">{errors.name.message}</p> : null}
      </div>

      <div>
        <Label className="font-mono text-axiom-11 uppercase text-[#6B7490]">Model</Label>
        <Controller
          name="model"
          control={control}
          render={({ field }) => (
            <Input {...field} className="mt-1 border-[rgba(255,255,255,0.1)] bg-[#080810]" />
          )}
        />
      </div>

      <div>
        <Label className="font-mono text-axiom-11 uppercase text-[#6B7490]">Vault key</Label>
        <Controller
          name="vault_key_id"
          control={control}
          render={({ field }) => (
            <select
              {...field}
              className="mt-1 w-full rounded-md border border-[rgba(255,255,255,0.1)] bg-[#080810] px-3 py-2 font-mono text-axiom-14 text-[#F0F2F8]"
            >
              {vaultKeys.map((k) => (
                <option key={k.id} value={k.id}>
                  {k.name} ({k.service}) {k.key_prefix}…{k.key_suffix}
                </option>
              ))}
            </select>
          )}
        />
        {errors.vault_key_id ? (
          <p className="mt-1 text-axiom-13 text-red-400">{errors.vault_key_id.message}</p>
        ) : null}
      </div>

      <div>
        <Label className="font-mono text-axiom-11 uppercase text-[#6B7490]">System prompt</Label>
        <Controller
          name="system_prompt"
          control={control}
          render={({ field }) => (
            <textarea
              {...field}
              rows={4}
              className="mt-1 w-full rounded-md border border-[rgba(255,255,255,0.1)] bg-[#080810] px-3 py-2 text-axiom-14 text-[#F0F2F8]"
            />
          )}
        />
      </div>

      <p className="font-mono text-axiom-11 uppercase text-[#6B7490]">
        Tools bundled: http_fetch, web_search, file_write (Phase 6.5 default)
      </p>

      {submitError ? <p className="text-axiom-14 text-red-400">{submitError}</p> : null}

      <Button
        type="submit"
        className="bg-neutral-100 text-text-inverse hover:bg-white"
        disabled={isSubmitting || vaultKeys.length === 0}
      >
        Create agent
      </Button>
    </form>
  );
}
