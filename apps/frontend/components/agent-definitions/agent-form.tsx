"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import type { ReactElement } from "react";
import { useEffect, useRef, useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DEFAULT_AGENT_TOOLS_CONFIG } from "@/lib/default-agent-tools";
import {
  isSupportedLlmService,
  modelProviderMismatchMessage,
  modelProviderPrefix,
  qualifyModel,
  unsupportedServiceMessage,
} from "@/lib/llm-providers";
import type { LlmProvider } from "@/lib/providers-api";
import type { VaultKey } from "@/lib/vault-api";

const schema = z.object({
  name: z.string().min(1, "Name is required"),
  model: z.string().min(1, "Model is required"),
  vault_key_id: z.string().uuid("Select an LLM credential."),
  system_prompt: z.string().min(1, "System prompt is required"),
});

type FormValues = z.infer<typeof schema>;

type AgentFormProps = {
  vaultKeys: VaultKey[];
  /** Provider catalog from the backend registry; empty falls back to free-text model entry. */
  providers?: LlmProvider[];
  onSubmit: (values: Record<string, unknown>) => Promise<void>;
  isSubmitting: boolean;
  submitError: string | null;
};

const EMPTY_VAULT_HINT_ID = "agent-form-empty-vault";
const CUSTOM_MODEL = "__custom__";

