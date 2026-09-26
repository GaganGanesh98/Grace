# Contrast verification — Phase 8.3 Midnight / Daylight palette

Measured, not eyeballed. Regenerate with:

```bash
uv run --project apps/backend python scripts/check-contrast.py
```

The script reads the token blocks straight out of
`apps/frontend/app/globals.css` (`.dark` = Midnight, `:root` = Daylight), so it
measures what ships rather than a copy that can drift. It resolves `var()`
aliases, converts OKLCH to sRGB (clamping out-of-gamut channels, the
conservative stand-in for browser gamut mapping), and exits non-zero if any pair
falls below its WCAG 2.1 threshold.

## Thresholds

- **4.5:1** — body text (WCAG 1.4.3). Every text pair below uses this.
- **3.0:1** — graphical objects and focus indicators (WCAG 1.4.11): status
  marks, the live dot, the focus ring.

## Results

| Pair | Midnight | Daylight | Need | Verdict |
|---|---|---|---|---|
| body text on page | 16.39 | 17.78 | 4.5:1 | PASS |
| body text on card | 15.49 | 18.83 | 4.5:1 | PASS |
| body text on sidebar | 16.79 | 17.01 | 4.5:1 | PASS |
| muted text on page | 6.78 | 6.75 | 4.5:1 | PASS |
| muted text on card | 6.41 | 7.15 | 4.5:1 | PASS |
| muted text on sidebar | 6.94 | 6.46 | 4.5:1 | PASS |
| muted text on secondary | 5.79 | 6.27 | 4.5:1 | PASS |
| muted text on table header | 6.58 | 6.55 | 4.5:1 | PASS |
| secondary text on card | 13.70 | 14.62 | 4.5:1 | PASS |
| active nav text | 9.16 | 7.64 | 4.5:1 | PASS |
| link text on card | 11.41 | 9.18 | 4.5:1 | PASS |
| primary button text | 4.88 | 5.65 | 4.5:1 | PASS |
| primary button text, hover | 5.82 | 7.06 | 4.5:1 | PASS |
| secondary button text | 12.38 | 12.82 | 4.5:1 | PASS |
| allow badge text | 7.82 | 6.56 | 4.5:1 | PASS |
| hold badge text | 8.34 | 6.74 | 4.5:1 | PASS |
| deny badge text | 6.37 | 6.01 | 4.5:1 | PASS |
| info badge text | 6.40 | 5.09 | 4.5:1 | PASS |
| allow text on card | 9.80 | 7.71 | 4.5:1 | PASS |
| hold text on card | 10.84 | 7.61 | 4.5:1 | PASS |
| deny text on card | 8.11 | 7.20 | 4.5:1 | PASS |
| info text on card | 8.31 | 5.84 | 4.5:1 | PASS |
| success mark on card | 8.00 | 4.21 | 3.0:1 | PASS |
| warning mark on card | 9.12 | 3.43 | 3.0:1 | PASS |
| danger mark on card | 6.33 | 4.22 | 3.0:1 | PASS |
| info mark on card | 8.31 | 3.63 | 3.0:1 | PASS |
| live dot on sidebar | 9.01 | 3.28 | 3.0:1 | PASS |
| focus ring on page | 3.89 | 5.48 | 3.0:1 | PASS |

**Blocking failures: 0** in both themes.

## Deviations from the Lovable export

The palette is Lovable's Grace design, with lightness-only tuning where it
failed a check (hue and chroma unchanged; each change is commented in
`globals.css`):

- Midnight `--primary` 0.65 → 0.56 (and `--primary-hover` to match): white
  button text was below 4.5:1.
- Daylight `--warning` tuned so warning marks clear 3:1 on cards.
- Daylight `--info` 0.63 → 0.60: the live-connection dot was 2.93:1 on the
  sidebar.
- Added `--info-strong` for Daylight: Lovable used `--info` for badge text at
  2.83:1.

## Rules for components

- Text uses the `-strong` status tokens (`--success-strong`, …) or the
  `text-status-*-fg` utilities. The base status tokens (`--success`, …) are only
  verified at 3:1 and are for marks, rings and dots.
- `--text-disabled` is intentionally below 4.5:1 (WCAG exempts inactive
  controls). Never use it for content the user is expected to read.
- New colour literals in components are a regression: they will not follow the
  theme. Use a token.
