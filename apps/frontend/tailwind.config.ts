import type { Config } from "tailwindcss";
import tailwindcssAnimate from "tailwindcss-animate";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      ringWidth: {
        3: "3px",
      },
      colors: {
        border: "var(--border)",
        input: "var(--input)",
        ring: "var(--ring)",
        background: "var(--background)",
        foreground: "var(--foreground)",
        primary: {
          DEFAULT: "var(--primary)",
          foreground: "var(--primary-foreground)",
        },
        secondary: {
          DEFAULT: "var(--secondary)",
          foreground: "var(--secondary-foreground)",
        },
        destructive: {
          DEFAULT: "var(--destructive)",
          foreground: "var(--destructive-foreground)",
        },
        muted: {
          DEFAULT: "var(--muted)",
          foreground: "var(--muted-foreground)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          foreground: "var(--accent-foreground)",
        },
        popover: {
          DEFAULT: "var(--popover)",
          foreground: "var(--popover-foreground)",
        },
        card: {
          DEFAULT: "var(--card)",
          foreground: "var(--card-foreground)",
        },
        surface: {
          page: "var(--surface-page)",
          chrome: "var(--surface-chrome)",
          card: "var(--surface-card)",
          elevated: "var(--surface-elevated)",
          input: "var(--surface-input)",
        },
        neutral: {
          100: "var(--neutral-100)",
          200: "var(--neutral-200)",
          400: "var(--neutral-400)",
          500: "var(--neutral-500)",
          600: "var(--neutral-600)",
          700: "var(--neutral-700)",
          800: "var(--neutral-800)",
          900: "var(--neutral-900)",
        },
        text: {
          primary: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          tertiary: "var(--text-tertiary)",
          disabled: "var(--text-disabled)",
          inverse: "var(--text-inverse)",
        },
        cyan: {
          400: "var(--cyan-400)",
        },
        status: {
          denied: {
            fg: "var(--status-denied-fg)",
            border: "var(--status-denied-border)",
            bg: "var(--status-denied-bg)",
          },
          held: {
            fg: "var(--status-held-fg)",
            border: "var(--status-held-border)",
            bg: "var(--status-held-bg)",
          },
          ok: {
            fg: "var(--status-ok-fg)",
            border: "var(--status-ok-border)",
            bg: "var(--status-ok-bg)",
          },
          neutral: {
            fg: "var(--status-neutral-fg)",
            border: "var(--status-neutral-border)",
            bg: "var(--status-neutral-bg)",
          },
          info: {
            fg: "var(--status-info-fg)",
            border: "var(--status-info-border)",
            bg: "var(--status-info-bg)",
          },
        },
      },
      fontFamily: {
        sans: "var(--font-sans)",
        mono: "var(--font-mono)",
      },
      borderRadius: {
        none: "var(--radius-none)",
        xs: "var(--radius-xs)",
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        pill: "var(--radius-pill)",
      },
      fontSize: {
        display: ["28px", { lineHeight: "1.15", letterSpacing: "-0.015em", fontWeight: "600" }],
        section: ["20px", { lineHeight: "1.25", letterSpacing: "-0.01em", fontWeight: "600" }],
        heading: ["16px", { lineHeight: "1.3", letterSpacing: "-0.005em", fontWeight: "600" }],
        "body-l": ["14px", { lineHeight: "1.5", fontWeight: "500" }],
        body: ["13px", { lineHeight: "1.5" }],
        "body-s": ["12px", { lineHeight: "1.45" }],
        caption: ["12px", { lineHeight: "1.4", letterSpacing: "0.005em", fontWeight: "500" }],
        micro: ["11px", { lineHeight: "1.3", letterSpacing: "0.06em", fontWeight: "600" }],
        "mono-body": ["13px", { lineHeight: "1.5" }],
        "mono-caption": ["12px", { lineHeight: "1.4" }],
        "axiom-10": ["calc(10px * var(--grace-font-scale, 1))", { lineHeight: "1.25" }],
        "axiom-11": ["calc(11px * var(--grace-font-scale, 1))", { lineHeight: "1.25" }],
        "axiom-12": ["calc(12px * var(--grace-font-scale, 1))", { lineHeight: "1.25" }],
        "axiom-13": ["calc(13px * var(--grace-font-scale, 1))", { lineHeight: "1.4" }],
        "axiom-14": ["calc(14px * var(--grace-font-scale, 1))", { lineHeight: "1.45" }],
        "axiom-15": ["calc(15px * var(--grace-font-scale, 1))", { lineHeight: "1.5" }],
        "axiom-16": ["calc(16px * var(--grace-font-scale, 1))", { lineHeight: "1.5" }],
        "axiom-18": ["calc(18px * var(--grace-font-scale, 1))", { lineHeight: "1.4" }],
        "axiom-20": ["calc(20px * var(--grace-font-scale, 1))", { lineHeight: "1.35" }],
        "axiom-22": ["calc(22px * var(--grace-font-scale, 1))", { lineHeight: "1.35" }],
        "axiom-24": ["calc(24px * var(--grace-font-scale, 1))", { lineHeight: "1.3" }],
        "axiom-28": ["calc(28px * var(--grace-font-scale, 1))", { lineHeight: "1.2" }],
      },
      transitionDuration: {
        instant: "var(--motion-instant)",
        fast: "var(--motion-fast)",
        base: "var(--motion-base)",
        slow: "var(--motion-slow)",
      },
      transitionTimingFunction: {
        default: "var(--ease-default)",
        out: "var(--ease-out)",
        in: "var(--ease-in)",
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
      },
    },
  },
  plugins: [tailwindcssAnimate],
};

export default config;