export function AgentForm({
  vaultKeys,
  providers = [],
  onSubmit,
  isSubmitting,
  submitError,
}: AgentFormProps): ReactElement {
  const {
    control,
    getValues,
    handleSubmit,
    setError,
    setValue,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "",
      model: "",
      vault_key_id: "",
      system_prompt: "You are a helpful assistant.",
    },
  });

  const [customModel, setCustomModel] = useState(false);
  const hasKeys = vaultKeys.length > 0;

  // Pick a sensible default, but never clobber a selection the user still can use —
  // the list re-renders whenever a credential is added mid-form.
  useEffect(() => {
    const current = getValues("vault_key_id");
    if (vaultKeys.some((k) => k.id === current && isSupportedLlmService(k.service))) {
      return;
    }
    const id = vaultKeys.find((k) => isSupportedLlmService(k.service))?.id ?? vaultKeys[0]?.id;
    if (id) {
      setValue("vault_key_id", id, { shouldValidate: true });
    }
  }, [vaultKeys, getValues, setValue]);

  const selectedKeyId = useWatch({ control, name: "vault_key_id" });
  const modelValue = useWatch({ control, name: "model" });
  const selectedKey = vaultKeys.find((k) => k.id === selectedKeyId) ?? null;
  const provider = selectedKey
    ? (providers.find((p) => p.service === selectedKey.service) ?? null)
    : null;
  const modelOptions = provider ? provider.models.map((m) => qualifyModel(provider.service, m)) : [];

  // Switching credentials must not leave a model string aimed at the old provider.
  const appliedKeyRef = useRef<string | null>(null);
  useEffect(() => {
    if (!provider || !selectedKeyId || appliedKeyRef.current === selectedKeyId) {
      return;
    }
    appliedKeyRef.current = selectedKeyId;
    if (provider.default_model) {
      setValue("model", qualifyModel(provider.service, provider.default_model));
      setCustomModel(false);
    }
  }, [provider, selectedKeyId, setValue]);

  const valueInCatalog = modelOptions.includes(modelValue ?? "");
  const useCustomModel = modelOptions.length === 0 || customModel || !valueInCatalog;
  const modelSelectValue = valueInCatalog && !customModel ? modelValue : CUSTOM_MODEL;

  return (
    <form
      className="space-y-4 rounded-lg border border-[rgba(255,255,255,0.08)] bg-[#0b0c0e] p-6"
      onSubmit={handleSubmit(async (vals) => {
        const vk = vaultKeys.find((x) => x.id === vals.vault_key_id);
        if (!vk) {
          setError("vault_key_id", {
            type: "manual",
            message: "That credential is no longer in your vault. Pick another one.",
          });
          return;
        }
        if (!isSupportedLlmService(vk.service)) {
          setError("vault_key_id", {
            type: "manual",
            message: unsupportedServiceMessage(vk.name, vk.service),
          });
          return;
        }
        const prefix = modelProviderPrefix(vals.model);
        if (prefix && prefix !== vk.service.toLowerCase()) {
          setError("model", {
            type: "manual",
            message: modelProviderMismatchMessage(vals.model, prefix, vk.service),
          });
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
      {hasKeys ? null : (
        <p id={EMPTY_VAULT_HINT_ID} className="text-axiom-14 text-amber-400" role="status">
          No LLM credentials in vault.{" "}
          <Link href="/dashboard/vault" className="border-b border-border-strong text-text-secondary">
            Add one in Vault →
          </Link>
        </p>
      )}

      <div>
        <Label htmlFor="agent-name" className="font-mono text-axiom-11 uppercase text-[#82878f]">
          Name
        </Label>
        <Controller
          name="name"
          control={control}
          render={({ field }) => (
            <Input {...field} id="agent-name" className="mt-1 border-[rgba(255,255,255,0.1)] bg-[#08090b]" />
          )}
        />
        {errors.name ? <p className="mt-1 text-axiom-13 text-red-400">{errors.name.message}</p> : null}
      </div>

      <div>
        <Label htmlFor="agent-vault-key" className="font-mono text-axiom-11 uppercase text-[#82878f]">
          Vault key
        </Label>
        <Controller
          name="vault_key_id"
          control={control}
          render={({ field }) => (
            <select
              {...field}
              id="agent-vault-key"
              disabled={!hasKeys}
              aria-invalid={Boolean(errors.vault_key_id)}
              className="mt-1 w-full rounded-md border border-[rgba(255,255,255,0.1)] bg-[#08090b] px-3 py-2 font-mono text-axiom-14 text-[#ecedef] disabled:opacity-60"
            >
              {hasKeys ? null : <option value="">No LLM credentials in vault</option>}
              {vaultKeys.map((k) => (
                <option key={k.id} value={k.id}>
                  {k.name} ({k.service}){isSupportedLlmService(k.service) ? "" : " — not supported"}{" "}
                  {k.key_prefix}…{k.key_suffix}
                </option>
              ))}
            </select>
          )}
        />
        {errors.vault_key_id ? (
          <p className="mt-1 text-axiom-13 text-red-400" role="alert">
            {errors.vault_key_id.message}
          </p>
        ) : null}
      </div>

      <div>
        <Label htmlFor="agent-model" className="font-mono text-axiom-11 uppercase text-[#82878f]">
          Model
        </Label>
        {modelOptions.length > 0 ? (
          <select
            id="agent-model"
            value={modelSelectValue}
            aria-invalid={Boolean(errors.model)}
            className="mt-1 w-full rounded-md border border-[rgba(255,255,255,0.1)] bg-[#08090b] px-3 py-2 font-mono text-axiom-14 text-[#ecedef]"
            onChange={(e) => {
              if (e.target.value === CUSTOM_MODEL) {
                setCustomModel(true);
                return;
              }
              setCustomModel(false);
              setValue("model", e.target.value, { shouldValidate: true });
            }}
          >
            {modelOptions.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
            <option value={CUSTOM_MODEL}>Custom model…</option>
          </select>
        ) : null}
        {useCustomModel ? (
          <Controller
            name="model"
            control={control}
            render={({ field }) => (
              <>
                {modelOptions.length > 0 ? (
                  <Label htmlFor="agent-model-custom" className="sr-only">
                    Custom model id
                  </Label>
                ) : null}
                <Input
                  {...field}
                  id={modelOptions.length > 0 ? "agent-model-custom" : "agent-model"}
                  placeholder={selectedKey ? `${selectedKey.service}/model-id` : "provider/model-id"}
                  className="mt-1 border-[rgba(255,255,255,0.1)] bg-[#08090b]"
                />
              </>
            )}
          />
        ) : null}
        <p className="mt-1 text-axiom-11 text-[#82878f]">
          {provider
            ? `Models for ${provider.label}. The provider prefix is stripped before the call.`
            : "Use provider/model-id — the provider prefix must match the selected credential."}
        </p>
        {errors.model ? (
          <p className="mt-1 text-axiom-13 text-red-400" role="alert">
            {errors.model.message}
          </p>
        ) : null}
      </div>

      <div>
        <Label htmlFor="agent-system-prompt" className="font-mono text-axiom-11 uppercase text-[#82878f]">
          System prompt
        </Label>
        <Controller
          name="system_prompt"
          control={control}
          render={({ field }) => (
            <textarea
              {...field}
              id="agent-system-prompt"
              rows={4}
              className="mt-1 w-full rounded-md border border-[rgba(255,255,255,0.1)] bg-[#08090b] px-3 py-2 text-axiom-14 text-[#ecedef]"
            />
          )}
        />
        {errors.system_prompt ? (
          <p className="mt-1 text-axiom-13 text-red-400">{errors.system_prompt.message}</p>
        ) : null}
      </div>

      <p className="font-mono text-axiom-11 uppercase text-[#82878f]">
        Tools bundled: http_fetch, web_search, file_write (Phase 6.5 default)
      </p>

      {submitError ? <p className="text-axiom-14 text-red-400">{submitError}</p> : null}

      <Button
        type="submit"
        className="bg-neutral-100 text-text-inverse hover:bg-white"
        disabled={isSubmitting || !hasKeys}
        title={hasKeys ? undefined : "Add an LLM provider credential to your vault first."}
        aria-describedby={hasKeys ? undefined : EMPTY_VAULT_HINT_ID}
      >
        Create agent
      </Button>
    </form>
  );
}
