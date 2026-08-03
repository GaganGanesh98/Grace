# AXIOM Design Tokens

**Status:** v1 — locked at Phase 7.7 boundary
**Calibration:** Enterprise / institutional infrastructure tool
**Reference points:** IBM Carbon (G100 dark theme), Bloomberg Terminal, Atlassian dark mode, Datadog, Splunk
**Stack:** Next.js 14 + Tailwind + shadcn/ui + TypeScript

This is the single source of truth for every color, type ramp, spacing value, radius, and motion duration shipped in AXIOM's frontend. All component code (existing and v0-generated) must reference these tokens — never hardcoded hex values, never ad-hoc pixel sizes.

The bottom of this file contains a compressed **v0 prompt prefix** to paste before every v0.app generation request. That's how the system stays coherent across screens.

---

## 1. Foundation principles

These are the calibration choices that distinguish AXIOM's UI from a startup developer tool. Every token below derives from these.

1. **Restraint over expression.** Color is punctuation, not paint. The default state of every surface is grayscale-on-navy. Color appears only where it carries semantic weight (a verdict, a live signal, a focus state). If a button is colored "because it looks nice," it is wrong.
2. **Borders over shadows.** Institutional UIs delineate structure with visible 1px borders, not floating drop-shadows. Cards have edges. Tables have dividers. Sections are clearly bounded.
3. **Density is the premium signal.** Tables ship at 36px row height. Body copy is 13px. Metadata is 12px. The dashboard packs more truth per pixel than its consumer-grade competitors. This is the inverse of Stripe-tier whitespace generosity — and it is what CISOs and reliability engineers actually want.
4. **Square geometry.** Border radii are small (4–6px). Pills are slightly rounded, not fully circular. Square reads as serious infrastructure; rounded reads as consumer SaaS.
5. **Motion serves comprehension, not delight.** No spring easings, no streaming pulses, no scaling on hover. Transitions are color/border/opacity only, 100–150ms. The UI never performs.
6. **Numerals are sacred.** `font-variant-numeric: tabular-nums` on every numeric column, timestamp, count, and percentage. Digits never jiggle as values change.
7. **Cyan is reserved.** The brand cyan `#22d3ee` survives in exactly one role: the **live signal indicator** (SSE connection dot, streaming status). It does not appear on buttons, active tabs, focused inputs, brand emphasis, or anywhere decorative. Active states default to white or muted blue.

---

## 2. Color tokens

### 2.1 Surfaces (navy substrate, preserved from current build)

| Token | Hex | Use |
|---|---|---|
| `--surface-page` | `#0a1628` | Main page background |
| `--surface-chrome` | `#070f1c` | Sidebar, top nav, deeper UI chrome |
| `--surface-card` | `#0f1d2e` | Cards, modal bodies, panel containers |
| `--surface-elevated` | `#16263a` | Hover/active row states inside cards and tables |
| `--surface-input` | `#0c1a2a` | Text inputs, selects, search bars |
| `--surface-overlay` | `rgba(7, 15, 28, 0.88)` | Modal backdrops |
| `--surface-code` | `#0a1421` | Inline code blocks, JSON viewers |

### 2.2 Neutral grays (Carbon-derived, for content layered on the navy)

These are cool grays that compose with the navy substrate. Used for borders, text, neutral chrome elements.

| Token | Hex | Use |
|---|---|---|
| `--neutral-100` | `#e8ebf0` | High-contrast text on navy |
| `--neutral-200` | `#c6cdd6` | Secondary text |
| `--neutral-400` | `#8b95a3` | Tertiary text, metadata |
| `--neutral-500` | `#6b7585` | Disabled text, deemphasized labels |
| `--neutral-600` | `#4d5667` | Strong borders, dividers |
| `--neutral-700` | `#363e4d` | Default borders |
| `--neutral-800` | `#242a36` | Subtle borders |
| `--neutral-900` | `#161b24` | Background tints, deep panel surfaces |

### 2.3 Borders

| Token | Hex | Use |
|---|---|---|
| `--border-subtle` | `#1a2230` | Default card/panel borders — visible but quiet |
| `--border-default` | `#243044` | Table dividers, input borders, segment dividers |
| `--border-strong` | `#36425a` | Focused inputs, emphasized separators |
| `--border-critical` | `#9aabc2` | High-emphasis borders (rare — only on primary CTAs) |

### 2.4 Text

| Token | Hex | Use |
|---|---|---|
| `--text-primary` | `#e8ebf0` | Body text, headings, primary content |
| `--text-secondary` | `#a8b3c2` | Secondary labels, table column headers, metadata |
| `--text-tertiary` | `#6b7585` | Captions, placeholders, deemphasized helper text |
| `--text-disabled` | `#3d4658` | Disabled controls, archived items |
| `--text-inverse` | `#0a1628` | Text on light/white backgrounds (rare) |
| `--text-link` | `#a8b3c2` | Default link text — same as secondary, *underlined* on hover, never a different color |

**Rule:** Links are not blue. Hyperlinks are styled as `--text-secondary` with a 1px solid `border-bottom` of `--border-strong` on hover. This is the Bloomberg/Carbon convention. Bright link blue reads as consumer web.

### 2.5 Brand cyan — RESERVED USE ONLY

| Token | Hex | Use |
|---|---|---|
| `--cyan-400` | `#22d3ee` | **Live signal indicator only** — SSE connection dot, streaming status |
| `--cyan-glow` | `rgba(34, 211, 238, 0.18)` | Soft halo behind live indicator (optional, low-emphasis) |

**Where cyan does NOT appear:** Buttons. Active tabs. Focused inputs. Brand mark in the header. Card accents. Hover states. Selected rows. Anywhere decorative.

**Active/focus states use neutral white instead:**
- Active tab indicator: 2px `--text-primary` underline
- Focused input ring: 2px `--neutral-100` outer ring
- Selected row: `--surface-elevated` background + `--neutral-100` left border (3px)

### 2.6 Semantic status (the governance taxonomy)

Carbon-tier desaturated. Each status has three values: **fg** (text/icon), **border** (chip outline), **bg** (10% alpha row tint).

| Status | fg | border | bg |
|---|---|---|---|
| **DENIED** (red) | `#fa4d56` | `#da1e28` | `rgba(218, 30, 40, 0.10)` |
| **HELD** (amber) | `#f1c21b` | `#d2a106` | `rgba(210, 161, 6, 0.10)` |
| **OK** (green) | `#42be65` | `#24a148` | `rgba(36, 161, 72, 0.08)` |
| **START** (neutral) | `#a8b3c2` | `#6b7585` | `rgba(168, 179, 194, 0.06)` |
| **STREAMING** (cyan) | `#22d3ee` | — | — |
| **DISCONNECTED** | `#6b7585` | `#4d5667` | none |
| **INFO** (blue) | `#78a9ff` | `#4589ff` | `rgba(69, 137, 255, 0.10)` |

**Notes on the institutional palette:**
- **DENIED** is `#fa4d56`, not `#f87171`. Carbon's red. Reads as "production alert" not "consumer warning."
- **OK** is `#42be65`, not `#34d399`. Carbon's green. Less playful, more clinical.
- **START** is now neutral gray, not cyan. Cyan is reserved for live signal only.
- All `bg` tints are 6–10% alpha — barely visible in tables, just enough to separate rows.

**Rule:** Don't introduce new status colors without a corresponding new verdict in the backend. If it doesn't have a `Receipt` or `AgentRun` status enum, it doesn't get a color.

---

## 3. Typography

### 3.1 Font families

```css
--font-sans: 'IBM Plex Sans', ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
--font-mono: 'IBM Plex Mono', ui-monospace, 'Menlo', 'Monaco', 'Courier New', monospace;
```

Load via Next.js `next/font/google`:

```ts
// app/layout.tsx
import { IBM_Plex_Sans, IBM_Plex_Mono } from 'next/font/google';

const sans = IBM_Plex_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-sans',
});
const mono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-mono',
});
```

**Why Plex.** IBM open-sourced Plex specifically for the Carbon Design System and serious enterprise software. It has the structural integrity of Helvetica with subtle humanist quirks (the slightly flared tail on the lowercase `l`, the squared-off `g`) that signal craft without performing it. Plex Mono is one of the few free monospaces designed *as a system family* with the sans, so tabular alignment between body and code is genuinely clean.

