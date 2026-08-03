"use client";

import { Check, Copy } from "lucide-react";
import { useState, type ReactElement } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function ApiKeyDisplay({
  prefix,
  className,
}: {
  /** e.g. axm_live_ */
  prefix: string;
  className?: string;
}): ReactElement {
  const [copied, setCopied] = useState(false);
  const masked = `${prefix}•••••••`;

  async function copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(masked);
      setCopied(true);
      toast.success("Masked key copied");
      setTimeout(() => {
        setCopied(false);
      }, 2000);
    } catch {
      toast.error("Could not copy");
    }
  }

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <code className="font-mono text-axiom-13 text-[#A0A8BC]">{masked}</code>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        className="h-8 min-h-8 border-border"
        onClick={() => void copy()}
      >
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      </Button>
    </div>
  );
}
