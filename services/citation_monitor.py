"""Multi-engine citation / measured SoV monitor.

OpenAI / Perplexity / Anthropic (Claude) / Google AI (Gemini) / xAI (Grok) /
Microsoft Copilot (Azure AI Foundry project) = measured when credentials are set.

Keys are read at call-time (not only at import) so load_dotenv / systemd env stay in sync.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import ContextVar
from typing import Any

from services.llm_retry import (
    call_with_retries,
    estimate_tpm_tokens,
    http_should_retry,
    probe_pacing_seconds,
)
from services.prompt_bank import default_prompts

logger = logging.getLogger(__name__)
_SOV_USAGE_ACTIVE: ContextVar[bool] = ContextVar(
    "sov_usage_active",
    default=False,
)


def is_sov_usage_call() -> bool:
    """True while the citation monitor invokes its billing callback."""
    return _SOV_USAGE_ACTIVE.get()


def _env(*names: str, default: str = "") -> str:
    for name in names:
        val = (os.getenv(name) or "").strip()
        if val:
            return val
    return default


def _openai_key() -> str:
    return _env("OPENAI_API_KEY")


def _openai_model() -> str:
    return _env("OPENAI_MODEL", default="gpt-4o-mini") or "gpt-4o-mini"


def _perplexity_key() -> str:
    return _env("PERPLEXITY_API_KEY")


def _perplexity_model() -> str:
    return _env("PERPLEXITY_MODEL", default="sonar") or "sonar"


def _anthropic_key() -> str:
    return _env("ANTHROPIC_API_KEY", "CLAUDE_API_KEY")


def _anthropic_model() -> str:
    return (
        _env("ANTHROPIC_MODEL", "CLAUDE_MODEL", default="claude-haiku-4-5-20251001")
        or "claude-haiku-4-5-20251001"
    )


def _anthropic_version() -> str:
    return _env("ANTHROPIC_API_VERSION", default="2023-06-01") or "2023-06-01"


def _gemini_key() -> str:
    return _env("GEMINI_API_KEY", "GOOGLE_AI_API_KEY", "GOOGLE_API_KEY")


def _gemini_model() -> str:
    return (
        _env("GEMINI_MODEL", "GOOGLE_AI_MODEL", default="gemini-flash-latest")
        or "gemini-flash-latest"
    )


def _xai_key() -> str:
    return _env("XAI_API_KEY", "GROK_API_KEY")


def _xai_model() -> str:
    return (
        _env("XAI_MODEL", "GROK_MODEL", default="grok-4-1-fast-non-reasoning")
        or "grok-4-1-fast-non-reasoning"
    )


def _azure_project_endpoint() -> str:
    """Foundry project endpoint (includes project path). No separate project_name in SDK v2."""
    return _env(
        "AZURE_AI_PROJECT_ENDPOINT",
        "FOUNDRY_PROJECT_ENDPOINT",
        "AZURE_AI_ENDPOINT",
        "AZURE_OPENAI_ENDPOINT",
    )


def _azure_ai_api_key() -> str:
    """Azure AI / Foundry / Cognitive Services API key (alternative to Entra ID)."""
    return _env(
        "AZURE_AI_API_KEY",
        "FOUNDRY_API_KEY",
        "AZURE_API_KEY",
        "AZURE_OPENAI_API_KEY",
    )


def _azure_ai_model() -> str:
    return (
        _env(
            "AZURE_AI_MODEL",
            "FOUNDRY_MODEL_NAME",
            "AZURE_OPENAI_DEPLOYMENT",
            default="gpt-4o-mini",
        )
        or "gpt-4o-mini"
    )


def _azure_ai_agent_name() -> str:
    """Optional Foundry Agent with Bing grounding — prefer for Copilot-like answers."""
    return _env("AZURE_AI_AGENT_NAME", "FOUNDRY_AGENT_NAME")


def _azure_configured() -> bool:
    """Endpoint + (API key or Entra ID service principal / DefaultAzureCredential)."""
    if not _azure_project_endpoint():
        return False
    if _azure_ai_api_key():
        return True
    if _env("AZURE_CLIENT_ID") and _env("AZURE_TENANT_ID") and _env("AZURE_CLIENT_SECRET"):
        return True
    return _env("AZURE_AI_USE_DEFAULT_CREDENTIAL", default="0") == "1"


def _azure_credential():
    tenant = _env("AZURE_TENANT_ID")
    client_id = _env("AZURE_CLIENT_ID")
    secret = _env("AZURE_CLIENT_SECRET")
    if tenant and client_id and secret:
        from azure.identity import ClientSecretCredential

        return ClientSecretCredential(
            tenant_id=tenant, client_id=client_id, client_secret=secret
        )
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential(exclude_interactive_browser_credential=True)


def _azure_openai_base_url(endpoint: str) -> str:
    """OpenAI-compatible base URL for Foundry / Azure AI resources.

    Project endpoints look like
    ``https://{resource}.services.ai.azure.com/api/projects/{project}``.
    Chat/completions with API key typically use the resource root
    ``…/openai/v1`` (not under ``/api/projects/…``).
    """
    base = endpoint.rstrip("/")
    if base.endswith("/openai/v1"):
        return base
    if "/api/projects/" in base:
        resource = base.split("/api/projects/", 1)[0].rstrip("/")
        return f"{resource}/openai/v1"
    return f"{base}/openai/v1"


# Back-compat aliases (may be empty if read before load_dotenv in odd import orders).
OPENAI_API_KEY = _openai_key()
OPENAI_MODEL = _openai_model()
PERPLEXITY_API_KEY = _perplexity_key()
PERPLEXITY_MODEL = _perplexity_model()
ANTHROPIC_API_KEY = _anthropic_key()
ANTHROPIC_MODEL = _anthropic_model()
ANTHROPIC_API_VERSION = _anthropic_version()
GEMINI_API_KEY = _gemini_key()
GEMINI_MODEL = _gemini_model()
XAI_API_KEY = _xai_key()
XAI_MODEL = _xai_model()
AZURE_AI_PROJECT_ENDPOINT = _azure_project_endpoint()
AZURE_AI_MODEL = _azure_ai_model()


def citation_monitor_available() -> bool:
    return bool(
        _openai_key()
        or _perplexity_key()
        or _anthropic_key()
        or _gemini_key()
        or _xai_key()
        or _azure_configured()
    )


def _normalize_needle(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _needles(brand: str, domain: str) -> set[str]:
    raw = {(brand or "").strip(), (domain or "").strip()}
    out: set[str] = set()
    for item in raw:
        if not item or len(item) < 3:
            continue
        out.add(item.lower())
        compact = _normalize_needle(item)
        if len(compact) >= 3:
            out.add(compact)
        if "." in item:
            apex = item.split(".")[0].lower()
            if len(apex) >= 3:
                out.add(apex)
                out.add(_normalize_needle(apex))
    return out


def _mentioned(text: str, needles: set[str]) -> bool:
    blob = text or ""
    lower = blob.lower()
    compact = _normalize_needle(blob)
    for n in needles:
        if not n:
            continue
        if n in lower or (len(n) >= 3 and n in compact):
            return True
    return False


def _probe_openai(
    prompts: list[str],
    needles: set[str],
    usage_callback: Any | None = None,
) -> dict[str, Any]:
    api_key = _openai_key()
    model = _openai_model()
    if not api_key:
        return {"available": False, "reason": "OPENAI_API_KEY assente", "details": []}
    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover
        return {"available": False, "reason": str(exc), "details": []}

    # max_retries=0: we own pacing/backoff to avoid stampedes across prompts.
    client = OpenAI(api_key=api_key, timeout=45.0, max_retries=0)
    hits = 0
    details: list[dict[str, Any]] = []
    pace = probe_pacing_seconds()
    for idx, prompt in enumerate(prompts):
        if idx and pace:
            time.sleep(pace)
        try:

            def _once(p: str = prompt) -> Any:
                return client.chat.completions.create(
                    model=model,
                    temperature=0.2,
                    max_tokens=350,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Rispondi in modo fattuale. Cita brand solo se li conosci; "
                                "non inventare URL."
                            ),
                        },
                        {"role": "user", "content": p},
                    ],
                )

            resp = call_with_retries(
                _once,
                retries=5,
                label="openai-sov",
                tokens=estimate_tpm_tokens(prompt_chars=len(prompt or "") + 200, max_output=350),
            )
            if hasattr(resp, "usage") and resp.usage and usage_callback:
                usage_callback(
                    provider="openai",
                    model=model,
                    input_tokens=resp.usage.prompt_tokens,
                    output_tokens=resp.usage.completion_tokens,
                )
            text = (resp.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.warning("openai citation probe failed: %s", str(exc)[:200])
            details.append({"prompt": prompt, "error": str(exc)[:160]})
            continue
        ok = _mentioned(text, needles)
        if ok:
            hits += 1
        details.append(
            {"prompt": prompt, "mentioned": ok, "excerpt": text[:280], "engine": "openai"}
        )
    ok_details = [d for d in details if "error" not in d]
    if not ok_details:
        return {
            "available": False,
            "reason": "OpenAI probe fallito su tutti i prompt",
            "details": details,
        }
    total = max(1, len(ok_details))
    rate = round(100.0 * hits / total)
    return {
        "available": True,
        "mention_rate": rate,
        "hits": hits,
        "samples": total,
        "details": details,
        "evidence": "measured",
        "model": model,
    }


def _probe_perplexity(
    prompts: list[str],
    needles: set[str],
    usage_callback: Any | None = None,
) -> dict[str, Any]:
    api_key = _perplexity_key()
    model = _perplexity_model()
    if not api_key:
        return {"available": False, "reason": "PERPLEXITY_API_KEY assente", "details": []}
    try:
        import requests
    except Exception as exc:  # pragma: no cover
        return {"available": False, "reason": str(exc), "details": []}

    hits = 0
    details: list[dict[str, Any]] = []
    system = "Be factual. Cite real brands only. Answer briefly."
    pace = probe_pacing_seconds()
    for idx, prompt in enumerate(prompts[:3]):
        if idx and pace:
            time.sleep(pace)
        try:

            def _once(p: str = prompt) -> Any:
                res = requests.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "temperature": 0.2,
                        "max_tokens": 350,
                        "messages": [
                            {
                                "role": "user",
                                "content": f"{system}\n\n{p}",
                            }
                        ],
                    },
                    timeout=45,
                )
                if http_should_retry(res.status_code):
                    raise RuntimeError(f"HTTP {res.status_code}: {(res.text or '')[:120]}")
                return res

            res = call_with_retries(
                _once,
                retries=4,
                label="perplexity-sov",
                tokens=estimate_tpm_tokens(prompt_chars=len(prompt or "") + 200, max_output=350),
            )
            if not res.ok:
                err_body = (res.text or "")[:180]
                details.append(
                    {
                        "prompt": prompt,
                        "error": f"HTTP {res.status_code}: {err_body}",
                        "engine": "perplexity",
                    }
                )
                continue
            data = res.json()
            usage = data.get("usage") or {}
            if usage and usage_callback:
                usage_callback(
                    provider="perplexity",
                    model=model,
                    input_tokens=int(usage.get("prompt_tokens", 0)),
                    output_tokens=int(usage.get("completion_tokens", 0)),
                )
            text = (
                ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
                or ""
            ).strip()
        except Exception as exc:
            logger.warning("perplexity citation probe failed: %s", str(exc)[:200])
            details.append(
                {"prompt": prompt, "error": str(exc)[:160], "engine": "perplexity"}
            )
            continue
        ok = _mentioned(text, needles)
        if ok:
            hits += 1
        details.append(
            {
                "prompt": prompt,
                "mentioned": ok,
                "excerpt": text[:280],
                "engine": "perplexity",
            }
        )
    ok_details = [d for d in details if "error" not in d]
    if not ok_details:
        reason = "Perplexity probe fallito su tutti i prompt"
        if details and details[0].get("error"):
            reason = str(details[0]["error"])[:160]
        return {"available": False, "reason": reason, "details": details}
    total = max(1, len(ok_details))
    rate = round(100.0 * hits / total)
    return {
        "available": True,
        "mention_rate": rate,
        "hits": hits,
        "samples": total,
        "details": details,
        "evidence": "measured",
        "model": model,
    }


def _probe_anthropic(
    prompts: list[str],
    needles: set[str],
    usage_callback: Any | None = None,
) -> dict[str, Any]:
    """Claude Messages API — SoV measured probe."""
    api_key = _anthropic_key()
    model = _anthropic_model()
    version = _anthropic_version()
    if not api_key:
        return {"available": False, "reason": "ANTHROPIC_API_KEY assente", "details": []}
    try:
        import requests
    except Exception as exc:  # pragma: no cover
        return {"available": False, "reason": str(exc), "details": []}

    hits = 0
    details: list[dict[str, Any]] = []
    system = (
        "Rispondi in modo fattuale. Cita brand solo se li conosci realmente; "
        "non inventare URL o menzioni."
    )
    for prompt in prompts[:3]:
        try:
            from services.llm_rpm import acquire_rpm
            from services.llm_tpm import acquire_tpm

            acquire_rpm("anthropic")
            acquire_tpm("anthropic", estimate_tpm_tokens(prompt_chars=len(prompt or "") + 280, max_output=350))
            res = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": version,
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 350,
                    "temperature": 0.2,
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=45,
            )
            if not res.ok:
                details.append(
                    {
                        "prompt": prompt,
                        "error": f"HTTP {res.status_code}: {(res.text or '')[:180]}",
                        "engine": "anthropic",
                    }
                )
                continue
            data = res.json()
            usage = data.get("usage") or {}
            if usage and usage_callback:
                usage_callback(
                    provider="anthropic",
                    model=model,
                    input_tokens=int(usage.get("input_tokens", 0)),
                    output_tokens=int(usage.get("output_tokens", 0)),
                )
            parts = data.get("content") or []
            text_bits: list[str] = []
            for part in parts:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_bits.append(str(part.get("text") or ""))
            text = "\n".join(text_bits).strip()
        except Exception as exc:
            logger.exception("anthropic citation probe failed")
            details.append(
                {"prompt": prompt, "error": str(exc)[:160], "engine": "anthropic"}
            )
            continue
        ok = _mentioned(text, needles)
        if ok:
            hits += 1
        details.append(
            {
                "prompt": prompt,
                "mentioned": ok,
                "excerpt": text[:280],
                "engine": "anthropic",
            }
        )
    ok_details = [d for d in details if "error" not in d]
    if not ok_details:
        reason = "Anthropic probe fallito su tutti i prompt"
        if details and details[0].get("error"):
            reason = str(details[0]["error"])[:160]
        return {"available": False, "reason": reason, "details": details}
    total = max(1, len(ok_details))
    rate = round(100.0 * hits / total)
    return {
        "available": True,
        "mention_rate": rate,
        "hits": hits,
        "samples": total,
        "details": details,
        "evidence": "measured",
        "model": model,
    }


def _probe_gemini(
    prompts: list[str],
    needles: set[str],
    usage_callback: Any | None = None,
) -> dict[str, Any]:
    """Google AI Gemini generateContent — SoV measured probe for AI Overview slot."""
    api_key = _gemini_key()
    model = _gemini_model()
    if not api_key:
        return {
            "available": False,
            "reason": "GEMINI_API_KEY / GOOGLE_AI_API_KEY assente",
            "details": [],
        }
    try:
        import requests
    except Exception as exc:  # pragma: no cover
        return {"available": False, "reason": str(exc), "details": []}

    hits = 0
    details: list[dict[str, Any]] = []
    system = (
        "Rispondi in modo fattuale. Cita brand solo se li conosci realmente; "
        "non inventare URL o menzioni."
    )
    for prompt in prompts[:3]:
        try:
            from services.llm_rpm import acquire_rpm
            from services.llm_tpm import acquire_tpm

            acquire_rpm("gemini")
            acquire_tpm("gemini", estimate_tpm_tokens(prompt_chars=len(prompt or "") + 280, max_output=350))
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent"
            )
            res = requests.post(
                url,
                headers={
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.2,
                        "maxOutputTokens": 350,
                    },
                },
                timeout=45,
            )
            if not res.ok:
                details.append(
                    {
                        "prompt": prompt,
                        "error": f"HTTP {res.status_code}: {(res.text or '')[:180]}",
                        "engine": "google",
                    }
                )
                continue
            data = res.json()
            usage = data.get("usageMetadata") or {}
            if usage and usage_callback:
                usage_callback(
                    provider="google",
                    model=model,
                    input_tokens=int(usage.get("promptTokenCount", 0)),
                    output_tokens=int(usage.get("candidatesTokenCount", 0)),
                )
            text_bits: list[str] = []
            for cand in data.get("candidates") or []:
                content = (cand or {}).get("content") or {}
                for part in content.get("parts") or []:
                    if isinstance(part, dict) and part.get("text"):
                        text_bits.append(str(part.get("text") or ""))
            text = "\n".join(text_bits).strip()
        except Exception as exc:
            logger.exception("gemini citation probe failed")
            details.append(
                {"prompt": prompt, "error": str(exc)[:160], "engine": "google"}
            )
            continue
        ok = _mentioned(text, needles)
        if ok:
            hits += 1
        details.append(
            {
                "prompt": prompt,
                "mentioned": ok,
                "excerpt": text[:280],
                "engine": "google",
            }
        )
    ok_details = [d for d in details if "error" not in d]
    if not ok_details:
        reason = "Gemini probe fallito su tutti i prompt"
        if details and details[0].get("error"):
            reason = str(details[0]["error"])[:160]
        return {"available": False, "reason": reason, "details": details}
    total = max(1, len(ok_details))
    rate = round(100.0 * hits / total)
    return {
        "available": True,
        "mention_rate": rate,
        "hits": hits,
        "samples": total,
        "details": details,
        "evidence": "measured",
        "model": model,
    }


def _probe_xai(
    prompts: list[str],
    needles: set[str],
    usage_callback: Any | None = None,
) -> dict[str, Any]:
    """xAI Grok chat/completions — SoV measured probe (OpenAI-compatible API)."""
    api_key = _xai_key()
    model = _xai_model()
    if not api_key:
        return {
            "available": False,
            "reason": "XAI_API_KEY / GROK_API_KEY assente",
            "details": [],
        }
    try:
        import requests
    except Exception as exc:  # pragma: no cover
        return {"available": False, "reason": str(exc), "details": []}

    hits = 0
    details: list[dict[str, Any]] = []
    system = (
        "Rispondi in modo fattuale. Cita brand solo se li conosci realmente; "
        "non inventare URL o menzioni."
    )
    for prompt in prompts[:3]:
        try:
            from services.llm_rpm import acquire_rpm
            from services.llm_tpm import acquire_tpm

            acquire_rpm("xai")
            acquire_tpm("xai", estimate_tpm_tokens(prompt_chars=len(prompt or "") + 280, max_output=350))
            res = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "temperature": 0.2,
                    "max_tokens": 350,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=45,
            )
            if not res.ok:
                details.append(
                    {
                        "prompt": prompt,
                        "error": f"HTTP {res.status_code}: {(res.text or '')[:180]}",
                        "engine": "xai",
                    }
                )
                continue
            data = res.json()
            usage = data.get("usage") or {}
            if usage and usage_callback:
                usage_callback(
                    provider="xai",
                    model=model,
                    input_tokens=int(usage.get("prompt_tokens", 0)),
                    output_tokens=int(usage.get("completion_tokens", 0)),
                )
            text = (
                ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
                or ""
            ).strip()
        except Exception as exc:
            logger.exception("xai/grok citation probe failed")
            details.append(
                {"prompt": prompt, "error": str(exc)[:160], "engine": "xai"}
            )
            continue
        ok = _mentioned(text, needles)
        if ok:
            hits += 1
        details.append(
            {
                "prompt": prompt,
                "mentioned": ok,
                "excerpt": text[:280],
                "engine": "xai",
            }
        )
    ok_details = [d for d in details if "error" not in d]
    if not ok_details:
        reason = "Grok probe fallito su tutti i prompt"
        if details and details[0].get("error"):
            reason = str(details[0]["error"])[:160]
        return {"available": False, "reason": reason, "details": details}
    total = max(1, len(ok_details))
    rate = round(100.0 * hits / total)
    return {
        "available": True,
        "mention_rate": rate,
        "hits": hits,
        "samples": total,
        "details": details,
        "evidence": "measured",
        "model": model,
    }


def _copilot_run_prompts(
    openai_client: Any,
    *,
    model: str,
    prompts: list[str],
    needles: set[str],
    usage_callback: Any | None,
) -> tuple[int, list[dict[str, Any]]]:
    hits = 0
    details: list[dict[str, Any]] = []
    system = (
        "Rispondi in modo fattuale. Cita brand solo se li conosci realmente; "
        "non inventare URL o menzioni."
    )
    for prompt in prompts[:3]:
        try:
            from services.llm_rpm import acquire_rpm
            from services.llm_tpm import acquire_tpm

            acquire_rpm("copilot")
            acquire_tpm("copilot", estimate_tpm_tokens(prompt_chars=len(prompt or "") + 280, max_output=350))
            text = ""
            try:
                resp = openai_client.responses.create(
                    model=model,
                    input=f"{system}\n\n{prompt}",
                )
                text = (getattr(resp, "output_text", None) or "").strip()
                usage = getattr(resp, "usage", None)
                if usage and usage_callback:
                    usage_callback(
                        provider="azure",
                        model=model,
                        input_tokens=int(
                            getattr(usage, "input_tokens", 0)
                            or getattr(usage, "prompt_tokens", 0)
                            or 0
                        ),
                        output_tokens=int(
                            getattr(usage, "output_tokens", 0)
                            or getattr(usage, "completion_tokens", 0)
                            or 0
                        ),
                    )
            except Exception:
                resp = openai_client.chat.completions.create(
                    model=model,
                    temperature=0.2,
                    max_tokens=350,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                )
                text = (
                    (resp.choices[0].message.content or "") if resp.choices else ""
                ).strip()
                if hasattr(resp, "usage") and resp.usage and usage_callback:
                    usage_callback(
                        provider="azure",
                        model=model,
                        input_tokens=int(getattr(resp.usage, "prompt_tokens", 0) or 0),
                        output_tokens=int(
                            getattr(resp.usage, "completion_tokens", 0) or 0
                        ),
                    )
        except Exception as exc:
            logger.exception("azure/copilot citation probe failed")
            details.append(
                {"prompt": prompt, "error": str(exc)[:160], "engine": "bing"}
            )
            continue
        ok = _mentioned(text, needles)
        if ok:
            hits += 1
        details.append(
            {
                "prompt": prompt,
                "mentioned": ok,
                "excerpt": text[:280],
                "engine": "bing",
            }
        )
    return hits, details


def _probe_copilot(
    prompts: list[str],
    needles: set[str],
    usage_callback: Any | None = None,
) -> dict[str, Any]:
    """Microsoft Copilot-like probe via Azure AI Foundry / Azure OpenAI.

    Auth options:
    1) API key (`AZURE_AI_API_KEY`) + project/resource endpoint
    2) Entra ID via AIProjectClient (service principal / DefaultAzureCredential)

    Prefer an Agent with Grounding with Bing Search (`AZURE_AI_AGENT_NAME`) when
    using Entra ID.
    """
    endpoint = _azure_project_endpoint()
    model = _azure_ai_model()
    agent_name = _azure_ai_agent_name() or None
    api_key = _azure_ai_api_key()
    if not endpoint:
        return {
            "available": False,
            "reason": (
                "AZURE_AI_PROJECT_ENDPOINT / FOUNDRY_PROJECT_ENDPOINT assente "
                "(endpoint progetto Foundry, non solo resource)."
            ),
            "details": [],
        }

    hits = 0
    details: list[dict[str, Any]] = []

    # Path A: API key against OpenAI-compatible Foundry / Azure OpenAI endpoint.
    if api_key:
        try:
            from openai import OpenAI
        except Exception as exc:  # pragma: no cover
            return {"available": False, "reason": str(exc), "details": []}
        try:
            client = OpenAI(
                base_url=_azure_openai_base_url(endpoint),
                api_key=api_key,
                timeout=45.0,
                default_headers={"api-key": api_key},
            )
            hits, details = _copilot_run_prompts(
                client,
                model=model,
                prompts=prompts,
                needles=needles,
                usage_callback=usage_callback,
            )
        except Exception as exc:
            logger.exception("azure api-key copilot probe failed")
            return {"available": False, "reason": str(exc)[:160], "details": details}
    else:
        # Path B: Entra ID + AIProjectClient
        try:
            from azure.ai.projects import AIProjectClient
        except Exception as exc:  # pragma: no cover
            return {
                "available": False,
                "reason": f"azure-ai-projects non installato: {exc}",
                "details": [],
            }
        try:
            credential = _azure_credential()
        except Exception as exc:
            return {
                "available": False,
                "reason": f"Azure credential error: {exc}"[:160],
                "details": [],
            }
        try:
            with AIProjectClient(
                endpoint=endpoint,
                credential=credential,
                allow_preview=bool(agent_name),
            ) as project_client:
                with project_client.get_openai_client(
                    agent_name=agent_name
                ) as openai_client:
                    hits, details = _copilot_run_prompts(
                        openai_client,
                        model=model,
                        prompts=prompts,
                        needles=needles,
                        usage_callback=usage_callback,
                    )
        except Exception as exc:
            logger.exception("azure AIProjectClient init/probe failed")
            return {
                "available": False,
                "reason": str(exc)[:160],
                "details": details,
            }

    ok_details = [d for d in details if "error" not in d]
    if not ok_details:
        reason = "Copilot (Azure AI) probe fallito su tutti i prompt"
        if details and details[0].get("error"):
            reason = str(details[0]["error"])[:160]
        return {"available": False, "reason": reason, "details": details}
    total = max(1, len(ok_details))
    rate = round(100.0 * hits / total)
    return {
        "available": True,
        "mention_rate": rate,
        "hits": hits,
        "samples": total,
        "details": details,
        "evidence": "measured",
        "model": agent_name or model,
    }


def _competitor_pressure(competitors: list[dict[str, Any]]) -> float:
    if not competitors:
        return 0.0
    scores = []
    for c in competitors:
        try:
            scores.append(
                float(c.get("aio_score") or 0) * 0.5 + float(c.get("geo_score") or 0) * 0.5
            )
        except (TypeError, ValueError):
            continue
    if not scores:
        return 0.0
    return min(25.0, sum(scores) / len(scores) * 0.2)


def _sov_engine_parallelism() -> int:
    try:
        n = int(os.getenv("SOV_ENGINE_PARALLEL", "2") or "2")
    except (TypeError, ValueError):
        n = 2
    return max(1, min(6, n))


def _sov_monitor_timeout_seconds() -> int:
    """Hard wall-clock for the whole multi-engine probe (keeps analyze moving)."""
    try:
        n = int(os.getenv("SOV_MONITOR_TIMEOUT_SECONDS", "90") or "90")
    except (TypeError, ValueError):
        n = 90
    return max(30, min(300, n))


def _sov_prompt_limit() -> int:
    """Full pack size (default 8). Fast mode uses SOV_FAST_PROMPTS when set."""
    try:
        full = int(os.getenv("ANALYSIS_SOV_PROMPTS", "8") or "8")
    except (TypeError, ValueError):
        full = 8
    mode = (os.getenv("SOV_PROMPT_MODE", "full") or "full").strip().lower()
    if mode in {"fast", "quick", "lite"}:
        try:
            fast = int(os.getenv("SOV_FAST_PROMPTS", "3") or "3")
        except (TypeError, ValueError):
            fast = 3
        return max(1, min(full, fast))
    return max(1, min(8, full))


def sov_prompt_limit() -> int:
    """Public alias for estimate/billing alignment with measured probes."""
    return _sov_prompt_limit()


def run_citation_monitor(
    *,
    brand: str,
    domain: str,
    prompts: list[str] | None = None,
    competitors: list[dict[str, Any]] | None = None,
    usage_callback: Any | None = None,
    heartbeat_callback: Any | None = None,
) -> dict[str, Any]:
    limit = _sov_prompt_limit()
    prompts = list(prompts or default_prompts(locale="it"))[:limit]
    needles = _needles(brand, domain)
    findings: list[dict[str, str]] = []
    engines_out: list[dict[str, Any]] = []
    all_details: list[dict[str, Any]] = []
    usage_lock = threading.Lock()
    credit_stop: dict[str, Any] = {"exc": None}

    def _beat() -> None:
        if not callable(heartbeat_callback):
            return
        try:
            # Prefer phase=sov so job status / overlay leave the Score step.
            heartbeat_callback(phase="sov")
        except TypeError:
            heartbeat_callback()
        except Exception:
            raise

    def _usage(**kwargs: Any) -> None:
        if not callable(usage_callback):
            return
        from services.usage_billing import InsufficientCreditError, JobLeaseLostError
        from services.sov_budget import SovDailyBudgetExceeded

        with usage_lock:
            if credit_stop["exc"] is not None:
                raise credit_stop["exc"]
            token = _SOV_USAGE_ACTIVE.set(True)
            try:
                usage_callback(**kwargs)
            except (
                InsufficientCreditError,
                JobLeaseLostError,
                SovDailyBudgetExceeded,
            ) as exc:
                credit_stop["exc"] = exc
                raise
            except Exception as exc:
                # Stop after debit/lease failures raised as RuntimeError from the job cb.
                msg = str(exc).lower()
                if "lease lost" in msg or "debit failed" in msg or "stop billing" in msg:
                    credit_stop["exc"] = exc
                    raise
                # Session/app-context noise from worker threads must not kill the suite.
                logger.exception("SoV usage_callback failed")
            finally:
                _SOV_USAGE_ACTIVE.reset(token)

    # Probe engines in parallel (wall-clock ~ max(engine) not sum).
    # Background pulse keeps the job lease alive during long sequential
    # per-prompt OpenAI/Anthropic loops (can exceed STALE_HEARTBEAT alone).
    stop_pulse = threading.Event()

    def _pulse_loop() -> None:
        while not stop_pulse.wait(25.0):
            try:
                _beat()
            except Exception:
                stop_pulse.set()
                return

    pulse_thread: threading.Thread | None = None
    if callable(heartbeat_callback):
        pulse_thread = threading.Thread(
            target=_pulse_loop, name="sov-lease-pulse", daemon=True
        )
        pulse_thread.start()

    jobs: list[tuple[str, Any]] = [
        ("openai", lambda: _probe_openai(prompts, needles, usage_callback=_usage)),
        ("perplexity", lambda: _probe_perplexity(prompts, needles, usage_callback=_usage)),
        ("anthropic", lambda: _probe_anthropic(prompts, needles, usage_callback=_usage)),
        ("gemini", lambda: _probe_gemini(prompts, needles, usage_callback=_usage)),
        ("xai", lambda: _probe_xai(prompts, needles, usage_callback=_usage)),
        ("copilot", lambda: _probe_copilot(prompts, needles, usage_callback=_usage)),
    ]
    results: dict[str, dict[str, Any]] = {}
    workers = _sov_engine_parallelism()
    pool: ThreadPoolExecutor | None = None
    try:
        wall = _sov_monitor_timeout_seconds()
        deadline = time.monotonic() + wall
        pool = ThreadPoolExecutor(max_workers=workers)
        futures = {pool.submit(fn): name for name, fn in jobs}
        pending = set(futures)
        while pending:
            if time.monotonic() >= deadline:
                logger.warning(
                    "SoV monitor wall timeout after %ss — continuing with partial engines",
                    wall,
                )
                for fut in pending:
                    fut.cancel()
                    name = futures[fut]
                    results.setdefault(
                        name,
                        {
                            "available": False,
                            "reason": f"timeout after {wall}s",
                        },
                    )
                break
            remaining = max(0.1, deadline - time.monotonic())
            try:
                done = next(as_completed(pending, timeout=min(5.0, remaining)))
            except TimeoutError:
                try:
                    _beat()
                except Exception:
                    for fut in pending:
                        fut.cancel()
                    raise
                continue
            pending.discard(done)
            name = futures[done]
            try:
                results[name] = done.result() or {}
            except Exception as exc:
                from services.usage_billing import InsufficientCreditError
                from services.sov_budget import SovDailyBudgetExceeded

                if isinstance(
                    exc,
                    (InsufficientCreditError, SovDailyBudgetExceeded),
                ) or credit_stop["exc"] is not None:
                    for fut in pending:
                        fut.cancel()
                    raise (credit_stop["exc"] or exc)
                logger.exception("SoV engine %s failed", name)
                results[name] = {"available": False, "reason": str(exc)[:160]}
            if credit_stop["exc"] is not None:
                for fut in pending:
                    fut.cancel()
                raise credit_stop["exc"]
            try:
                _beat()
            except Exception:
                # Cancel remaining work on lease loss.
                for fut in pending:
                    fut.cancel()
                raise
    finally:
        stop_pulse.set()
        if pulse_thread is not None:
            pulse_thread.join(timeout=1.0)
        if pool is not None:
            # Do not block analyze on a hung engine after wall timeout.
            try:
                pool.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                pool.shutdown(wait=False)

    openai = results.get("openai") or {}
    if openai.get("available"):
        engines_out.append(
            {
                "id": "openai",
                "label": "ChatGPT",
                "vendor": "OpenAI",
                "mention_rate": openai["mention_rate"],
                "hits": openai["hits"],
                "samples": openai["samples"],
                "evidence": "measured",
                "accent": "#10A37F",
            }
        )
        all_details.extend(openai.get("details") or [])
    else:
        engines_out.append(
            {
                "id": "openai",
                "label": "ChatGPT",
                "vendor": "OpenAI",
                "mention_rate": None,
                "evidence": "unavailable",
                "reason": openai.get("reason"),
                "accent": "#10A37F",
            }
        )

    pplx = results.get("perplexity") or {}
    if pplx.get("available"):
        engines_out.append(
            {
                "id": "perplexity",
                "label": "Perplexity",
                "vendor": "Perplexity",
                "mention_rate": pplx["mention_rate"],
                "hits": pplx["hits"],
                "samples": pplx["samples"],
                "evidence": "measured",
                "accent": "#20B8CD",
                "model": pplx.get("model") or _perplexity_model(),
            }
        )
        all_details.extend(pplx.get("details") or [])
    else:
        engines_out.append(
            {
                "id": "perplexity",
                "label": "Perplexity",
                "vendor": "Perplexity",
                "mention_rate": None,
                "evidence": "unavailable",
                "reason": pplx.get("reason"),
                "accent": "#20B8CD",
            }
        )

    anthropic = results.get("anthropic") or {}
    if anthropic.get("available"):
        engines_out.append(
            {
                "id": "anthropic",
                "label": "Claude",
                "vendor": "Anthropic",
                "mention_rate": anthropic["mention_rate"],
                "hits": anthropic["hits"],
                "samples": anthropic["samples"],
                "evidence": "measured",
                "accent": "#D4A27F",
                "model": anthropic.get("model"),
            }
        )
        all_details.extend(anthropic.get("details") or [])
    else:
        engines_out.append(
            {
                "id": "anthropic",
                "label": "Claude",
                "vendor": "Anthropic",
                "mention_rate": None,
                "evidence": "unavailable",
                "reason": anthropic.get("reason"),
                "accent": "#D4A27F",
            }
        )

    gemini = results.get("gemini") or {}
    if gemini.get("available"):
        engines_out.append(
            {
                "id": "google",
                "label": "Gemini",
                "vendor": "Google (proxy AI Overview)",
                "mention_rate": gemini["mention_rate"],
                "hits": gemini["hits"],
                "samples": gemini["samples"],
                "evidence": "measured",
                "accent": "#4285F4",
                "model": gemini.get("model") or _gemini_model(),
            }
        )
        all_details.extend(gemini.get("details") or [])
    else:
        engines_out.append(
            {
                "id": "google",
                "label": "Gemini",
                "vendor": "Google (proxy AI Overview)",
                "mention_rate": None,
                "evidence": "unavailable" if _gemini_key() else "pending",
                "reason": gemini.get("reason")
                or (
                    "Probe via Gemini API (non è Google AI Overview nativo). "
                    "Imposta GEMINI_API_KEY."
                ),
                "accent": "#4285F4",
            }
        )

    xai = results.get("xai") or {}
    if xai.get("available"):
        engines_out.append(
            {
                "id": "xai",
                "label": "Grok",
                "vendor": "xAI",
                "mention_rate": xai["mention_rate"],
                "hits": xai["hits"],
                "samples": xai["samples"],
                "evidence": "measured",
                "accent": "#E8E8E8",
                "model": xai.get("model") or _xai_model(),
            }
        )
        all_details.extend(xai.get("details") or [])
    else:
        engines_out.append(
            {
                "id": "xai",
                "label": "Grok",
                "vendor": "xAI",
                "mention_rate": None,
                "evidence": "unavailable" if _xai_key() else "pending",
                "reason": xai.get("reason")
                or "Imposta XAI_API_KEY (console.x.ai) per SoV measured.",
                "accent": "#E8E8E8",
            }
        )

    copilot = results.get("copilot") or {}
    if copilot.get("available"):
        engines_out.append(
            {
                "id": "bing",
                "label": "Azure AI",
                "vendor": "Microsoft Azure",
                "mention_rate": copilot["mention_rate"],
                "hits": copilot["hits"],
                "samples": copilot["samples"],
                "evidence": "measured",
                "accent": "#7B83EB",
                "model": copilot.get("model") or _azure_ai_model(),
            }
        )
        all_details.extend(copilot.get("details") or [])
    else:
        engines_out.append(
            {
                "id": "bing",
                "label": "Azure AI",
                "vendor": "Microsoft Azure",
                "accent": "#7B83EB",
                "mention_rate": None,
                "evidence": "unavailable" if _azure_project_endpoint() else "pending",
                "reason": copilot.get("reason")
                or (
                    "Probe via Azure AI Foundry (proxy Copilot). "
                    "Imposta AZURE_AI_PROJECT_ENDPOINT + AZURE_AI_API_KEY "
                    "(oppure Entra ID: AZURE_TENANT_ID / CLIENT_ID / CLIENT_SECRET)."
                ),
            }
        )

    measured_rates = [
        float(e["mention_rate"])
        for e in engines_out
        if e.get("evidence") == "measured" and e.get("mention_rate") is not None
    ]
    brand_rate = round(sum(measured_rates) / len(measured_rates)) if measured_rates else None
    pressure = _competitor_pressure(competitors or [])

    competitor_benchmark = []
    for c in (competitors or [])[:3]:
        competitor_benchmark.append(
            {
                "domain": c.get("domain") or c.get("url"),
                "aio_score": c.get("aio_score"),
                "geo_score": c.get("geo_score"),
                "rating": c.get("rating"),
                "note": (
                    "Score snapshot; SoV measured condiviso richiede stessi prompt "
                    "sul rivale (Plus)."
                ),
            }
        )

    if measured_rates:
        findings.append(
            {
                "category": "geo",
                "severity": "ok",
                "title": "Citation monitor attivo",
                "detail": (
                    f"Probe measured su {len(measured_rates)} engine · "
                    f"brand mention rate medio {brand_rate}% · "
                    f"{len(prompts)} prompt · parallel={workers}."
                ),
                "evidence": "measured",
            }
        )
        if brand_rate is not None and brand_rate < 20:
            findings.append(
                {
                    "category": "geo",
                    "severity": "warn",
                    "title": "SoV measured basso",
                    "detail": (
                        "Poche menzioni brand nei prompt probe. Rafforza entity, "
                        "llms.txt e contenuti citabili; amplia il prompt bank."
                    ),
                    "evidence": "measured",
                }
            )
    else:
        findings.append(
            {
                "category": "geo",
                "severity": "warn",
                "title": "Citation monitor non configurato",
                "detail": (
                    "Imposta OPENAI_API_KEY, PERPLEXITY_API_KEY, ANTHROPIC_API_KEY, "
                    "GEMINI_API_KEY, XAI_API_KEY e/o AZURE_AI_PROJECT_ENDPOINT "
                    "per SoV measured."
                ),
                "evidence": "estimated",
            }
        )

    available = bool(measured_rates)
    return {
        "evidence": "measured" if available else "proxy",
        "available": available,
        "label": "Misurato (multi-engine probe)" if available else "Non disponibile",
        "engines": engines_out,
        "brand_mention_rate": brand_rate,
        "details": all_details[:40],
        "prompts_used": prompts,
        "competitor_benchmark": competitor_benchmark,
        "competitor_pressure": round(pressure, 1),
        "findings": findings,
        "parallel_engines": workers,
        "note": (
            "ChatGPT / Perplexity / Claude / Gemini (proxy AI Overview) / Grok / "
            "Azure AI (proxy Copilot): mention rate da prompt pack. "
            "Non equivale a ranking garantito nelle risposte live."
        ),
    }



def run_measured_sov(
    *, brand: str, domain: str, engines: list[str] | None = None
) -> dict[str, Any]:
    return run_citation_monitor(
        brand=brand, domain=domain, prompts=None, competitors=None
    )
