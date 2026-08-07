# Contrast verification — Phase 8.0 palette

Measured, not eyeballed. Regenerate with:

```bash
cd apps/backend && uv run python ../../scripts/check-contrast.py
```

The script exits non-zero if any non-exempt pair falls below its WCAG 2.1
threshold, so it can be wired into CI later. Ratios below were produced against
the palette committed in `apps/frontend/app/globals.css`.

## Palette under test

| Role | Token | Value |
|---|---|---|
| Page | `--surface-page` | `#0b0c0e` |
| Chrome | `--surface-chrome` | `#08090b` |
| Card | `--surface-card` | `#111214` |
| Elevated | `--surface-elevated` | `#17181b` |
| Input | `--surface-input` | `#0e0f11` |
| Text primary | `--text-primary` | `#ecedef` |
| Text secondary | `--text-secondary` | `#a8adb5` |
| Text tertiary | `--text-tertiary` | `#82878f` |
| Text disabled | `--text-disabled` | `#4a4e55` |

## Text on surfaces

Threshold: 4.5:1 for body text (WCAG 2.1 AA, 1.4.3).

| Token | page | chrome | card | elevated | input | Verdict |
|---|---|---|---|---|---|---|
| primary | 16.70 | 17.00 | 16.00 | 15.15 | 16.37 | PASS |
| secondary | 8.67 | 8.83 | 8.31 | 7.87 | 8.50 | PASS |
| tertiary | 5.42 | 5.51 | 5.19 | 4.91 | 5.31 | PASS |
| disabled | 2.34 | 2.38 | 2.24 | 2.12 | 2.29 | Exempt |

`--text-disabled` is intentionally below threshold: WCAG 1.4.3 exempts inactive
controls, and a disabled control that meets full body contrast does not read as
disabled. It must never be used for content the user is expected to read.

`--text-tertiary` was moved from the initially-chosen `#7a7f87` to `#82878f`
during this phase: the darker value measured 4.41 against `--surface-elevated`,
which fails body AA. The published value clears 4.5 on every surface while
staying visibly subordinate to `--text-secondary` (~8:1).

## Semantic status ramp

Threshold: 3.0:1 (non-text / large-text indicators). These colours are unchanged
from the Carbon-derived ramp — the point of the neutral surfaces is that they
carry more of their own signal without raising saturation.

| Token | page | card | Verdict |
|---|---|---|---|
| denied `#fa4d56` | 5.83 | 5.59 | PASS |
| held `#f1c21b` | 11.62 | 11.13 | PASS |
| ok `#42be65` | 8.19 | 7.84 | PASS |
| info `#78a9ff` | 8.31 | 7.96 | PASS |
| live cyan `#22d3ee` | 10.83 | 10.37 | PASS |

**Blocking failures: 0.**

## Scope note

This covers the token layer. Phase 8.0 also remapped a parallel set of
hardcoded hex values (`#6b7490`, `#a0a8bc`, `#f0f2f8`, `#0a0a14`, `#080810` and
the ad-hoc reds/greens `#f87171` / `#e05050` / `#34d399`) that had accumulated
outside the token system across ~12 files, folding them onto these tokens and
onto the canonical status ramp. Without that, only part of the app would have
changed palette.

Not covered here, and deferred to Phase 8.1 with the rest of the visual work:
depth/elevation treatment, empty-state redesign, the sidebar, and the motion
system. The login page keeps its `#4ab7ff` accent, which is a deliberate
auth-page brand accent rather than palette drift.
