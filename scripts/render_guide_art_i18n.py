#!/usr/bin/env python3
"""Generate locale-specific copies of the Italian guide SVGs."""

from __future__ import annotations

from pathlib import Path

from services.guide_art_i18n import (
    GUIDE_ART_LOCALES,
    ITALIAN_LEAKS,
    localize_guide_svg,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "static" / "img" / "guide"


def main() -> None:
    sources = sorted(
        p for p in SRC.glob("*.svg") if p.is_file() and p.parent == SRC
    )
    if not sources:
        raise SystemExit(f"no source SVGs in {SRC}")
    for loc in GUIDE_ART_LOCALES:
        dest = SRC / loc
        dest.mkdir(parents=True, exist_ok=True)
        for src in sources:
            svg = src.read_text(encoding="utf-8")
            out = localize_guide_svg(svg, loc)
            leaks = [n for n in ITALIAN_LEAKS if n in out]
            if leaks:
                raise SystemExit(f"{loc}/{src.name} still has {leaks!r}")
            (dest / src.name).write_text(out, encoding="utf-8")
        print(f"wrote {len(sources)} SVGs → {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
