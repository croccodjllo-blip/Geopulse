"""Multi-engine citation / measured SoV monitor.

OpenAI / Perplexity / Anthropic (Claude) / Google AI (Gemini) / xAI (Grok) /
Microsoft Copilot (Azure AI Foundry project) = measured when credentials are set.

Keys are read at call-time (not only at import) so load_dotenv / systemd env stay in sync.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from services.prompt_bank import default_prompts

logger = logging.getLogger(__name__)


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

    client = OpenAI(api_key=api_key, timeout=45.0)
    hits = 0
    details: list[dict[str, Any]] = []
    for prompt in prompts:
        try:
            resp = client.chat.completions.create(
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
                    {"role": "user", "content": prompt},
                ],
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
            logger.exception("openai citation probe failed")
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
    for prompt in prompts[:3]:
        try:
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
                            "content": f"{system}\n\n{prompt}",
                        }
                    ],
                },
                timeout=45,
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
            logger.exception("perplexity citation probe failed")
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


def run_citation_monitor(
    *,
    brand: str,
    domain: str,
    prompts: list[str] | None = None,
    competitors: list[dict[str, Any]] | None = None,
    usage_callback: Any | None = None,
    heartbeat_callback: Any | None = None,
) -> dict[str, Any]:
    prompts = list(prompts or default_prompts(locale="it"))[:8]
    needles = _needles(brand, domain)
    findings: list[dict[str, str]] = []
    engines_out: list[dict[str, Any]] = []
    all_details: list[dict[str, Any]] = []

    def _beat() -> None:
        if not callable(heartbeat_callback):
            return
        try:
            heartbeat_callback()
        except Exception:
            # Propagate lease-loss / cancel so the worker can stop cleanly.
            raise

    openai = _probe_openai(prompts, needles, usage_callback=usage_callback)
    _beat()
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

    pplx = _probe_perplexity(prompts, needles, usage_callback=usage_callback)
    _beat()
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

    anthropic = _probe_anthropic(prompts, needles, usage_callback=usage_callback)
    _beat()
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
                "model": anthropic.get("model") or _anthropic_model(),
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

    gemini = _probe_gemini(prompts, needles, usage_callback=usage_callback)
    _beat()
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

    xai = _probe_xai(prompts, needles, usage_callback=usage_callback)
    _beat()
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

    copilot = _probe_copilot(prompts, needles, usage_callback=usage_callback)
    _beat()
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
                    f"{len(prompts)} prompt."
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
