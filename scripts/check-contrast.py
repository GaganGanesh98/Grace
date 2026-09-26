"""WCAG 2.1 contrast checker for Grace's theme tokens.

Reads the Midnight (`.dark`) and Daylight (`:root`) token blocks straight out of
apps/frontend/app/globals.css -- so what is measured is what ships, not a copy
that can drift -- resolves `var(--x)` references, converts OKLCH to sRGB, and
checks every text/background pairing the UI actually uses.

    uv run --project apps/backend python scripts/check-contrast.py [path/to/globals.css]

Exits non-zero if any pair falls below its threshold.
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

DEFAULT_CSS = Path(__file__).resolve().parents[1] / "apps" / "frontend" / "app" / "globals.css"

# (label, foreground token, background token, minimum ratio)
# 4.5:1 = WCAG 1.4.3 body text. 3.0:1 = WCAG 1.4.11 non-text / graphical.
PAIRS: list[tuple[str, str, str, float]] = [
    ("body text on page", "--foreground", "--background", 4.5),
    ("body text on card", "--foreground", "--card", 4.5),
    ("body text on sidebar", "--foreground", "--sidebar-bg", 4.5),
    ("muted text on page", "--muted-foreground", "--background", 4.5),
    ("muted text on card", "--muted-foreground", "--card", 4.5),
    ("muted text on sidebar", "--muted-foreground", "--sidebar-bg", 4.5),
    ("muted text on secondary", "--muted-foreground", "--secondary", 4.5),
    ("muted text on table header", "--muted-foreground", "--surface-muted", 4.5),
    ("secondary text on card", "--secondary-foreground", "--card", 4.5),
    ("active nav text", "--accent-foreground", "--accent", 4.5),
    ("link text on card", "--accent-foreground", "--card", 4.5),
    ("primary button text", "--primary-foreground", "--primary", 4.5),
    ("primary button text, hover", "--primary-foreground", "--primary-hover", 4.5),
    ("secondary button text", "--secondary-foreground", "--secondary", 4.5),
    ("allow badge text", "--success-strong", "--success-soft", 4.5),
    ("hold badge text", "--warning-strong", "--warning-soft", 4.5),
    ("deny badge text", "--danger-strong", "--danger-soft", 4.5),
    ("info badge text", "--info-strong", "--info-soft", 4.5),
    ("allow text on card", "--success-strong", "--card", 4.5),
    ("hold text on card", "--warning-strong", "--card", 4.5),
    ("deny text on card", "--danger-strong", "--card", 4.5),
    ("info text on card", "--info-strong", "--card", 4.5),
    ("success mark on card", "--success", "--card", 3.0),
    ("warning mark on card", "--warning", "--card", 3.0),
    ("danger mark on card", "--danger", "--card", 3.0),
    ("info mark on card", "--info", "--card", 3.0),
    ("live dot on sidebar", "--info", "--sidebar-bg", 3.0),
    ("focus ring on page", "--ring", "--background", 3.0),
]


def _block(css: str, selector: str) -> dict[str, str]:
    """Return {--token: raw value} for the first `selector { ... }` block."""
    m = re.search(re.escape(selector) + r"\s*\{(.*?)\}", css, re.DOTALL)
    if not m:
        raise SystemExit(f"selector {selector!r} not found")
    return {k.strip(): v.strip() for k, v in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", m.group(1))}


def _resolve(tokens: dict[str, str], name: str, depth: int = 0) -> str:
    if depth > 10:
        raise SystemExit(f"var() cycle resolving {name}")
    value = tokens[name]
    ref = re.fullmatch(r"var\((--[\w-]+)\)", value)
    return _resolve(tokens, ref.group(1), depth + 1) if ref else value


def _oklch_to_srgb(value: str) -> tuple[float, float, float]:
    m = re.fullmatch(r"oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\)", value)
    if not m:
        raise SystemExit(f"unsupported colour {value!r} (expected oklch(L C H))")
    lightness, chroma, hue = (float(g) for g in m.groups())
    a = chroma * math.cos(math.radians(hue))
    b = chroma * math.sin(math.radians(hue))
    l_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    lin = (
        4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
        -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
        -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_,
    )
    # Browsers gamut-map out-of-range colours; clamping is the conservative stand-in.
    return tuple(min(1.0, max(0.0, c)) for c in lin)  # type: ignore[return-value]


def _luminance(value: str) -> float:
    r, g, b = _oklch_to_srgb(value)  # already linear-light sRGB
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _ratio(fg: str, bg: str) -> float:
    a, b = _luminance(fg), _luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def main(argv: list[str]) -> int:
    css_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_CSS
    css = css_path.read_text(encoding="utf-8")
    failures = 0
    for theme, selector in (("Daylight", ":root"), ("Midnight", ".dark")):
        tokens = _block(css, ":root")
        if selector != ":root":
            tokens = {**tokens, **_block(css, selector)}
        print(f"\n{theme}  ({selector})")
        print(f"  {'pair':<28} {'ratio':>6}  need  result")
        for label, fg, bg, need in PAIRS:
            ratio = _ratio(_resolve(tokens, fg), _resolve(tokens, bg))
            ok = ratio >= need
            failures += not ok
            print(f"  {label:<28} {ratio:>6.2f}  {need:>4}  {'PASS' if ok else 'FAIL'}")
    print(f"\nblocking failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
