"""FinOps: optional B2/S3 lifecycle cleanup for old analyze packs.

Deletes objects under ``ANALYZE_S3_PREFIX`` older than ``ANALYZE_S3_RETENTION_DAYS``
(default 90). Safe no-op when artifact store is not s3.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


def retention_days() -> int:
    try:
        return max(1, int(os.getenv("ANALYZE_S3_RETENTION_DAYS", "90") or "90"))
    except (TypeError, ValueError):
        return 90


def cleanup_expired_packs(*, limit: int = 500) -> dict[str, Any]:
    from services.artifact_s3 import artifact_store_backend, s3_bucket, s3_prefix, _client

    if artifact_store_backend() != "s3":
        return {"ok": True, "skipped": True, "reason": "store_not_s3"}
    bucket = s3_bucket()
    if not bucket:
        return {"ok": False, "error": "no_bucket"}
    prefix = s3_prefix().rstrip("/") + "/"
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days())
    client = _client()
    deleted = 0
    scanned = 0
    token: str | None = None
    while scanned < limit:
        kwargs: dict[str, Any] = {
            "Bucket": bucket,
            "Prefix": prefix,
            "MaxKeys": min(100, limit - scanned),
        }
        if token:
            kwargs["ContinuationToken"] = token
        resp = client.list_objects_v2(**kwargs)
        contents = resp.get("Contents") or []
        if not contents:
            break
        to_delete = []
        for obj in contents:
            scanned += 1
            last_mod = obj.get("LastModified")
            if last_mod is None:
                continue
            if last_mod.tzinfo is None:
                last_mod = last_mod.replace(tzinfo=timezone.utc)
            if last_mod < cutoff:
                to_delete.append({"Key": obj["Key"]})
        if to_delete:
            client.delete_objects(
                Bucket=bucket, Delete={"Objects": to_delete, "Quiet": True}
            )
            deleted += len(to_delete)
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
        if not token:
            break
    logger.info(
        "S3 pack lifecycle scanned=%s deleted=%s retention_days=%s",
        scanned,
        deleted,
        retention_days(),
    )
    return {
        "ok": True,
        "scanned": scanned,
        "deleted": deleted,
        "retention_days": retention_days(),
        "cutoff": cutoff.isoformat(),
    }
