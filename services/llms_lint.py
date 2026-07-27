"""Semantic lint for llms.txt and ai.txt beyond presence checks."""

from __future__ import annotations

import re
from typing import Any

SECTION_RE = re.compile(r"^##?\s+(.+)$", re.M)


def lint_llms_txt(text: str, *, present: bool) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    if not present:
        return {
            "score": 0,
            "present": False,
            "findings": [
                {
                    "category": "aio",
                    "severity": "warn",
                    "title": "llms.txt lint: file assente",
                    "detail": "Pubblica /llms.txt in root.",
                    "evidence": "measured",
                }
            ],
        }

    text = text or ""
    sections = [m.group(1).strip().lower() for m in SECTION_RE.finditer(text)]
    urls = re.findall(r"https?://[^\s)]+", text)
    has_contact = bool(re.search(r"contact|email|@", text, re.I))
    has_citation = bool(re.search(r"preferred citation|citation|cita", text, re.I))
    has_disambig = bool(re.search(r"\bGEO\b.*\bGIS\b|\bAIO\b.*All-in-One", text, re.I))
    score = 20
    score += min(30, len(sections) * 6)
    score += min(20, len(urls) * 2)
    score += 10 if has_contact else 0
    score += 10 if has_citation else 0
    score += 10 if has_disambig else 0
    score = min(100, score)

    missing = []
    if not has_contact:
        missing.append("Contact")
    if not has_citation:
        missing.append("Preferred citation")
    if len(urls) < 3:
        missing.append("URL canonici")
    if len(sections) < 2:
        missing.append("sezioni ##")

    if score >= 70:
        findings.append(
            {
                "category": "aio",
                "severity": "ok",
                "title": "llms.txt lint OK",
                "detail": f"Sezioni {len(sections)} · URL {len(urls)} · score {score}.",
                "evidence": "measured",
            }
        )
    else:
        findings.append(
            {
                "category": "aio",
                "severity": "warn",
                "title": "llms.txt lint: migliorabile",
                "detail": "Manca: " + (", ".join(missing) if missing else "profondità semantica"),
                "evidence": "estimated",
            }
        )

    return {
        "present": True,
        "score": score,
        "sections": sections[:20],
        "url_count": len(urls),
        "findings": findings,
    }


def lint_ai_txt(text: str, *, present: bool) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    if not present:
        return {
            "score": 0,
            "present": False,
            "findings": [
                {
                    "category": "aio",
                    "severity": "warn",
                    "title": "ai.txt lint: file assente",
                    "detail": "Pubblica /ai.txt con policy Allow/Disallow per training/crawler.",
                    "evidence": "measured",
                }
            ],
        }
    text = text or ""
    has_contact = bool(re.search(r"contact|@", text, re.I))
    has_allow = bool(re.search(r"allow|disallow", text, re.I))
    has_llms_ref = bool(re.search(r"llms\.txt", text, re.I))
    score = 40 + (20 if has_contact else 0) + (20 if has_allow else 0) + (20 if has_llms_ref else 0)
    if score >= 70:
        findings.append(
            {
                "category": "aio",
                "severity": "ok",
                "title": "ai.txt lint OK",
                "detail": f"Policy machine-readable presente (score {score}).",
                "evidence": "measured",
            }
        )
    else:
        findings.append(
            {
                "category": "aio",
                "severity": "warn",
                "title": "ai.txt lint debole",
                "detail": "Aggiungi contact, Allow/Disallow e link a llms.txt.",
                "evidence": "estimated",
            }
        )
    return {"present": True, "score": score, "findings": findings}
