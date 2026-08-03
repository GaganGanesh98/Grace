"use client";

import { type ReactElement } from "react";

import { useFontScale } from "@/components/font-scale-provider";
import { Button } from "@/components/ui/button";
import { type FontScaleValue } from "@/lib/axiom-storage";
import { cn } from "@/lib/utils";

export default function SettingsPage(): ReactElement {
  const { scale, setScale, options } = useFontScale();

  return (
    <div className="space-y-12">
      <header>
        <h1 className="text-axiom-24 font-medium text-[#F0F2F8]">Settings</h1>
        <p className="mt-2 text-axiom-15 text-[#A0A8BC]">Display preferences</p>
      </header>

      <section className="space-y-4">
        <h2 className="font-mono text-axiom-16 font-medium uppercase tracking-[1px] text-[#F0F2F8]">
          Font size
        </h2>
        <div>
          <div className="mb-2 text-axiom-15 text-[#A0A8BC]">Choose a comfortable reading size for the dashboard.</div>
          <div className="flex flex-wrap gap-2">
            {options.map((o) => (
              <Button
                key={o.value}
                type="button"
                variant={scale === o.value ? "primary" : "secondary"}
                className={cn(
                  scale === o.value &&
                    "border-text-primary bg-surface-elevated text-text-primary hover:border-text-primary hover:bg-surface-elevated hover:text-text-primary",
                )}
                onClick={() => {
                  setScale(o.value as FontScaleValue);
                }}
              >
                {o.label}
              </Button>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
