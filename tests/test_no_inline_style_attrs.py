"""Templates must not use HTML style= (CSP style-src-attr 'none')."""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1] / "templates"
_STYLE_ATTR = re.compile(r"\sstyle\s*=", re.I)


def test_templates_have_no_style_attributes():
    bad: list[str] = []
    for path in sorted(_ROOT.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"\{#.*?#\}", "", text, flags=re.S)
        text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        for i, line in enumerate(text.splitlines(), 1):
            if _STYLE_ATTR.search(line):
                bad.append(f"{path.relative_to(_ROOT.parent)}:{i}: {line.strip()[:100]}")
    assert bad == [], "Inline style= attrs found:\n" + "\n".join(bad)
