"""Optional S3 (or S3-compatible) store for analysis optimization packs.

When ``ANALYZE_ARTIFACT_STORE=s3`` and ``ANALYZE_S3_BUCKET`` is set,
``persist_analysis`` uploads the pack JSON and sets ``pack_uri``. With
``ANALYZE_ARTIFACT_DB_LEAN=1`` (default under s3 store) bulky artifact TEXT
columns are cleared after a successful upload so Postgres stays lean;
callers hydrate via ``ensure_pack_loaded``.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PACK_FILE_KEYS = (
    "llms.txt",
    "organization.jsonld.html",
    "faq.jsonld.html",
    "meta-pack.html",
    "robots.txt",
    "fix-this-week.md",
    "before-after.md",
)

_ATTR_BY_FILE = {
    "llms.txt": "llms_txt",
    "organization.jsonld.html": "json_ld_artifact",
    "faq.jsonld.html": "faq_artifact",
    "meta-pack.html": "meta_pack_artifact",
    "robots.txt": "robots_artifact",
    "fix-this-week.md": "checklist_artifact",
    "before-after.md": "before_after_artifact",
}


def artifact_store_backend() -> str:
    raw = (os.getenv("ANALYZE_ARTIFACT_STORE") or "db").strip().lower()
    if raw in {"s3", "minio", "object"}:
        return "s3"
    return "db"


def db_lean_enabled() -> bool:
    raw = (os.getenv("ANALYZE_ARTIFACT_DB_LEAN") or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    # Default lean when S3 store is active.
    return artifact_store_backend() == "s3"


def preview_chars() -> int:
    try:
        return max(0, int(os.getenv("ANALYZE_ARTIFACT_PREVIEW_CHARS", "2048") or "2048"))
    except (TypeError, ValueError):
        return 2048


def s3_bucket() -> str:
    return (os.getenv("ANALYZE_S3_BUCKET") or "").strip()


def s3_prefix() -> str:
    raw = (os.getenv("ANALYZE_S3_PREFIX") or "analyze-packs").strip().strip("/")
    return raw or "analyze-packs"


def s3_region() -> str:
    return (
        (os.getenv("ANALYZE_S3_REGION") or "").strip()
        or (os.getenv("AWS_DEFAULT_REGION") or "").strip()
        or (os.getenv("AWS_REGION") or "").strip()
        or "eu-central-1"
    )


def _client():
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - env without boto3
        raise RuntimeError("boto3 is required for ANALYZE_ARTIFACT_STORE=s3") from exc
    kwargs: dict[str, Any] = {"region_name": s3_region()}
    endpoint = (os.getenv("ANALYZE_S3_ENDPOINT_URL") or "").strip()
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client("s3", **kwargs)


def pack_object_key(*, user_id: int, site_id: int, run_id: int) -> str:
    return f"{s3_prefix()}/u{int(user_id)}/s{int(site_id)}/r{int(run_id)}/pack.json"


def pack_uri_for_key(bucket: str, key: str) -> str:
    return f"s3://{bucket}/{key}"


def parse_pack_uri(uri: str) -> tuple[str, str] | None:
    raw = (uri or "").strip()
    if not raw.startswith("s3://"):
        return None
    rest = raw[5:]
    if "/" not in rest:
        return None
    bucket, key = rest.split("/", 1)
    if not bucket or not key:
        return None
    return bucket, key


def pack_dict_from_mapping(pack: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in PACK_FILE_KEYS:
        val = pack.get(name) or ""
        out[name] = val if isinstance(val, str) else str(val)
    return out


def upload_pack(
    pack: dict[str, str],
    *,
    user_id: int,
    site_id: int,
    run_id: int,
) -> str | None:
    """Upload pack JSON; return ``s3://…`` URI or None on skip/failure."""
    if artifact_store_backend() != "s3":
        return None
    bucket = s3_bucket()
    if not bucket:
        logger.warning("ANALYZE_ARTIFACT_STORE=s3 but ANALYZE_S3_BUCKET unset")
        return None
    key = pack_object_key(user_id=user_id, site_id=site_id, run_id=run_id)
    body = json.dumps(pack_dict_from_mapping(pack), ensure_ascii=False).encode("utf-8")
    try:
        client = _client()
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType="application/json; charset=utf-8",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "S3 pack upload failed user=%s site=%s run=%s: %s",
            user_id,
            site_id,
            run_id,
            exc,
        )
        return None
    return pack_uri_for_key(bucket, key)


def download_pack(uri: str) -> dict[str, str] | None:
    parsed = parse_pack_uri(uri)
    if parsed is None:
        return None
    bucket, key = parsed
    try:
        client = _client()
        resp = client.get_object(Bucket=bucket, Key=key)
        raw = resp["Body"].read()
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("S3 pack download failed uri=%s err=%s", uri[:120], exc)
        return None
    if not isinstance(data, dict):
        return None
    return pack_dict_from_mapping({str(k): str(v or "") for k, v in data.items()})


def apply_pack_attrs(entity: Any, pack: dict[str, str]) -> None:
    for file_key, attr in _ATTR_BY_FILE.items():
        if hasattr(entity, attr):
            setattr(entity, attr, pack.get(file_key) or "")


def clear_bulky_pack_attrs(entity: Any, *, llms_preview: str = "") -> None:
    """Clear artifact TEXT columns after a successful S3 upload (DB lean)."""
    for attr in _ATTR_BY_FILE.values():
        if hasattr(entity, attr):
            setattr(entity, attr, "")
    if hasattr(entity, "llms_txt"):
        limit = preview_chars()
        entity.llms_txt = (llms_preview or "")[:limit] if limit else ""


def entity_needs_hydrate(entity: Any) -> bool:
    uri = getattr(entity, "pack_uri", None) or ""
    if not uri:
        return False
    # If any full artifact is already present, skip.
    for attr in (
        "json_ld_artifact",
        "faq_artifact",
        "meta_pack_artifact",
        "robots_artifact",
        "checklist_artifact",
        "before_after_artifact",
    ):
        if (getattr(entity, attr, None) or "").strip():
            return False
    return True


def ensure_pack_loaded(entity: Any) -> Any:
    """Hydrate pack artifact attributes from ``pack_uri`` when DB lean."""
    if not entity_needs_hydrate(entity):
        return entity
    uri = getattr(entity, "pack_uri", None) or ""
    pack = download_pack(uri)
    if not pack:
        return entity
    apply_pack_attrs(entity, pack)
    return entity
