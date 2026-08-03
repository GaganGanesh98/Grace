"use client";

import { KeyRound } from "lucide-react";
import { type ReactElement } from "react";

import { Button } from "@/components/ui/button";

type EmptyStateProps = {
  onAddCredential: () => void;
};

export function VaultEmptyState({ onAddCredential }: EmptyStateProps): ReactElement {
  return (
    <div className="mx-auto flex max-w-[480px] flex-col items-center pt-24 text-center">
      <KeyRound className="h-12 w-12 text-text-tertiary" aria-hidden />
      <h2 className="mt-6 text-section text-text-primary">No credentials yet</h2>
      <p className="mt-2 text-body leading-[1.5] text-text-secondary">
        Add an LLM provider key or tool credential
        <br />
        to enable agent runs
      </p>
      <Button type="button" className="mt-6" onClick={onAddCredential}>
        Add credential
      </Button>
    </div>
  );
}
