"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useSyncExternalStore, type ReactElement } from "react";

import { Button } from "@/components/ui/button";

const noopSubscribe = (): (() => void) => () => {};

/** Midnight ⇄ Daylight. next-themes owns persistence and the `.dark` class on <html>. */
export function ThemeToggle(): ReactElement {
  const { resolvedTheme, setTheme } = useTheme();
  // The theme is unknown during SSR; render the Midnight icon on the server
  // and first client pass so hydration matches, then the real one.
  const hydrated = useSyncExternalStore(noopSubscribe, () => true, () => false);

  const dark = !hydrated || resolvedTheme !== "light";
  const label = dark ? "Switch to Daylight theme" : "Switch to Midnight theme";
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      aria-label={label}
      title={label}
      onClick={() => setTheme(dark ? "light" : "dark")}
    >
      {dark ? <Sun aria-hidden /> : <Moon aria-hidden />}
    </Button>
  );
}
