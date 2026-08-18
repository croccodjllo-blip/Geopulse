#!/usr/bin/env python3
"""Concurrent GEO/AIO analyze capacity stress harness.

Measures how many parallel domain audits Centropic can *admit* and how
plan/global gates surface as HTTP 429 / ConcurrentAnalysisError — without
necessarily burning LLM tokens.

Usage (VPS or local with prod-like env)::

    # Caps + live queue (safe, read-only)
    python scripts/stress_analyze_concurrency.py report

    # Per-user concurrent cap (service layer; cancels jobs after)
    python scripts/stress_analyze_concurrency.py per-user --plan admin

    # Multi-tenant admission ramp (STOP analyze workers first — no LLM)
    sudo systemctl stop aio-bot-analyze 'aio-bot-analyze@2'
    python scripts/stress_analyze_concurrency.py admission \\
        --users 40 --per-user 5 --ramp 8,16,32,64,100,150,200
    sudo systemctl start aio-bot-analyze 'aio-bot-analyze@2'

    # Concurrent HTTP against dashboard confirm (workers should be stopped)
    python scripts/stress_analyze_concurrency.py http-ramp --n 12 --user-id 1

Safety defaults:
  - Jobs use source=stress and URL host stress.invalid (SSRF-safe / fail-fast
    if a worker ever claims one).
  - Always cancel leftover stress jobs + release holds on exit.
  - ``admission`` / ``http-ramp`` refuse unless workers look idle OR
    ``--i-know-workers-are-stopped`` is set.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

STRESS_SOURCE = "stress"
STRESS_HOST = "stress.invalid"
STRESS_URL_PREFIX = f"https://{STRESS_HOST}/cap"


@dataclass
class AttemptResult:
    ok: bool
    kind: str
    ms: float
    detail: str = ""
    job_id: int | None = None


@dataclass
class RampSummary:
    target: int
    accepted: int
    rejected: int
    errors: int
    elapsed_ms: float
    redis_depth: int | None = None
    db_pending: int | None = None
    db_running: int | None = None
    reject_kinds: dict[str, int] = field(default_factory=dict)


def _load_app():
    os.environ.setdefault("FLASK_DEBUG", "0")
    try:
        from dotenv import load_dotenv

        env_path = os.path.join(ROOT, ".env")
        if os.path.isfile(env_path):
            load_dotenv(env_path)
    except Exception:
        pass
    from app import app

    return app


def _caps_snapshot() -> dict[str, Any]:
    from services.jobs import MAX_RUNNING_ANALYZE_JOBS
    from services.usage_billing import concurrent_analyze_cap_for as _cap_fn

    class _U:
        def __init__(self, plan: str, admin: bool = False):
            self.plan = plan
            self.role = "admin" if admin else "user"
            self.is_admin = admin

    free = int(os.getenv("MAX_CONCURRENT_ANALYZE_FREE", "1"))
    plus = int(os.getenv("MAX_CONCURRENT_ANALYZE_PLUS", "3"))
    business = int(os.getenv("MAX_CONCURRENT_ANALYZE_BUSINESS", "5"))
    admin = int(os.getenv("MAX_CONCURRENT_ANALYZE_ADMIN", "8"))
    fallback = int(os.getenv("MAX_CONCURRENT_ANALYZE_JOBS", "2"))

    return {
        "MAX_RUNNING_ANALYZE_JOBS": MAX_RUNNING_ANALYZE_JOBS,
        "ANALYZE_WORKER_CONCURRENCY": os.getenv("ANALYZE_WORKER_CONCURRENCY"),
        "MAX_CONCURRENT_ANALYZE_FREE": free,
        "MAX_CONCURRENT_ANALYZE_PLUS": plus,
        "MAX_CONCURRENT_ANALYZE_BUSINESS": business,
        "MAX_CONCURRENT_ANALYZE_ADMIN": admin,
        "MAX_CONCURRENT_ANALYZE_JOBS": fallback,
        "resolved_caps": {
            "free": _cap_fn(_U("free"), free=free, plus=plus, business=business, admin=admin, fallback=fallback),
            "plus": _cap_fn(_U("plus"), free=free, plus=plus, business=business, admin=admin, fallback=fallback),
            "business": _cap_fn(
                _U("business"), free=free, plus=plus, business=business, admin=admin, fallback=fallback
            ),
            "admin": _cap_fn(
                _U("admin", admin=True),
                free=free,
                plus=plus,
                business=business,
                admin=admin,
                fallback=fallback,
            ),
        },
        "http_rate_limits": {
            "dashboard_user_per_hour": 20,
            "dashboard_ip_per_hour": 40,
            "api_analyze_user_per_hour": 30,
        },
        "theoretical": {
            "single_tenant_max_inflight": {
                "free": free,
                "plus": plus,
                "business": business,
                "admin": admin,
            },
            "platform_claim_cap": MAX_RUNNING_ANALYZE_JOBS,
            "note": (
                "Per-tenant HTTP/API hits ConcurrentAnalysisError → 429 too_many_jobs "
                "at plan cap (pending+running). Global claim blocks at "
                "MAX_RUNNING_ANALYZE_JOBS. Dashboard also rate-limits 20/user/h "
                "(API 30/user/h) → 429 rate_limited."
            ),
        },
    }


def _queue_snapshot(app) -> dict[str, Any]:
    from app import AnalysisJob, db

    out: dict[str, Any] = {}
    with app.app_context():
        out["db_pending"] = AnalysisJob.query.filter_by(status="pending").count()
        out["db_running"] = AnalysisJob.query.filter_by(status="running").count()
        out["db_stress_active"] = (
            AnalysisJob.query.filter(
                AnalysisJob.status.in_(("pending", "running")),
                AnalysisJob.source == STRESS_SOURCE,
            ).count()
            if hasattr(AnalysisJob, "source")
            else None
        )
    try:
        from services.analyze_queue import queue_backend, queue_depth, queue_depth_by_priority

        out["queue_backend"] = queue_backend()
        out["redis_depth"] = queue_depth()
        out["redis_by_priority"] = queue_depth_by_priority()
    except Exception as exc:
        out["queue_error"] = str(exc)
    return out


def _workers_appear_idle(app) -> bool:
    snap = _queue_snapshot(app)
    return int(snap.get("db_running") or 0) == 0


def _stress_url(tag: str, i: int) -> str:
    return f"{STRESS_URL_PREFIX}/{tag}/{i}-{uuid.uuid4().hex[:10]}"


def _ensure_stress_users(app, *, n: int, plan: str) -> list[int]:
    """Create or reuse disposable stress users. Returns user ids."""
    from app import User, db
    from services.usage_billing import is_unlimited_user
    from sqlalchemy import text

    ids: list[int] = []
    with app.app_context():
        # Prod may have NOT NULL welcome_credit_granted without a DEFAULT;
        # ORM inserts omit unmapped/defaulted columns and would violate NN.
        try:
            db.session.execute(
                text(
                    "ALTER TABLE users "
                    "ALTER COLUMN welcome_credit_granted SET DEFAULT false"
                )
            )
            db.session.commit()
        except Exception:
            db.session.rollback()
        for i in range(n):
            email = f"stress-cap-{plan}-{i:04d}@stress.invalid"
            user = User.query.filter_by(email=email).first()
            if user is None:
                user = User(
                    email=email,
                    name=f"Stress {plan} {i}",
                    plan="admin" if plan == "admin" else plan,
                    role="admin" if plan == "admin" else "user",
                    credit_balance_cents=10_000_000,
                    credit_held_cents=0,
                )
                user.set_password(uuid.uuid4().hex + "Aa1!")
                if hasattr(user, "welcome_credit_granted"):
                    user.welcome_credit_granted = True
                if hasattr(user, "email_verified_at"):
                    user.email_verified_at = datetime.now(timezone.utc)
                db.session.add(user)
                db.session.flush()
                try:
                    db.session.execute(
                        text(
                            "UPDATE users SET welcome_credit_granted = true "
                            "WHERE id = :id"
                        ),
                        {"id": int(user.id)},
                    )
                except Exception:
                    pass
                db.session.commit()
            else:
                user.plan = "admin" if plan == "admin" else plan
                user.role = "admin" if plan == "admin" else (user.role or "user")
                if hasattr(user, "welcome_credit_granted"):
                    user.welcome_credit_granted = True
                user.credit_balance_cents = max(
                    int(user.credit_balance_cents or 0), 10_000_000
                )
                db.session.commit()
            ids.append(int(user.id))
            _ = is_unlimited_user  # imported for clarity / future
    return ids


def _cancel_stress_jobs(app) -> int:
    """Mark all stress pending/running jobs as error and release holds."""
    from app import AnalysisJob, User, db
    from services.usage_billing import release_job_hold

    cancelled = 0
    with app.app_context():
        q = AnalysisJob.query.filter(
            AnalysisJob.status.in_(("pending", "running")),
        )
        if hasattr(AnalysisJob, "source"):
            q = q.filter(AnalysisJob.source == STRESS_SOURCE)
        else:
            q = q.filter(AnalysisJob.url.like(f"{STRESS_URL_PREFIX}%"))
        jobs = q.all()
        for job in jobs:
            job.status = "error"
            job.error = "stress harness cleanup"
            job.finished_at = datetime.now(timezone.utc)
            job.lease_token = None
            owner = db.session.get(User, job.user_id)
            if owner is not None:
                try:
                    release_job_hold(db.session, owner, job)
                except Exception:
                    pass
            cancelled += 1
        db.session.commit()
        # Drain redis of stress job ids (best-effort: flush stress-only unknown;
        # safer to LPOP until empty when only stress ran under paused workers).
        try:
            from services.analyze_queue import queue_backend, try_pop_analyze_job

            if queue_backend() == "redis":
                # Pop up to cancelled*2 ids left in queue after cancel.
                for _ in range(max(cancelled * 2, 50)):
                    if try_pop_analyze_job() is None:
                        break
        except Exception:
            pass
    return cancelled


def _admit_one(
    app,
    *,
    user_id: int,
    url: str,
    required_cents: int = 10,
) -> AttemptResult:
    """Mirror production admit path: assert → hold → enqueue."""
    from app import AnalysisJob, User, concurrent_analyze_cap_for, db
    from services.jobs import DuplicateAnalyzeJobError, enqueue_analysis
    from services.usage_billing import (
        ConcurrentAnalysisError,
        InsufficientCreditError,
        assert_can_start_analysis,
        hold_credit,
    )
    from app import CreditLedger

    t0 = time.perf_counter()
    with app.app_context():
        user = db.session.get(User, user_id)
        if user is None:
            return AttemptResult(False, "no_user", (time.perf_counter() - t0) * 1000)
        cap = concurrent_analyze_cap_for(user)
        try:
            assert_can_start_analysis(
                db.session,
                user,
                AnalysisJob=AnalysisJob,
                required_cents=required_cents,
                max_concurrent_jobs=cap,
            )
            held = hold_credit(
                db.session,
                CreditLedger,
                user,
                amount_cents=required_cents,
                description="stress admit",
            )
            job = enqueue_analysis(
                db.session,
                AnalysisJob,
                user_id=user.id,
                url=url,
                max_pages=1,
                run_measured=False,
                held_cents=int(held or 0),
                source=STRESS_SOURCE,
                plan=getattr(user, "plan", None),
                is_admin=bool(getattr(user, "is_admin", False)),
            )
            ms = (time.perf_counter() - t0) * 1000
            return AttemptResult(True, "accepted", ms, job_id=int(job.id))
        except ConcurrentAnalysisError as exc:
            db.session.rollback()
            return AttemptResult(
                False, "too_many_jobs", (time.perf_counter() - t0) * 1000, str(exc)
            )
        except InsufficientCreditError as exc:
            db.session.rollback()
            return AttemptResult(
                False, "insufficient_credit", (time.perf_counter() - t0) * 1000, str(exc)
            )
        except DuplicateAnalyzeJobError as exc:
            db.session.rollback()
            return AttemptResult(
                False, "duplicate", (time.perf_counter() - t0) * 1000, str(exc)
            )
        except Exception as exc:
            db.session.rollback()
            return AttemptResult(
                False, "error", (time.perf_counter() - t0) * 1000, repr(exc)
            )


def cmd_report(args: argparse.Namespace) -> int:
    app = _load_app()
    caps = _caps_snapshot()
    snap = _queue_snapshot(app)
    payload = {"caps": caps, "live": snap}
    print(json.dumps(payload, indent=2, default=str))
    return 0


def cmd_per_user(args: argparse.Namespace) -> int:
    app = _load_app()
    if not args.i_know_workers_are_stopped and not _workers_appear_idle(app):
        print(
            "REFUSE: db_running > 0. Stop analyze workers or pass "
            "--i-know-workers-are-stopped",
            file=sys.stderr,
        )
        return 2
    plan = args.plan
    user_ids = _ensure_stress_users(app, n=1, plan=plan)
    uid = user_ids[0]
    from app import concurrent_analyze_cap_for, db, User

    with app.app_context():
        user = db.session.get(User, uid)
        cap = concurrent_analyze_cap_for(user)
    # Try cap+2 admits in parallel to surface the gate.
    target = cap + 2
    tag = f"peruser-{plan}-{int(time.time())}"
    results: list[AttemptResult] = []
    with ThreadPoolExecutor(max_workers=min(target, 16)) as pool:
        futs = [
            pool.submit(
                _admit_one, app, user_id=uid, url=_stress_url(tag, i)
            )
            for i in range(target)
        ]
        for fut in as_completed(futs):
            results.append(fut.result())
    accepted = sum(1 for r in results if r.ok)
    rejected = [r for r in results if not r.ok]
    kinds: dict[str, int] = {}
    for r in rejected:
        kinds[r.kind] = kinds.get(r.kind, 0) + 1
    cancelled = _cancel_stress_jobs(app)
    out = {
        "plan": plan,
        "cap": cap,
        "attempted": target,
        "accepted": accepted,
        "rejected": len(rejected),
        "reject_kinds": kinds,
        "cancelled": cancelled,
        "pass": accepted == cap and kinds.get("too_many_jobs", 0) >= 1,
    }
    print(json.dumps(out, indent=2))
    return 0 if out["pass"] else 1


def _parse_ramp(raw: str) -> list[int]:
    vals = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        vals.append(int(part))
    return sorted(set(v for v in vals if v > 0))


def cmd_admission(args: argparse.Namespace) -> int:
    app = _load_app()
    if not args.i_know_workers_are_stopped and not _workers_appear_idle(app):
        print(
            "REFUSE: db_running > 0. Stop analyze workers first:\n"
            "  systemctl stop aio-bot-analyze 'aio-bot-analyze@2'\n"
            "or pass --i-know-workers-are-stopped",
            file=sys.stderr,
        )
        return 2

    plan = args.plan
    users_n = max(1, int(args.users))
    per_user = max(1, int(args.per_user))
    ramp = _parse_ramp(args.ramp) or [8, 16, 32, 64]
    user_ids = _ensure_stress_users(app, n=users_n, plan=plan)

    from app import concurrent_analyze_cap_for, db, User

    with app.app_context():
        sample = db.session.get(User, user_ids[0])
        plan_cap = concurrent_analyze_cap_for(sample)
    if per_user > plan_cap:
        print(
            f"WARN: --per-user {per_user} > plan cap {plan_cap}; "
            f"clamping to {plan_cap}",
            file=sys.stderr,
        )
        per_user = plan_cap

    max_capacity = users_n * per_user
    summaries: list[RampSummary] = []
    tag_base = f"adm-{int(time.time())}"

    for target in ramp:
        if target > max_capacity:
            print(
                f"SKIP ramp={target}: need more users "
                f"(max={max_capacity} = {users_n}×{per_user})",
                file=sys.stderr,
            )
            continue
        # Fresh slate between steps.
        _cancel_stress_jobs(app)
        time.sleep(0.2)

        # Round-robin assign targets across users (≤ per_user each).
        assignments: list[tuple[int, str]] = []
        per_counts = {uid: 0 for uid in user_ids}
        i = 0
        while len(assignments) < target:
            uid = user_ids[i % len(user_ids)]
            if per_counts[uid] < per_user:
                assignments.append((uid, _stress_url(f"{tag_base}-{target}", len(assignments))))
                per_counts[uid] += 1
            i += 1
            if i > target * len(user_ids) + 10:
                break

        t0 = time.perf_counter()
        results: list[AttemptResult] = []
        workers = min(32, max(4, target))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [
                pool.submit(_admit_one, app, user_id=uid, url=url)
                for uid, url in assignments
            ]
            for fut in as_completed(futs):
                results.append(fut.result())
        elapsed = (time.perf_counter() - t0) * 1000
        snap = _queue_snapshot(app)
        kinds: dict[str, int] = {}
        for r in results:
            if not r.ok:
                kinds[r.kind] = kinds.get(r.kind, 0) + 1
        summary = RampSummary(
            target=target,
            accepted=sum(1 for r in results if r.ok),
            rejected=sum(1 for r in results if not r.ok),
            errors=kinds.get("error", 0),
            elapsed_ms=round(elapsed, 1),
            redis_depth=snap.get("redis_depth"),
            db_pending=snap.get("db_pending"),
            db_running=snap.get("db_running"),
            reject_kinds=kinds,
        )
        summaries.append(summary)
        print(json.dumps({"ramp_step": asdict(summary)}, default=str), flush=True)

    cancelled = _cancel_stress_jobs(app)
    caps = _caps_snapshot()
    # Largest fully accepted step.
    max_ok = 0
    for s in summaries:
        if s.accepted == s.target and s.errors == 0:
            max_ok = max(max_ok, s.target)
    out = {
        "mode": "admission",
        "plan": plan,
        "users": users_n,
        "per_user": per_user,
        "plan_cap": plan_cap,
        "max_fully_accepted": max_ok,
        "steps": [asdict(s) for s in summaries],
        "cancelled": cancelled,
        "caps": caps,
    }
    print(json.dumps(out, indent=2, default=str))
    return 0


def cmd_http_ramp(args: argparse.Namespace) -> int:
    """Concurrent dashboard analyze/confirmed via Flask test_client."""
    app = _load_app()
    if not args.i_know_workers_are_stopped and not _workers_appear_idle(app):
        print(
            "REFUSE: db_running > 0. Stop workers or pass "
            "--i-know-workers-are-stopped",
            file=sys.stderr,
        )
        return 2

    from app import User, concurrent_analyze_cap_for, db, ensure_schema

    n = max(1, int(args.n))
    with app.app_context():
        ensure_schema()
        if args.user_id:
            user = db.session.get(User, int(args.user_id))
        else:
            ids = _ensure_stress_users(app, n=1, plan=args.plan)
            user = db.session.get(User, ids[0])
        if user is None:
            print("ERROR: user not found", file=sys.stderr)
            return 2
        uid = int(user.id)
        cap = concurrent_analyze_cap_for(user)
        sv = int(getattr(user, "session_version", 0) or 0)

    tag = f"http-{int(time.time())}"
    results: list[dict[str, Any]] = []

    def _one(i: int) -> dict[str, Any]:
        url = _stress_url(tag, i)
        t0 = time.perf_counter()
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = uid
            sess["session_version"] = sv
        # CSRF: many forms need token; confirmed JSON may use header — probe both.
        resp = client.post(
            "/dashboard/analyze/confirmed",
            json={"url": url, "run_measured": False},
            headers={"Content-Type": "application/json"},
        )
        # Fallback form-encoded if JSON route rejects.
        if resp.status_code in (400, 404, 405):
            resp = client.post(
                "/dashboard/analyze/confirmed",
                data={"url": url, "confirm": "1"},
                follow_redirects=False,
            )
        body = ""
        try:
            body = resp.get_data(as_text=True)[:400]
        except Exception:
            pass
        err = ""
        try:
            payload = resp.get_json(silent=True) or {}
            err = str(payload.get("error") or "")
        except Exception:
            pass
        return {
            "i": i,
            "status": resp.status_code,
            "error": err,
            "ms": round((time.perf_counter() - t0) * 1000, 1),
            "body_snip": body[:160],
        }

    with ThreadPoolExecutor(max_workers=min(n, 16)) as pool:
        futs = [pool.submit(_one, i) for i in range(n)]
        for fut in as_completed(futs):
            results.append(fut.result())

    cancelled = _cancel_stress_jobs(app)
    by_status: dict[str, int] = {}
    by_error: dict[str, int] = {}
    for r in results:
        by_status[str(r["status"])] = by_status.get(str(r["status"]), 0) + 1
        if r.get("error"):
            by_error[r["error"]] = by_error.get(r["error"], 0) + 1
    out = {
        "mode": "http-ramp",
        "user_id": uid,
        "cap": cap,
        "n": n,
        "by_status": by_status,
        "by_error": by_error,
        "results": sorted(results, key=lambda x: x["i"]),
        "cancelled": cancelled,
    }
    print(json.dumps(out, indent=2, default=str))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_report = sub.add_parser("report", help="Print caps + live queue")
    p_report.set_defaults(func=cmd_report)

    p_pu = sub.add_parser("per-user", help="Verify plan concurrent cap")
    p_pu.add_argument("--plan", default="admin", choices=["free", "plus", "business", "admin"])
    p_pu.add_argument("--i-know-workers-are-stopped", action="store_true")
    p_pu.set_defaults(func=cmd_per_user)

    p_ad = sub.add_parser("admission", help="Multi-tenant admission ramp")
    p_ad.add_argument("--plan", default="business", choices=["free", "plus", "business", "admin"])
    p_ad.add_argument("--users", type=int, default=40)
    p_ad.add_argument("--per-user", type=int, default=5)
    p_ad.add_argument("--ramp", default="8,16,32,64,100,150,200")
    p_ad.add_argument("--i-know-workers-are-stopped", action="store_true")
    p_ad.set_defaults(func=cmd_admission)

    p_http = sub.add_parser("http-ramp", help="Concurrent HTTP analyze admit")
    p_http.add_argument("--n", type=int, default=12)
    p_http.add_argument("--user-id", type=int, default=0)
    p_http.add_argument("--plan", default="admin")
    p_http.add_argument("--i-know-workers-are-stopped", action="store_true")
    p_http.set_defaults(func=cmd_http_ramp)

    args = parser.parse_args()
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