### 3.2 Type scale

| Token | Size / Weight / Line-height / Tracking | Use |
|---|---|---|
| `text-display` | 28px / 600 / 1.15 / -0.015em | Page titles (rare — sign-in, error pages) |
| `text-section` | 20px / 600 / 1.25 / -0.01em | Section headings, primary card titles |
| `text-heading` | 16px / 600 / 1.3 / -0.005em | Card headers, drawer titles |
| `text-body-l` | 14px / 500 / 1.5 / 0 | Primary body text in narrative content |
| `text-body` | 13px / 400 / 1.5 / 0 | **Default body** — table cells, paragraph text |
| `text-body-s` | 12px / 400 / 1.45 / 0 | Secondary descriptions, dense metadata |
| `text-caption` | 12px / 500 / 1.4 / 0.005em | Labels, helper copy |
| `text-micro` | 11px / 600 / 1.3 / 0.06em uppercase | Pills, badges, axis labels, table headers |
| `text-mono-body` | 13px / 400 / 1.5 / 0 | Code, IDs, hashes (inside paragraphs) |
| `text-mono-caption` | 12px / 400 / 1.4 / 0 | Timestamps, receipt IDs (in tables) |

**Rule:** 13px is the default body size. Do not pad sizes up to feel "premium" — Bloomberg ships at 11px, Carbon at 14px max. Density IS the premium signal. Reserve 14px+ for narrative content (settings descriptions, empty-state copy), not data.

### 3.3 Tabular numerals

Always enabled on numeric columns, timestamps, IDs, counts:

```css
.tabular { font-variant-numeric: tabular-nums; }
```

Apply globally to `<table>` and `<code>` by default. Otherwise digits jiggle as values change — unacceptable in a real-time dashboard.

### 3.4 Letter-spacing rules

- **Display sizes (≥20px):** negative tracking (−0.01 to −0.015em). Tightens character relationships at large sizes.
- **Body sizes (12–14px):** zero tracking. Plex was designed for these sizes — don't override.
- **Micro/uppercase (≤11px, all caps):** positive tracking (+0.05 to +0.06em). Required for legibility of small caps.

---

## 4. Spacing

4px base, geometric scale, Tailwind-aligned.

| Token | Pixel | Tailwind | Use |
|---|---|---|---|
| `space-1` | 4px | `1` | Inline gap, badge padding-x |
| `space-2` | 8px | `2` | Compact stacks, button padding-y |
| `space-3` | 12px | `3` | Default form-field gap, button padding-x |
| `space-4` | 16px | `4` | **Card padding (default)**, section gap |
| `space-6` | 24px | `6` | Card padding (spacious), section gap (default) |
| `space-8` | 32px | `8` | Section padding-x, large gaps |
| `space-12` | 48px | `12` | Page-section vertical rhythm |
| `space-16` | 64px | `16` | Page padding-x (desktop) |

### Density anchors

These are the values used throughout the app. Memorize these.

| Element | Value |
|---|---|
| Table row height | **36px** |
| Table header row height | **32px** |
| List item height (default) | **48px** |
| List item height (compact) | **40px** |
| Top nav height | **48px** |
| Sidebar width (expanded) | **224px** |
| Sidebar width (collapsed) | **56px** |
| Drawer width | **480px** |
| Modal max-width | **560px** |
| Card default padding | **16px** (`space-4`) |
| Card spacious padding | **24px** (`space-6`) |
| Page padding-x (desktop) | **32px** (`space-8`) |
| Page padding-x (mobile) | **16px** (`space-4`) |

---

## 5. Border radii

Square-leaning. Carbon ships with 0–4px radii on most components.

| Token | Pixel | Use |
|---|---|---|
| `radius-none` | 0px | Tables, code blocks, full-width banners |
| `radius-xs` | 2px | Status pills (default), tight inline chips |
| `radius-sm` | 4px | **Buttons (default)**, inputs, segment controls |
| `radius-md` | 6px | **Cards (default)**, panels, dropdowns |
| `radius-lg` | 8px | Modals, drawers |
| `radius-pill` | 9999px | Avatars, dot indicators (only when fully circular is required) |

**Rule:** Never mix more than two radii in a single composition. A card (`radius-md`) containing buttons (`radius-sm`) is fine. A card containing pills (`radius-xs`) and buttons (`radius-sm`) and a circular avatar (`radius-pill`) is visual noise. Pick two and commit.

---

## 6. Motion

### 6.1 Durations

| Token | Value | Use |
|---|---|---|
| `motion-instant` | 80ms | Color transitions on hover (links, icons, table rows) |
| `motion-fast` | 120ms | Button hover, simple state changes |
| `motion-base` | 180ms | Drawer/modal entry, expanding rows |
| `motion-slow` | 240ms | Page transitions (rare) |

That's the entire motion vocabulary. Four tokens. No spring, no overshoot, no deliberate tier.

### 6.2 Easings

