from pathlib import Path


def test_no_bare_or_broad_except_outside_main() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "axiom"
    bad: list[str] = []
    for path in root.rglob("*.py"):
        if path.name == "main.py":
            continue
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("except:"):
                bad.append(f"{path}:{i}:{stripped}")
            if "except Exception" in line and "noqa" not in line:
                bad.append(f"{path}:{i}:{stripped}")
    assert not bad, "Broad/bare except found:\n" + "\n".join(bad)
