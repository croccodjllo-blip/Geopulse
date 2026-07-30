#!/usr/bin/env python3
"""Extract UI strings and auto-translate missing gettext entries with OpenAI.

Run after editing templates / wrapped Python strings:

  python scripts/i18n_auto_translate.py

Options:
  --force          retranslate all strings (not only empty msgstr)
  --fuzzy          also retranslate fuzzy msgstr (recommended after babel update)
  --skip-extract   only fill/compile existing .po files
  --model NAME     OpenAI model (default gpt-4o-mini or I18N_MODEL)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from babel.messages.catalog import Catalog  # noqa: E402
from babel.messages.pofile import read_po, write_po  # noqa: E402

LOCALES = {
    "en": "en",
    "de": "de",
    "es": "es",
    "zh": "zh_Hans",
    "ko": "ko",
}

LANG_NAMES = {
    "en": "English",
    "de": "German",
    "es": "Spanish",
    "zh": "Simplified Chinese",
    "ko": "Korean",
}


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def extract_and_update() -> None:
    pot = ROOT / "translations" / "messages.pot"
    pot.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            sys.executable,
            "-m",
            "babel.messages.frontend",
            "extract",
            "-F",
            "babel.cfg",
            "-k",
            "_",
            "-k",
            "gettext",
            "-o",
            str(pot),
            ".",
        ]
    )
    for babel_loc in LOCALES.values():
        po = ROOT / "translations" / babel_loc / "LC_MESSAGES" / "messages.po"
        po.parent.mkdir(parents=True, exist_ok=True)
        cmd = "update" if po.exists() else "init"
        run(
            [
                sys.executable,
                "-m",
                "babel.messages.frontend",
                cmd,
                "-i",
                str(pot),
                "-d",
                "translations",
                "-l",
                babel_loc,
            ]
        )


def translate_batch(texts: list[str], target: str, model: str) -> dict[str, str]:
    if not texts:
        return {}
    from openai import OpenAI

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    lang = LANG_NAMES[target]
    system = (
        "You are a professional UI localization engine for Centropic "
        "(AI visibility / GEO SaaS). Translate from Italian to "
        f"{lang}. Keep product names Centropic, AIO, GEO, Plus, llms.txt, "
        "JSON-LD, ChatGPT, Claude, Perplexity, Edge Signals, Schema.org "
        "unchanged. Preserve HTML entities, placeholders like %(name)s, "
        "and punctuation. Return ONLY JSON."
    )
    result: dict[str, str] = {}
    batch_size = 35
    for start in range(0, len(texts), batch_size):
        chunk = texts[start : start + batch_size]
        resp = client.chat.completions.create(
            model=model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": (
                        'Respond as {"translations": {"<italian>": "<translated>", ...}} '
                        "using each source string exactly as key.\n\n"
                        + json.dumps(chunk, ensure_ascii=False, indent=2)
                    ),
                },
            ],
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
        mapping = data.get("translations") if isinstance(data, dict) else None
        if not isinstance(mapping, dict):
            mapping = data if isinstance(data, dict) else {}
        for src in chunk:
            val = mapping.get(src)
            if isinstance(val, str) and val.strip():
                result[src] = val.strip()
        print(f"  translated batch {start + 1}-{start + len(chunk)} → {len(result)} total")
        time.sleep(0.25)
    return result


def fill_locale(
    short: str, babel_loc: str, *, force: bool, fuzzy: bool, model: str
) -> int:
    po_path = ROOT / "translations" / babel_loc / "LC_MESSAGES" / "messages.po"
    with po_path.open("r", encoding="utf-8") as fh:
        catalog: Catalog = read_po(fh)
    targets: list[str] = []
    for msg in catalog:
        if not msg.id or msg.id == "":
            continue
        if isinstance(msg.id, tuple):
            continue
        empty = not (msg.string or "").strip()
        if force or empty or (fuzzy and msg.fuzzy):
            targets.append(str(msg.id))
    # dedupe preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for t in targets:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    print(f"[{short}/{babel_loc}] to translate: {len(uniq)}")
    if not uniq:
        return 0
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY required for auto-translate")
    mapping = translate_batch(uniq, short, model)
    updated = 0
    for msg in catalog:
        if not msg.id or isinstance(msg.id, tuple):
            continue
        new = mapping.get(str(msg.id))
        if new:
            msg.string = new
            if msg.fuzzy and "fuzzy" in msg.flags:
                msg.flags.discard("fuzzy")
            updated += 1
    with po_path.open("wb") as fh:
        write_po(fh, catalog, ignore_obsolete=True)
    return updated


def compile_all() -> None:
    run(
        [
            sys.executable,
            "-m",
            "babel.messages.frontend",
            "compile",
            "-d",
            "translations",
            "--statistics",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--fuzzy",
        action="store_true",
        help="Retranslate fuzzy entries (wrong fuzzy matches after update)",
    )
    parser.add_argument("--skip-extract", action="store_true")
    parser.add_argument("--model", default=os.getenv("I18N_MODEL", "gpt-4o-mini"))
    args = parser.parse_args()
    if not args.skip_extract:
        extract_and_update()
    total = 0
    for short, babel_loc in LOCALES.items():
        total += fill_locale(
            short,
            babel_loc,
            force=args.force,
            fuzzy=args.fuzzy,
            model=args.model,
        )
    compile_all()
    print(f"Done. Filled {total} msgstr entries across {len(LOCALES)} locales.")
    print("Re-run this script whenever you edit wrapped UI strings.")


if __name__ == "__main__":
    main()