| Token | Value | Use |
|---|---|---|
| `ease-default` | `cubic-bezier(0.2, 0, 0.38, 0.9)` | All state changes (Carbon's productive easing) |
| `ease-out` | `cubic-bezier(0, 0, 0.38, 0.9)` | Element entering view (drawer, modal) |
| `ease-in` | `cubic-bezier(0.2, 0, 1, 0.9)` | Element leaving view |

Carbon's productive easing curves — engineered for institutional UIs where motion communicates state change without drawing attention to itself.

### 6.3 Animation rules

**Animate:**
- `opacity`, `color`, `background-color`, `border-color`
- `transform: translateX/Y` (drawer/modal slide-in only)

**Never animate:**
- `transform: scale` — reads as consumer/playful
- `box-shadow` — drift between dark UIs
- `width`, `height`, `padding`, `margin`, `top/left/right/bottom` — layout reflow
- Any element on hover beyond color/border changes

**The live indicator** is the only piece of UI that animates continuously, and it does so quietly — a 2-second opacity breath, not a glow pulse:

```css
@keyframes live-breath {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}
.live-dot {
  animation: live-breath 2s ease-in-out infinite;
  background: var(--cyan-400);
  width: 8px;
  height: 8px;
  border-radius: 9999px;
}
```

No box-shadow glow. No scaling. Just opacity breathing.

**Reduced motion:** every animation collapses to ≤ 0.01ms when `prefers-reduced-motion: reduce`.

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 7. Shadows

Almost none. Institutional dark UIs use borders to delineate structure, not shadows.

| Token | Value | Use |
|---|---|---|
| `shadow-none` | `none` | Cards, panels, most surfaces (default) |
| `shadow-sm` | `0 1px 2px rgba(0, 0, 0, 0.4)` | Dropdown menus, tooltips |
| `shadow-md` | `0 4px 12px rgba(0, 0, 0, 0.5)` | Drawers, modals |

**Rule:** Cards do not have shadows. They have borders. If you find yourself adding a shadow to make a card "pop," the answer is to strengthen the border, not add elevation.

Focus rings are 2px outer rings, not shadows:

```css
.focus-ring:focus-visible {
  outline: 2px solid var(--neutral-100);
  outline-offset: 2px;
}
```

---

## 8. Component primitives

The atoms every page composes from. v0 generations should match these exactly. Divergence is a regression.

### 8.1 Status pill

The single most-rendered AXIOM-specific component.

```
┌─────────────────┐
│ ● DENIED        │   ← uppercase mono, solid dot (no glow), bg-tint, 2px radius
└─────────────────┘
```

**Spec:**
- Padding: `2px 8px` (top-bottom 2px, left-right 8px)
- Border-radius: `radius-xs` (2px) — *not* full pill
- Font: `text-micro` (11px / 600 / uppercase / +0.06em tracking)
- Background: status `bg` color
- Border: 1px solid status `border` color
- Min-width: `64px` (tabular rhythm in tables)
- Dot: 6px solid circle, status `fg` color, `margin-right: 6px`. **No glow. No animation.**

### 8.2 Card

- Background: `--surface-card`
- Border: 1px solid `--border-subtle`
- Border-radius: `radius-md` (6px)
- Padding: `space-4` (16px) default, `space-6` (24px) spacious
- Header (if present): `text-heading`, margin-bottom `space-3` (12px), with optional 1px `--border-subtle` divider below

### 8.3 Button — primary

The primary CTA. White-on-navy, not cyan.

- Background: `--neutral-100` (`#e8ebf0`)
- Text: `--text-inverse` (`#0a1628`), `text-body`, weight 600
- Padding: `8px 16px` default, `6px 12px` compact
- Border-radius: `radius-sm` (4px)
- Hover: background `#ffffff`, transition `motion-fast` `ease-default`
- Active: background `--neutral-200`
- Focus: 2px `--neutral-100` outline with 2px offset
- Disabled: opacity 0.4, cursor not-allowed

### 8.4 Button — secondary

- Background: transparent
- Text: `--text-primary`, `text-body`, weight 500
- Border: 1px solid `--border-default`
- Padding: same as primary
- Hover: background `--surface-elevated`, border `--border-strong`
- Active: background `--neutral-800`
- Focus: same as primary

### 8.5 Button — destructive

For DELETE, REVOKE, KILL agent.

- Background: transparent
- Text: `#fa4d56` (DENIED `fg`), weight 600
- Border: 1px solid `#da1e28` (DENIED `border`)
- Hover: background `rgba(218, 30, 40, 0.10)`, border `#fa4d56`

### 8.6 Input

- Background: `--surface-input`
- Border: 1px solid `--border-default`
- Border-radius: `radius-sm` (4px)
- Padding: `8px 12px`
- Font: `text-body` (13px sans)
- Text color: `--text-primary`
- Placeholder: `--text-tertiary`
- Hover: border `--border-strong`
- Focus: 2px `--neutral-100` outer ring (no inner border change)
- Error: border `#fa4d56`, error message in `text-caption` `#fa4d56` below

### 8.7 Table

- Background: transparent (sits on `--surface-card`)
- Header row: `--surface-elevated` background, `text-micro` uppercase, `--text-secondary` color, height `32px`
- Body row: 1px `--border-subtle` bottom border, height `36px`, padding `0 16px`
- Hover: `--surface-elevated` background, `motion-instant` color transition
- Selected: `--surface-elevated` + 3px `--neutral-100` left border
- Cell font: `text-body` (13px) for sans content, `text-mono-caption` (12px) for IDs/timestamps
- Numeric cells: right-aligned, `tabular-nums`

### 8.8 Tab — horizontal

For project workspace tabs and similar segment navigation.

- Tab text: `text-body`, weight 500, color `--text-secondary`
- Padding: `12px 16px`
- Bottom border (inactive): 2px transparent
- Hover: color `--text-primary`, bottom border 2px `--border-default`
- Active: color `--text-primary`, weight 600, bottom border 2px `--text-primary` (white, not cyan)

### 8.9 Live indicator

The one place cyan still lives.

```html
<span class="live-indicator">
  <span class="live-dot"></span>
  <span class="live-label">STREAMING</span>
</span>
```

```css
.live-indicator {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font: var(--text-micro);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-secondary);
}
.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 9999px;
  background: var(--cyan-400);
  animation: live-breath 2s ease-in-out infinite;
}
.live-label {
  /* default secondary text — the dot carries the signal, not the text */
}
```

When disconnected, swap the dot to `--neutral-500` and remove the animation. The label stays the same.

---

## 9. CSS variables — copy-paste block

This is the operational core. Paste into `app/globals.css` (or equivalent):

```css
:root {
  /* Surfaces */
  --surface-page: #0a1628;
  --surface-chrome: #070f1c;
  --surface-card: #0f1d2e;
  --surface-elevated: #16263a;
  --surface-input: #0c1a2a;
  --surface-overlay: rgba(7, 15, 28, 0.88);
  --surface-code: #0a1421;

  /* Neutrals */
  --neutral-100: #e8ebf0;
  --neutral-200: #c6cdd6;
  --neutral-400: #8b95a3;
  --neutral-500: #6b7585;
  --neutral-600: #4d5667;
  --neutral-700: #363e4d;
  --neutral-800: #242a36;
  --neutral-900: #161b24;

  /* Borders */
  --border-subtle: #1a2230;
  --border-default: #243044;
  --border-strong: #36425a;
  --border-critical: #9aabc2;

  /* Text */
  --text-primary: #e8ebf0;
  --text-secondary: #a8b3c2;
  --text-tertiary: #6b7585;
  --text-disabled: #3d4658;
  --text-inverse: #0a1628;
  --text-link: #a8b3c2;

  /* Brand cyan — RESERVED for live indicator only */
  --cyan-400: #22d3ee;
  --cyan-glow: rgba(34, 211, 238, 0.18);

  /* Semantic — DENIED */
  --status-denied-fg: #fa4d56;
  --status-denied-border: #da1e28;
  --status-denied-bg: rgba(218, 30, 40, 0.10);

  /* Semantic — HELD */
  --status-held-fg: #f1c21b;
  --status-held-border: #d2a106;
  --status-held-bg: rgba(210, 161, 6, 0.10);

  /* Semantic — OK */
  --status-ok-fg: #42be65;
  --status-ok-border: #24a148;
  --status-ok-bg: rgba(36, 161, 72, 0.08);

  /* Semantic — START / DISCONNECTED */
  --status-neutral-fg: #a8b3c2;
  --status-neutral-border: #6b7585;
  --status-neutral-bg: rgba(168, 179, 194, 0.06);

  /* Semantic — INFO */
  --status-info-fg: #78a9ff;
  --status-info-border: #4589ff;
  --status-info-bg: rgba(69, 137, 255, 0.10);

  /* Typography */
  --font-sans: 'IBM Plex Sans', ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono: 'IBM Plex Mono', ui-monospace, 'Menlo', 'Monaco', 'Courier New', monospace;

  /* Spacing — 4px base */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --space-8: 32px;
  --space-12: 48px;
  --space-16: 64px;

  /* Radii */
  --radius-none: 0px;
  --radius-xs: 2px;
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-pill: 9999px;

  /* Motion */
  --motion-instant: 80ms;
  --motion-fast: 120ms;
  --motion-base: 180ms;
  --motion-slow: 240ms;
  --ease-default: cubic-bezier(0.2, 0, 0.38, 0.9);
  --ease-out: cubic-bezier(0, 0, 0.38, 0.9);
  --ease-in: cubic-bezier(0.2, 0, 1, 0.9);

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.4);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.5);

  /* Density anchors */
  --density-row: 36px;
  --density-row-header: 32px;
  --density-list: 48px;
  --density-list-compact: 40px;
  --density-nav-top: 48px;
  --density-sidebar: 224px;
  --density-sidebar-collapsed: 56px;
  --density-drawer: 480px;
  --density-modal: 560px;
}

html {
  background: var(--surface-page);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 13px;
  line-height: 1.5;
  font-variant-numeric: tabular-nums;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

@keyframes live-breath {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}
```

---

## 10. Tailwind config snippet

Paste into `tailwind.config.ts`:

```ts
import type { Config } from 'tailwindcss';

const config: Config = {
  theme: {
    extend: {
      colors: {
        surface: {
          page: 'var(--surface-page)',
          chrome: 'var(--surface-chrome)',
          card: 'var(--surface-card)',
          elevated: 'var(--surface-elevated)',
          input: 'var(--surface-input)',
        },
        neutral: {
          100: 'var(--neutral-100)',
          200: 'var(--neutral-200)',
          400: 'var(--neutral-400)',
          500: 'var(--neutral-500)',
          600: 'var(--neutral-600)',
          700: 'var(--neutral-700)',
          800: 'var(--neutral-800)',
          900: 'var(--neutral-900)',
        },
        border: {
          subtle: 'var(--border-subtle)',
          DEFAULT: 'var(--border-default)',
          strong: 'var(--border-strong)',
          critical: 'var(--border-critical)',
        },
        text: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          tertiary: 'var(--text-tertiary)',
          disabled: 'var(--text-disabled)',
          inverse: 'var(--text-inverse)',
        },
        cyan: {
          400: 'var(--cyan-400)',
        },
        status: {
          denied: {
            fg: 'var(--status-denied-fg)',
            border: 'var(--status-denied-border)',
            bg: 'var(--status-denied-bg)',
          },
          held: {
            fg: 'var(--status-held-fg)',
            border: 'var(--status-held-border)',
            bg: 'var(--status-held-bg)',
          },
          ok: {
            fg: 'var(--status-ok-fg)',
            border: 'var(--status-ok-border)',
            bg: 'var(--status-ok-bg)',
          },
          neutral: {
            fg: 'var(--status-neutral-fg)',
            border: 'var(--status-neutral-border)',
            bg: 'var(--status-neutral-bg)',
          },
          info: {
            fg: 'var(--status-info-fg)',
            border: 'var(--status-info-border)',
            bg: 'var(--status-info-bg)',
          },
        },
      },
      fontFamily: {
        sans: 'var(--font-sans)',
        mono: 'var(--font-mono)',
      },
      fontSize: {
        'display': ['28px', { lineHeight: '1.15', letterSpacing: '-0.015em', fontWeight: '600' }],
        'section': ['20px', { lineHeight: '1.25', letterSpacing: '-0.01em', fontWeight: '600' }],
        'heading': ['16px', { lineHeight: '1.3', letterSpacing: '-0.005em', fontWeight: '600' }],
        'body-l': ['14px', { lineHeight: '1.5', fontWeight: '500' }],
        'body': ['13px', { lineHeight: '1.5' }],
        'body-s': ['12px', { lineHeight: '1.45' }],
        'caption': ['12px', { lineHeight: '1.4', letterSpacing: '0.005em', fontWeight: '500' }],
        'micro': ['11px', { lineHeight: '1.3', letterSpacing: '0.06em', fontWeight: '600' }],
        'mono-body': ['13px', { lineHeight: '1.5' }],
        'mono-caption': ['12px', { lineHeight: '1.4' }],
      },
      borderRadius: {
        none: 'var(--radius-none)',
        xs: 'var(--radius-xs)',
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        pill: 'var(--radius-pill)',
      },
      transitionDuration: {
        instant: 'var(--motion-instant)',
        fast: 'var(--motion-fast)',
        base: 'var(--motion-base)',
        slow: 'var(--motion-slow)',
      },
      transitionTimingFunction: {
        default: 'var(--ease-default)',
        out: 'var(--ease-out)',
        in: 'var(--ease-in)',
      },
      boxShadow: {
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
      },
    },
  },
};

export default config;
```

---

## 11. v0 prompt prefix — the operational tool

**Paste this verbatim before every v0.app prompt.** It is what keeps generated screens coherent across the system.

```
DESIGN SYSTEM — AXIOM (use these exact values, no improvisation):

CALIBRATION
- Enterprise/institutional infrastructure tool. References: IBM Carbon, Bloomberg Terminal, Atlassian dark mode.
- Restraint over expression. Color is punctuation, not paint.
- Borders define structure, not shadows. Cards have visible 1px borders, not floating drop-shadows.
- Density is the premium signal. Pack truth per pixel.
- Cyan #22d3ee is RESERVED for the live indicator only. Nowhere else.

COLORS
- Surfaces: page #0a1628 / chrome #070f1c / card #0f1d2e / elevated #16263a / input #0c1a2a
- Borders: subtle #1a2230 / default #243044 / strong #36425a
- Text: primary #e8ebf0 / secondary #a8b3c2 / tertiary #6b7585 / disabled #3d4658
- Active states (focus, selection, brand emphasis): use #e8ebf0 (white), NOT cyan
- Status DENIED: fg #fa4d56, border #da1e28, bg rgba(218,30,40,0.10)
- Status HELD: fg #f1c21b, border #d2a106, bg rgba(210,161,6,0.10)
- Status OK: fg #42be65, border #24a148, bg rgba(36,161,72,0.08)
- Status START: fg #a8b3c2 (neutral, not cyan)
- LIVE indicator: #22d3ee dot with 2s opacity breath (NO glow, NO box-shadow)

TYPOGRAPHY
- Sans: IBM Plex Sans (load from Google Fonts, weights 400/500/600/700)
- Mono: IBM Plex Mono (timestamps, IDs, code)
- Default body: 13px / 400 / 1.5 / sans
- Default mono caption: 12px / 400 / mono
- Headings: 16px section / 20px page section / 28px display
- Micro/uppercase pill labels: 11px / 600 / +0.06em tracking
- Tabular nums on every numeric column, timestamp, count, percentage

LAYOUT
- Spacing: 4 / 8 / 12 / 16 / 24 / 32 px
- Radii: cards 6px, buttons 4px, inputs 4px, status pills 2px (NOT fully rounded)
- Density: tables 36px row height, headers 32px, list items 48px
- Card padding: 16px default, 24px spacious
- Page padding-x: 32px desktop

COMPONENTS
- Status pill: 2px radius (not full-pill), uppercase 11px mono, solid 6px dot (no glow), bg-tint, 1px border, min-width 64px
- Card: bg #0f1d2e, 1px border #1a2230, 6px radius, 16px padding, NO shadow
- Primary button: bg #e8ebf0 (white), text #0a1628, 4px radius, 8px 16px padding (NOT cyan)
- Secondary button: transparent bg, 1px border #243044, text #e8ebf0
- Destructive button: transparent bg, 1px border #da1e28, text #fa4d56
- Input: bg #0c1a2a, 1px border #243044, 4px radius, focus 2px white outer ring (NOT cyan)
- Active tab: 2px white bottom border (NOT cyan)
- Selected row: bg #16263a + 3px white left border
- Table: header bg #16263a / row 36px / hover #16263a / 1px subtle bottom border per row

MOTION
- Hover: 120ms ease (cubic-bezier(0.2, 0, 0.38, 0.9))
- Drawer/modal entry: 180ms ease-out
- NEVER animate scale, width, height, padding, margin, top/left/right/bottom
- NEVER use spring/overshoot easing
- Live dot: 2s opacity breath only (no glow, no scaling)

LINKS
- Same color as text-secondary, underlined on hover (1px solid border-bottom #36425a)
- Never bright blue. Never cyan.

STACK: Tailwind + shadcn/ui, TypeScript, no external libs unless explicitly specified.
ABSOLUTELY DO NOT use: bright blue links, cyan accents on buttons, glowing status pills, drop shadows on cards, fully-rounded pills, scale animations on hover, spring easing, gradient backgrounds, decorative blur effects, or rounded-full radius on anything except dot indicators.
```

---

## 12. Migration from current shipped UI

Surfaces shipped through Phase 7.12 used cyan as a brand-flowing accent. The pivot to v1 tokens requires the following surgical edits to existing components. Estimated effort: 4–6 hours of Cursor work.

| Surface | Current | New | Effort |
|---|---|---|---|
| Sidebar logo / brand mark | Cyan accent | Neutral white `#e8ebf0` | 5 min |
| Active tab indicators | Cyan bottom border | White (`--text-primary`) bottom border | 15 min |
| Selected sidebar item | Cyan left border | White (`--text-primary`) left border + `--surface-elevated` bg | 15 min |
| Primary CTA buttons | Cyan-filled | White-filled (`--neutral-100` bg, `--text-inverse` text) | 30 min |
| Focused input rings | Cyan ring | White ring (`--neutral-100`) | 20 min |
| Status pills | Full-rounded with glow | 2px radius, no glow, solid dot | 45 min |
| Card border-radius | 12px | 6px | 10 min |
| Card shadows (if any) | Drop shadow | Removed; rely on border | 30 min |
| Table row height | 40px | 36px | 5 min |
| Card padding | 24px default | 16px default | 30 min |
| Geist Sans/Mono import | Geist | IBM Plex Sans/Mono | 30 min |
| SSE green dot (Phase 7.6) | **Keep cyan** | Unchanged — this is the one allowed cyan use | 0 min |
| Streaming pulse animation | Glow pulse | Opacity breath only, no glow | 20 min |

Start the migration with the typography swap (Plex import) — it's a one-file change in `app/layout.tsx` and visibly shifts the entire UI character before any other token applies. Then radii, then color swaps, then density.

---

## 13. Governance

- **Source of truth:** this file. Changes ship as PRs to `docs/design-tokens.md` with a brief justification in the commit message.
- **Versioning:** semver. v1 is the initial enterprise calibration. Breaking changes (renamed tokens, removed values) require a major bump and migration notes.
- **Deprecation policy:** when a token is replaced, mark with `@deprecated` comment and keep it for one minor version before removal.
- **No tokens added without a use case.** If a new color/size/radius is needed for a single component, the question is whether the component is wrong, not whether the token system is incomplete.
- **No tokens added "in case we need them later."** Add when needed, not before.

---

*End of v1.*
# AXIOM Design Tokens

**Status:** v1 — locked at Phase 7.7 boundary
**Calibration:** Enterprise / institutional infrastructure tool
**Reference points:** IBM Carbon (G100 dark theme), Bloomberg Terminal, Atlassian dark mode, Datadog, Splunk
**Stack:** Next.js 14 + Tailwind + shadcn/ui + TypeScript

This is the single source of truth for every color, type ramp, spacing value, radius, and motion duration shipped in AXIOM's frontend. All component code (existing and v0-generated) must reference these tokens — never hardcoded hex values, never ad-hoc pixel sizes.

The bottom of this file contains a compressed **v0 prompt prefix** to paste before every v0.app generation request. That's how the system stays coherent across screens.

---

## 1. Foundation principles

These are the calibration choices that distinguish AXIOM's UI from a startup developer tool. Every token below derives from these.

1. **Restraint over expression.** Color is punctuation, not paint. The default state of every surface is grayscale-on-navy. Color appears only where it carries semantic weight (a verdict, a live signal, a focus state). If a button is colored "because it looks nice," it is wrong.
2. **Borders over shadows.** Institutional UIs delineate structure with visible 1px borders, not floating drop-shadows. Cards have edges. Tables have dividers. Sections are clearly bounded.
3. **Density is the premium signal.** Tables ship at 36px row height. Body copy is 13px. Metadata is 12px. The dashboard packs more truth per pixel than its consumer-grade competitors. This is the inverse of Stripe-tier whitespace generosity — and it is what CISOs and reliability engineers actually want.
4. **Square geometry.** Border radii are small (4–6px). Pills are slightly rounded, not fully circular. Square reads as serious infrastructure; rounded reads as consumer SaaS.
5. **Motion serves comprehension, not delight.** No spring easings, no streaming pulses, no scaling on hover. Transitions are color/border/opacity only, 100–150ms. The UI never performs.
6. **Numerals are sacred.** `font-variant-numeric: tabular-nums` on every numeric column, timestamp, count, and percentage. Digits never jiggle as values change.
7. **Cyan is reserved.** The brand cyan `#22d3ee` survives in exactly one role: the **live signal indicator** (SSE connection dot, streaming status). It does not appear on buttons, active tabs, focused inputs, brand emphasis, or anywhere decorative. Active states default to white or muted blue.

---

## 2. Color tokens

### 2.1 Surfaces (navy substrate, preserved from current build)

| Token | Hex | Use |
|---|---|---|
| `--surface-page` | `#0a1628` | Main page background |
| `--surface-chrome` | `#070f1c` | Sidebar, top nav, deeper UI chrome |
| `--surface-card` | `#0f1d2e` | Cards, modal bodies, panel containers |
| `--surface-elevated` | `#16263a` | Hover/active row states inside cards and tables |
| `--surface-input` | `#0c1a2a` | Text inputs, selects, search bars |
| `--surface-overlay` | `rgba(7, 15, 28, 0.88)` | Modal backdrops |
| `--surface-code` | `#0a1421` | Inline code blocks, JSON viewers |

### 2.2 Neutral grays (Carbon-derived, for content layered on the navy)

These are cool grays that compose with the navy substrate. Used for borders, text, neutral chrome elements.

| Token | Hex | Use |
|---|---|---|
| `--neutral-100` | `#e8ebf0` | High-contrast text on navy |
| `--neutral-200` | `#c6cdd6` | Secondary text |
| `--neutral-400` | `#8b95a3` | Tertiary text, metadata |
| `--neutral-500` | `#6b7585` | Disabled text, deemphasized labels |
| `--neutral-600` | `#4d5667` | Strong borders, dividers |
| `--neutral-700` | `#363e4d` | Default borders |
| `--neutral-800` | `#242a36` | Subtle borders |
| `--neutral-900` | `#161b24` | Background tints, deep panel surfaces |

### 2.3 Borders

| Token | Hex | Use |
|---|---|---|
| `--border-subtle` | `#1a2230` | Default card/panel borders — visible but quiet |
| `--border-default` | `#243044` | Table dividers, input borders, segment dividers |
| `--border-strong` | `#36425a` | Focused inputs, emphasized separators |
| `--border-critical` | `#9aabc2` | High-emphasis borders (rare — only on primary CTAs) |

### 2.4 Text

| Token | Hex | Use |
|---|---|---|
| `--text-primary` | `#e8ebf0` | Body text, headings, primary content |
| `--text-secondary` | `#a8b3c2` | Secondary labels, table column headers, metadata |
| `--text-tertiary` | `#6b7585` | Captions, placeholders, deemphasized helper text |
| `--text-disabled` | `#3d4658` | Disabled controls, archived items |
| `--text-inverse` | `#0a1628` | Text on light/white backgrounds (rare) |
| `--text-link` | `#a8b3c2` | Default link text — same as secondary, *underlined* on hover, never a different color |

**Rule:** Links are not blue. Hyperlinks are styled as `--text-secondary` with a 1px solid `border-bottom` of `--border-strong` on hover. This is the Bloomberg/Carbon convention. Bright link blue reads as consumer web.

### 2.5 Brand cyan — RESERVED USE ONLY

| Token | Hex | Use |
|---|---|---|
| `--cyan-400` | `#22d3ee` | **Live signal indicator only** — SSE connection dot, streaming status |
| `--cyan-glow` | `rgba(34, 211, 238, 0.18)` | Soft halo behind live indicator (optional, low-emphasis) |

**Where cyan does NOT appear:** Buttons. Active tabs. Focused inputs. Brand mark in the header. Card accents. Hover states. Selected rows. Anywhere decorative.

**Active/focus states use neutral white instead:**
- Active tab indicator: 2px `--text-primary` underline
- Focused input ring: 2px `--neutral-100` outer ring
- Selected row: `--surface-elevated` background + `--neutral-100` left border (3px)

### 2.6 Semantic status (the governance taxonomy)

Carbon-tier desaturated. Each status has three values: **fg** (text/icon), **border** (chip outline), **bg** (10% alpha row tint).

| Status | fg | border | bg |
|---|---|---|---|
| **DENIED** (red) | `#fa4d56` | `#da1e28` | `rgba(218, 30, 40, 0.10)` |
| **HELD** (amber) | `#f1c21b` | `#d2a106` | `rgba(210, 161, 6, 0.10)` |
| **OK** (green) | `#42be65` | `#24a148` | `rgba(36, 161, 72, 0.08)` |
| **START** (neutral) | `#a8b3c2` | `#6b7585` | `rgba(168, 179, 194, 0.06)` |
| **STREAMING** (cyan) | `#22d3ee` | — | — |
| **DISCONNECTED** | `#6b7585` | `#4d5667` | none |
| **INFO** (blue) | `#78a9ff` | `#4589ff` | `rgba(69, 137, 255, 0.10)` |

**Notes on the institutional palette:**
- **DENIED** is `#fa4d56`, not `#f87171`. Carbon's red. Reads as "production alert" not "consumer warning."
- **OK** is `#42be65`, not `#34d399`. Carbon's green. Less playful, more clinical.
- **START** is now neutral gray, not cyan. Cyan is reserved for live signal only.
- All `bg` tints are 6–10% alpha — barely visible in tables, just enough to separate rows.

**Rule:** Don't introduce new status colors without a corresponding new verdict in the backend. If it doesn't have a `Receipt` or `AgentRun` status enum, it doesn't get a color.

---

## 3. Typography

### 3.1 Font families

```css
--font-sans: 'IBM Plex Sans', ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
--font-mono: 'IBM Plex Mono', ui-monospace, 'Menlo', 'Monaco', 'Courier New', monospace;
```

Load via Next.js `next/font/google`:

```ts
// app/layout.tsx
import { IBM_Plex_Sans, IBM_Plex_Mono } from 'next/font/google';

const sans = IBM_Plex_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-sans',
});
const mono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-mono',
});
```

**Why Plex.** IBM open-sourced Plex specifically for the Carbon Design System and serious enterprise software. It has the structural integrity of Helvetica with subtle humanist quirks (the slightly flared tail on the lowercase `l`, the squared-off `g`) that signal craft without performing it. Plex Mono is one of the few free monospaces designed *as a system family* with the sans, so tabular alignment between body and code is genuinely clean.

### 3.2 Type scale

| Token | Size / Weight / Line-height / Tracking | Use |
|---|---|---|
| `text-display` | 28px / 600 / 1.15 / -0.015em | Page titles (rare — sign-in, error pages) |
| `text-section` | 20px / 600 / 1.25 / -0.01em | Section headings, primary card titles |
| `text-heading` | 16px / 600 / 1.3 / -0.005em | Card headers, drawer titles |
| `text-body-l` | 14px / 500 / 1.5 / 0 | Primary body text in narrative content |
| `text-body` | 13px / 400 / 1.5 / 0 | **Default body** — table cells, paragraph text |
| `text-body-s` | 12px / 400 / 1.45 / 0 | Secondary descriptions, dense metadata |
| `text-caption` | 12px / 500 / 1.4 / 0.005em | Labels, helper copy |
| `text-micro` | 11px / 600 / 1.3 / 0.06em uppercase | Pills, badges, axis labels, table headers |
| `text-mono-body` | 13px / 400 / 1.5 / 0 | Code, IDs, hashes (inside paragraphs) |
| `text-mono-caption` | 12px / 400 / 1.4 / 0 | Timestamps, receipt IDs (in tables) |

**Rule:** 13px is the default body size. Do not pad sizes up to feel "premium" — Bloomberg ships at 11px, Carbon at 14px max. Density IS the premium signal. Reserve 14px+ for narrative content (settings descriptions, empty-state copy), not data.

### 3.3 Tabular numerals

Always enabled on numeric columns, timestamps, IDs, counts:

```css
.tabular { font-variant-numeric: tabular-nums; }
```

Apply globally to `<table>` and `<code>` by default. Otherwise digits jiggle as values change — unacceptable in a real-time dashboard.

### 3.4 Letter-spacing rules

- **Display sizes (≥20px):** negative tracking (−0.01 to −0.015em). Tightens character relationships at large sizes.
- **Body sizes (12–14px):** zero tracking. Plex was designed for these sizes — don't override.
- **Micro/uppercase (≤11px, all caps):** positive tracking (+0.05 to +0.06em). Required for legibility of small caps.

---

## 4. Spacing

4px base, geometric scale, Tailwind-aligned.

| Token | Pixel | Tailwind | Use |
|---|---|---|---|
| `space-1` | 4px | `1` | Inline gap, badge padding-x |
| `space-2` | 8px | `2` | Compact stacks, button padding-y |
| `space-3` | 12px | `3` | Default form-field gap, button padding-x |
| `space-4` | 16px | `4` | **Card padding (default)**, section gap |
| `space-6` | 24px | `6` | Card padding (spacious), section gap (default) |
| `space-8` | 32px | `8` | Section padding-x, large gaps |
| `space-12` | 48px | `12` | Page-section vertical rhythm |
| `space-16` | 64px | `16` | Page padding-x (desktop) |

### Density anchors

These are the values used throughout the app. Memorize these.

| Element | Value |
|---|---|
| Table row height | **36px** |
| Table header row height | **32px** |
| List item height (default) | **48px** |
| List item height (compact) | **40px** |
| Top nav height | **48px** |
| Sidebar width (expanded) | **224px** |
| Sidebar width (collapsed) | **56px** |
| Drawer width | **480px** |
| Modal max-width | **560px** |
| Card default padding | **16px** (`space-4`) |
| Card spacious padding | **24px** (`space-6`) |
| Page padding-x (desktop) | **32px** (`space-8`) |
| Page padding-x (mobile) | **16px** (`space-4`) |

---

## 5. Border radii

Square-leaning. Carbon ships with 0–4px radii on most components.

| Token | Pixel | Use |
|---|---|---|
| `radius-none` | 0px | Tables, code blocks, full-width banners |
| `radius-xs` | 2px | Status pills (default), tight inline chips |
| `radius-sm` | 4px | **Buttons (default)**, inputs, segment controls |
| `radius-md` | 6px | **Cards (default)**, panels, dropdowns |
| `radius-lg` | 8px | Modals, drawers |
| `radius-pill` | 9999px | Avatars, dot indicators (only when fully circular is required) |

**Rule:** Never mix more than two radii in a single composition. A card (`radius-md`) containing buttons (`radius-sm`) is fine. A card containing pills (`radius-xs`) and buttons (`radius-sm`) and a circular avatar (`radius-pill`) is visual noise. Pick two and commit.

---

## 6. Motion

### 6.1 Durations

| Token | Value | Use |
|---|---|---|
| `motion-instant` | 80ms | Color transitions on hover (links, icons, table rows) |
| `motion-fast` | 120ms | Button hover, simple state changes |
| `motion-base` | 180ms | Drawer/modal entry, expanding rows |
| `motion-slow` | 240ms | Page transitions (rare) |

That's the entire motion vocabulary. Four tokens. No spring, no overshoot, no deliberate tier.

### 6.2 Easings

| Token | Value | Use |
|---|---|---|
| `ease-default` | `cubic-bezier(0.2, 0, 0.38, 0.9)` | All state changes (Carbon's productive easing) |
| `ease-out` | `cubic-bezier(0, 0, 0.38, 0.9)` | Element entering view (drawer, modal) |
| `ease-in` | `cubic-bezier(0.2, 0, 1, 0.9)` | Element leaving view |

Carbon's productive easing curves — engineered for institutional UIs where motion communicates state change without drawing attention to itself.

### 6.3 Animation rules

**Animate:**
- `opacity`, `color`, `background-color`, `border-color`
- `transform: translateX/Y` (drawer/modal slide-in only)

**Never animate:**
- `transform: scale` — reads as consumer/playful
- `box-shadow` — drift between dark UIs
- `width`, `height`, `padding`, `margin`, `top/left/right/bottom` — layout reflow
- Any element on hover beyond color/border changes

**The live indicator** is the only piece of UI that animates continuously, and it does so quietly — a 2-second opacity breath, not a glow pulse:

```css
@keyframes live-breath {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}
.live-dot {
  animation: live-breath 2s ease-in-out infinite;
  background: var(--cyan-400);
  width: 8px;
  height: 8px;
  border-radius: 9999px;
}
```

No box-shadow glow. No scaling. Just opacity breathing.

**Reduced motion:** every animation collapses to ≤ 0.01ms when `prefers-reduced-motion: reduce`.

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 7. Shadows

Almost none. Institutional dark UIs use borders to delineate structure, not shadows.

| Token | Value | Use |
|---|---|---|
| `shadow-none` | `none` | Cards, panels, most surfaces (default) |
| `shadow-sm` | `0 1px 2px rgba(0, 0, 0, 0.4)` | Dropdown menus, tooltips |
| `shadow-md` | `0 4px 12px rgba(0, 0, 0, 0.5)` | Drawers, modals |

**Rule:** Cards do not have shadows. They have borders. If you find yourself adding a shadow to make a card "pop," the answer is to strengthen the border, not add elevation.

Focus rings are 2px outer rings, not shadows:

```css
.focus-ring:focus-visible {
  outline: 2px solid var(--neutral-100);
  outline-offset: 2px;
}
```

---

## 8. Component primitives

The atoms every page composes from. v0 generations should match these exactly. Divergence is a regression.

### 8.1 Status pill

The single most-rendered AXIOM-specific component.

```
┌─────────────────┐
│ ● DENIED        │   ← uppercase mono, solid dot (no glow), bg-tint, 2px radius
└─────────────────┘
```

**Spec:**
- Padding: `2px 8px` (top-bottom 2px, left-right 8px)
- Border-radius: `radius-xs` (2px) — *not* full pill
- Font: `text-micro` (11px / 600 / uppercase / +0.06em tracking)
- Background: status `bg` color
- Border: 1px solid status `border` color
- Min-width: `64px` (tabular rhythm in tables)
- Dot: 6px solid circle, status `fg` color, `margin-right: 6px`. **No glow. No animation.**

### 8.2 Card

- Background: `--surface-card`
- Border: 1px solid `--border-subtle`
- Border-radius: `radius-md` (6px)
- Padding: `space-4` (16px) default, `space-6` (24px) spacious
- Header (if present): `text-heading`, margin-bottom `space-3` (12px), with optional 1px `--border-subtle` divider below

### 8.3 Button — primary

The primary CTA. White-on-navy, not cyan.

- Background: `--neutral-100` (`#e8ebf0`)
- Text: `--text-inverse` (`#0a1628`), `text-body`, weight 600
- Padding: `8px 16px` default, `6px 12px` compact
- Border-radius: `radius-sm` (4px)
- Hover: background `#ffffff`, transition `motion-fast` `ease-default`
- Active: background `--neutral-200`
- Focus: 2px `--neutral-100` outline with 2px offset
- Disabled: opacity 0.4, cursor not-allowed

### 8.4 Button — secondary

- Background: transparent
- Text: `--text-primary`, `text-body`, weight 500
- Border: 1px solid `--border-default`
- Padding: same as primary
- Hover: background `--surface-elevated`, border `--border-strong`
- Active: background `--neutral-800`
- Focus: same as primary

### 8.5 Button — destructive

For DELETE, REVOKE, KILL agent.

- Background: transparent
- Text: `#fa4d56` (DENIED `fg`), weight 600
- Border: 1px solid `#da1e28` (DENIED `border`)
- Hover: background `rgba(218, 30, 40, 0.10)`, border `#fa4d56`

### 8.6 Input

- Background: `--surface-input`
- Border: 1px solid `--border-default`
- Border-radius: `radius-sm` (4px)
- Padding: `8px 12px`
- Font: `text-body` (13px sans)
- Text color: `--text-primary`
- Placeholder: `--text-tertiary`
- Hover: border `--border-strong`
- Focus: 2px `--neutral-100` outer ring (no inner border change)
- Error: border `#fa4d56`, error message in `text-caption` `#fa4d56` below

### 8.7 Table

- Background: transparent (sits on `--surface-card`)
- Header row: `--surface-elevated` background, `text-micro` uppercase, `--text-secondary` color, height `32px`
- Body row: 1px `--border-subtle` bottom border, height `36px`, padding `0 16px`
- Hover: `--surface-elevated` background, `motion-instant` color transition
- Selected: `--surface-elevated` + 3px `--neutral-100` left border
- Cell font: `text-body` (13px) for sans content, `text-mono-caption` (12px) for IDs/timestamps
- Numeric cells: right-aligned, `tabular-nums`

### 8.8 Tab — horizontal

For project workspace tabs and similar segment navigation.

- Tab text: `text-body`, weight 500, color `--text-secondary`
- Padding: `12px 16px`
- Bottom border (inactive): 2px transparent
- Hover: color `--text-primary`, bottom border 2px `--border-default`
- Active: color `--text-primary`, weight 600, bottom border 2px `--text-primary` (white, not cyan)

### 8.9 Live indicator

The one place cyan still lives.

```html
<span class="live-indicator">
  <span class="live-dot"></span>
  <span class="live-label">STREAMING</span>
</span>
```

```css
.live-indicator {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font: var(--text-micro);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-secondary);
}
.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 9999px;
  background: var(--cyan-400);
  animation: live-breath 2s ease-in-out infinite;
}
.live-label {
  /* default secondary text — the dot carries the signal, not the text */
}
```

When disconnected, swap the dot to `--neutral-500` and remove the animation. The label stays the same.

---

## 9. CSS variables — copy-paste block

This is the operational core. Paste into `app/globals.css` (or equivalent):

```css
:root {
  /* Surfaces */
  --surface-page: #0a1628;
  --surface-chrome: #070f1c;
  --surface-card: #0f1d2e;
  --surface-elevated: #16263a;
  --surface-input: #0c1a2a;
  --surface-overlay: rgba(7, 15, 28, 0.88);
  --surface-code: #0a1421;

  /* Neutrals */
  --neutral-100: #e8ebf0;
  --neutral-200: #c6cdd6;
  --neutral-400: #8b95a3;
  --neutral-500: #6b7585;
  --neutral-600: #4d5667;
  --neutral-700: #363e4d;
  --neutral-800: #242a36;
  --neutral-900: #161b24;

  /* Borders */
  --border-subtle: #1a2230;
  --border-default: #243044;
  --border-strong: #36425a;
  --border-critical: #9aabc2;

  /* Text */
  --text-primary: #e8ebf0;
  --text-secondary: #a8b3c2;
  --text-tertiary: #6b7585;
  --text-disabled: #3d4658;
  --text-inverse: #0a1628;
  --text-link: #a8b3c2;

  /* Brand cyan — RESERVED for live indicator only */
  --cyan-400: #22d3ee;
  --cyan-glow: rgba(34, 211, 238, 0.18);

  /* Semantic — DENIED */
  --status-denied-fg: #fa4d56;
  --status-denied-border: #da1e28;
  --status-denied-bg: rgba(218, 30, 40, 0.10);

  /* Semantic — HELD */
  --status-held-fg: #f1c21b;
  --status-held-border: #d2a106;
  --status-held-bg: rgba(210, 161, 6, 0.10);

  /* Semantic — OK */
  --status-ok-fg: #42be65;
  --status-ok-border: #24a148;
  --status-ok-bg: rgba(36, 161, 72, 0.08);

  /* Semantic — START / DISCONNECTED */
  --status-neutral-fg: #a8b3c2;
  --status-neutral-border: #6b7585;
  --status-neutral-bg: rgba(168, 179, 194, 0.06);

  /* Semantic — INFO */
  --status-info-fg: #78a9ff;
  --status-info-border: #4589ff;
  --status-info-bg: rgba(69, 137, 255, 0.10);

  /* Typography */
  --font-sans: 'IBM Plex Sans', ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono: 'IBM Plex Mono', ui-monospace, 'Menlo', 'Monaco', 'Courier New', monospace;

  /* Spacing — 4px base */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --space-8: 32px;
  --space-12: 48px;
  --space-16: 64px;

  /* Radii */
  --radius-none: 0px;
  --radius-xs: 2px;
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-pill: 9999px;

  /* Motion */
  --motion-instant: 80ms;
  --motion-fast: 120ms;
  --motion-base: 180ms;
  --motion-slow: 240ms;
  --ease-default: cubic-bezier(0.2, 0, 0.38, 0.9);
  --ease-out: cubic-bezier(0, 0, 0.38, 0.9);
  --ease-in: cubic-bezier(0.2, 0, 1, 0.9);

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.4);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.5);

  /* Density anchors */
  --density-row: 36px;
  --density-row-header: 32px;
  --density-list: 48px;
  --density-list-compact: 40px;
  --density-nav-top: 48px;
  --density-sidebar: 224px;
  --density-sidebar-collapsed: 56px;
  --density-drawer: 480px;
  --density-modal: 560px;
}

html {
  background: var(--surface-page);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 13px;
  line-height: 1.5;
  font-variant-numeric: tabular-nums;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

@keyframes live-breath {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}
```

---

## 10. Tailwind config snippet

Paste into `tailwind.config.ts`:

```ts
import type { Config } from 'tailwindcss';

const config: Config = {
  theme: {
    extend: {
      colors: {
        surface: {
          page: 'var(--surface-page)',
          chrome: 'var(--surface-chrome)',
          card: 'var(--surface-card)',
          elevated: 'var(--surface-elevated)',
          input: 'var(--surface-input)',
        },
        neutral: {
          100: 'var(--neutral-100)',
          200: 'var(--neutral-200)',
          400: 'var(--neutral-400)',
          500: 'var(--neutral-500)',
          600: 'var(--neutral-600)',
          700: 'var(--neutral-700)',
          800: 'var(--neutral-800)',
          900: 'var(--neutral-900)',
        },
        border: {
          subtle: 'var(--border-subtle)',
          DEFAULT: 'var(--border-default)',
          strong: 'var(--border-strong)',
          critical: 'var(--border-critical)',
        },
        text: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          tertiary: 'var(--text-tertiary)',
          disabled: 'var(--text-disabled)',
          inverse: 'var(--text-inverse)',
        },
        cyan: {
          400: 'var(--cyan-400)',
        },
        status: {
          denied: {
            fg: 'var(--status-denied-fg)',
            border: 'var(--status-denied-border)',
            bg: 'var(--status-denied-bg)',
          },
          held: {
            fg: 'var(--status-held-fg)',
            border: 'var(--status-held-border)',
            bg: 'var(--status-held-bg)',
          },
          ok: {
            fg: 'var(--status-ok-fg)',
            border: 'var(--status-ok-border)',
            bg: 'var(--status-ok-bg)',
          },
          neutral: {
            fg: 'var(--status-neutral-fg)',
            border: 'var(--status-neutral-border)',
            bg: 'var(--status-neutral-bg)',
          },
          info: {
            fg: 'var(--status-info-fg)',
            border: 'var(--status-info-border)',
            bg: 'var(--status-info-bg)',
          },
        },
      },
      fontFamily: {
        sans: 'var(--font-sans)',
        mono: 'var(--font-mono)',
      },
      fontSize: {
        'display': ['28px', { lineHeight: '1.15', letterSpacing: '-0.015em', fontWeight: '600' }],
        'section': ['20px', { lineHeight: '1.25', letterSpacing: '-0.01em', fontWeight: '600' }],
        'heading': ['16px', { lineHeight: '1.3', letterSpacing: '-0.005em', fontWeight: '600' }],
        'body-l': ['14px', { lineHeight: '1.5', fontWeight: '500' }],
        'body': ['13px', { lineHeight: '1.5' }],
        'body-s': ['12px', { lineHeight: '1.45' }],
        'caption': ['12px', { lineHeight: '1.4', letterSpacing: '0.005em', fontWeight: '500' }],
        'micro': ['11px', { lineHeight: '1.3', letterSpacing: '0.06em', fontWeight: '600' }],
        'mono-body': ['13px', { lineHeight: '1.5' }],
        'mono-caption': ['12px', { lineHeight: '1.4' }],
      },
      borderRadius: {
        none: 'var(--radius-none)',
        xs: 'var(--radius-xs)',
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        pill: 'var(--radius-pill)',
      },
      transitionDuration: {
        instant: 'var(--motion-instant)',
        fast: 'var(--motion-fast)',
        base: 'var(--motion-base)',
        slow: 'var(--motion-slow)',
      },
      transitionTimingFunction: {
        default: 'var(--ease-default)',
        out: 'var(--ease-out)',
        in: 'var(--ease-in)',
      },
      boxShadow: {
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
      },
    },
  },
};

export default config;
```

---

## 11. v0 prompt prefix — the operational tool

**Paste this verbatim before every v0.app prompt.** It is what keeps generated screens coherent across the system.

```
DESIGN SYSTEM — AXIOM (use these exact values, no improvisation):

CALIBRATION
- Enterprise/institutional infrastructure tool. References: IBM Carbon, Bloomberg Terminal, Atlassian dark mode.
- Restraint over expression. Color is punctuation, not paint.
- Borders define structure, not shadows. Cards have visible 1px borders, not floating drop-shadows.
- Density is the premium signal. Pack truth per pixel.
- Cyan #22d3ee is RESERVED for the live indicator only. Nowhere else.

COLORS
- Surfaces: page #0a1628 / chrome #070f1c / card #0f1d2e / elevated #16263a / input #0c1a2a
- Borders: subtle #1a2230 / default #243044 / strong #36425a
- Text: primary #e8ebf0 / secondary #a8b3c2 / tertiary #6b7585 / disabled #3d4658
- Active states (focus, selection, brand emphasis): use #e8ebf0 (white), NOT cyan
- Status DENIED: fg #fa4d56, border #da1e28, bg rgba(218,30,40,0.10)
- Status HELD: fg #f1c21b, border #d2a106, bg rgba(210,161,6,0.10)
- Status OK: fg #42be65, border #24a148, bg rgba(36,161,72,0.08)
- Status START: fg #a8b3c2 (neutral, not cyan)
- LIVE indicator: #22d3ee dot with 2s opacity breath (NO glow, NO box-shadow)

TYPOGRAPHY
- Sans: IBM Plex Sans (load from Google Fonts, weights 400/500/600/700)
- Mono: IBM Plex Mono (timestamps, IDs, code)
- Default body: 13px / 400 / 1.5 / sans
- Default mono caption: 12px / 400 / mono
- Headings: 16px section / 20px page section / 28px display
- Micro/uppercase pill labels: 11px / 600 / +0.06em tracking
- Tabular nums on every numeric column, timestamp, count, percentage

LAYOUT
- Spacing: 4 / 8 / 12 / 16 / 24 / 32 px
- Radii: cards 6px, buttons 4px, inputs 4px, status pills 2px (NOT fully rounded)
- Density: tables 36px row height, headers 32px, list items 48px
- Card padding: 16px default, 24px spacious
- Page padding-x: 32px desktop

COMPONENTS
- Status pill: 2px radius (not full-pill), uppercase 11px mono, solid 6px dot (no glow), bg-tint, 1px border, min-width 64px
- Card: bg #0f1d2e, 1px border #1a2230, 6px radius, 16px padding, NO shadow
- Primary button: bg #e8ebf0 (white), text #0a1628, 4px radius, 8px 16px padding (NOT cyan)
- Secondary button: transparent bg, 1px border #243044, text #e8ebf0
- Destructive button: transparent bg, 1px border #da1e28, text #fa4d56
- Input: bg #0c1a2a, 1px border #243044, 4px radius, focus 2px white outer ring (NOT cyan)
- Active tab: 2px white bottom border (NOT cyan)
- Selected row: bg #16263a + 3px white left border
- Table: header bg #16263a / row 36px / hover #16263a / 1px subtle bottom border per row

MOTION
- Hover: 120ms ease (cubic-bezier(0.2, 0, 0.38, 0.9))
- Drawer/modal entry: 180ms ease-out
- NEVER animate scale, width, height, padding, margin, top/left/right/bottom
- NEVER use spring/overshoot easing
- Live dot: 2s opacity breath only (no glow, no scaling)

LINKS
- Same color as text-secondary, underlined on hover (1px solid border-bottom #36425a)
- Never bright blue. Never cyan.

STACK: Tailwind + shadcn/ui, TypeScript, no external libs unless explicitly specified.
ABSOLUTELY DO NOT use: bright blue links, cyan accents on buttons, glowing status pills, drop shadows on cards, fully-rounded pills, scale animations on hover, spring easing, gradient backgrounds, decorative blur effects, or rounded-full radius on anything except dot indicators.
```

---

## 12. Migration from current shipped UI

Surfaces shipped through Phase 7.12 used cyan as a brand-flowing accent. The pivot to v1 tokens requires the following surgical edits to existing components. Estimated effort: 4–6 hours of Cursor work.

| Surface | Current | New | Effort |
|---|---|---|---|
| Sidebar logo / brand mark | Cyan accent | Neutral white `#e8ebf0` | 5 min |
| Active tab indicators | Cyan bottom border | White (`--text-primary`) bottom border | 15 min |
| Selected sidebar item | Cyan left border | White (`--text-primary`) left border + `--surface-elevated` bg | 15 min |
| Primary CTA buttons | Cyan-filled | White-filled (`--neutral-100` bg, `--text-inverse` text) | 30 min |
| Focused input rings | Cyan ring | White ring (`--neutral-100`) | 20 min |
| Status pills | Full-rounded with glow | 2px radius, no glow, solid dot | 45 min |
| Card border-radius | 12px | 6px | 10 min |
| Card shadows (if any) | Drop shadow | Removed; rely on border | 30 min |
| Table row height | 40px | 36px | 5 min |
| Card padding | 24px default | 16px default | 30 min |
| Geist Sans/Mono import | Geist | IBM Plex Sans/Mono | 30 min |
| SSE green dot (Phase 7.6) | **Keep cyan** | Unchanged — this is the one allowed cyan use | 0 min |
| Streaming pulse animation | Glow pulse | Opacity breath only, no glow | 20 min |

Start the migration with the typography swap (Plex import) — it's a one-file change in `app/layout.tsx` and visibly shifts the entire UI character before any other token applies. Then radii, then color swaps, then density.

---

## 13. Governance

- **Source of truth:** this file. Changes ship as PRs to `docs/design-tokens.md` with a brief justification in the commit message.
- **Versioning:** semver. v1 is the initial enterprise calibration. Breaking changes (renamed tokens, removed values) require a major bump and migration notes.
- **Deprecation policy:** when a token is replaced, mark with `@deprecated` comment and keep it for one minor version before removal.
- **No tokens added without a use case.** If a new color/size/radius is needed for a single component, the question is whether the component is wrong, not whether the token system is incomplete.
- **No tokens added "in case we need them later."** Add when needed, not before.

---

*End of v1.*
