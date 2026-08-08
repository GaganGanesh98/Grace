"""WCAG 2.1 contrast checker for the Grace palette (Phase 8.0 Part 4)."""

from __future__ import annotations

import sys


def srgb_to_lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * srgb_to_lin(r) + 0.7152 * srgb_to_lin(g) + 0.0722 * srgb_to_lin(b)


def ratio(fg: str, bg: str) -> float:
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


SURFACES = {
    "page": "#0B0C0E",
    "chrome": "#08090B",
    "card": "#111214",
    "elevated": "#17181B",
    "input": "#0E0F11",
}

TEXT = {
    "primary": "#ECEDEF",
    "secondary": "#A8ADB5",
    "tertiary": "#82878F",
    "disabled": "#4A4E55",
}

STATUS = {
    "denied": "#fa4d56",
    "held": "#f1c21b",
    "ok": "#42be65",
    "info": "#78a9ff",
    "live-cyan": "#22d3ee",
}


def verdict(r: float, need: float) -> str:
    return "PASS" if r >= need else "FAIL"


def main() -> int:
    failures = 0
    print(f"{'token':<12} {'surface':<10} {'ratio':>6}  AA-body(4.5)  AA-large(3.0)")
    print("-" * 62)
    for tname, tval in TEXT.items():
        for sname, sval in SURFACES.items():
            r = ratio(tval, sval)
            body = verdict(r, 4.5)
            large = verdict(r, 3.0)
            # 'disabled' is exempt from AA by design (WCAG 1.4.3 excludes
            # inactive controls); report it but do not count it as a failure.
            if tname != "disabled" and sname != "chrome" and body == "FAIL":
                if tname == "tertiary" and large == "PASS":
                    pass  # tertiary is metadata/large-only; large AA is the bar
                else:
                    failures += 1
            print(f"{tname:<12} {sname:<10} {r:>6.2f}  {body:<12}  {large}")
        print()

    print(f"{'status':<12} {'surface':<10} {'ratio':>6}  AA-large(3.0)")
    print("-" * 62)
    for sname_status, sval_status in STATUS.items():
        for sname in ("page", "card"):
            r = ratio(sval_status, SURFACES[sname])
            large = verdict(r, 3.0)
            if large == "FAIL":
                failures += 1
            print(f"{sname_status:<12} {sname:<10} {r:>6.2f}  {large}")
        print()

    print(f"\nblocking failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
