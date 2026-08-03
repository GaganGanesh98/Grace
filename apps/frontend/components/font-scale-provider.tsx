"use client";

import { usePathname } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";

import {
  FONT_SCALE_LS_KEY,
  FONT_SCALE_OPTIONS,
  readFontScaleFromStorage,
  type FontScaleValue,
} from "@/lib/axiom-storage";

type FontScaleContextValue = {
  scale: FontScaleValue;
  setScale: (s: FontScaleValue) => void;
  options: typeof FONT_SCALE_OPTIONS;
};

const FontScaleContext = createContext<FontScaleContextValue | null>(null);

export function FontScaleProvider({ children }: { children: ReactNode }): ReactElement {
  const pathname = usePathname();
  const [scale, setScaleState] = useState<FontScaleValue>(1.0);

  useEffect(() => {
    const s = readFontScaleFromStorage();
    setScaleState(s);
    if (typeof document !== "undefined") {
      document.documentElement.style.setProperty("--axiom-font-scale", String(s));
    }
  }, []);

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }
    document.documentElement.style.setProperty("--axiom-font-scale", String(scale));
    const dash = document.querySelector("[data-axiom-dashboard]");
    if (dash instanceof HTMLElement) {
      dash.style.setProperty("--axiom-font-scale", String(scale));
    }
    try {
      window.localStorage.setItem(FONT_SCALE_LS_KEY, String(scale));
    } catch {
      /* ignore */
    }
  }, [scale, pathname]);

  const setScale = useCallback((s: FontScaleValue) => {
    setScaleState(s);
  }, []);

  const value = useMemo(
    () => ({ scale, setScale, options: FONT_SCALE_OPTIONS }),
    [scale, setScale],
  );

  return <FontScaleContext.Provider value={value}>{children}</FontScaleContext.Provider>;
}

export function useFontScale(): FontScaleContextValue {
  const ctx = useContext(FontScaleContext);
  if (!ctx) {
    throw new Error("useFontScale must be used within FontScaleProvider");
  }
  return ctx;
}
