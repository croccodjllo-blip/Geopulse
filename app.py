"""
Centropic (centropic.ai) — SaaS per ottimizzazione GEO/AIO dei siti web.
Analisi score + findings + generazione pack artifact (llms.txt, JSON-LD, meta, robots).
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import math
import os
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

# Carica .env PRIMA di qualsiasi import services che legge os.getenv a livello modulo.
load_dotenv()

from flask import (
    Flask,
    Response,
    abort,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from flask_babel import Babel, gettext as _
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect, FlaskForm
from flask_wtf.csrf import generate_csrf
from sqlalchemy import UniqueConstraint, func, inspect, text
from sqlalchemy.exc import IntegrityError
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import (
    BooleanField,
    HiddenField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TelField,
    TextAreaField,
    URLField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    Optional,
    ValidationError,
)

from services.analysis_store import (
    DEFAULT_RESCAN_HOUR,
    RESCAN_INTERVALS,
    clamp_hour,
    next_rescan_after,
)
from services.analyze_pipeline import run_analysis_pipeline
from services.analyze_eta import compute_analyze_eta
from services.analyzer import (
    ABS_MAX_CRAWL_PAGES,
    critical_crawl_pages,
    normalize_url,
)
from services.billing import (
    construct_event as stripe_construct_event,
    create_checkout_session,
    create_portal_session,
    payments_enabled,
    payments_provider,
    plan_from_subscription_status,
    stripe_enabled,
)
from services.paddle_billing import (
    client_config as paddle_client_config,
    create_plus_checkout as paddle_create_plus_checkout,
    create_topup_checkout as paddle_create_topup_checkout,
    extract_user_id as paddle_extract_user_id,
    paddle_enabled,
    paddle_overlay_ready,
    paddle_topup_price_id,
    paddle_topups_enabled,
    parse_webhook_event as paddle_parse_webhook_event,
    plan_from_paddle_subscription_status,
    topup_cents_for_transaction,
    transaction_grants_plus,
    transaction_gross_cents,
    transaction_is_subscription,
    verify_webhook_signature as paddle_verify_webhook_signature,
)
from services.usage_billing import (
    check_page_word_budget,
    estimate_analysis_cost,
    estimate_improvement,
    has_sufficient_credit,
    has_sufficient_credit_for_job,
    required_credit_with_grace_cents,
    GRACE_MARGIN,
    get_balance_cents,
    deduct_credit,
    debit_leased_job_usage,
    topup_credit,
    hold_credit,
    release_hold,
    consume_hold,
    release_job_hold,
    InsufficientCreditError,
    ConcurrentAnalysisError,
    record_actual_usage,
    is_unlimited_user,
    debit_cents_from_usage,
    assert_can_start_analysis,
)
from services.export import multi_site_zip, pack_zip_bytes, runs_to_csv
from services.guides import GUIDES
from services.jobs import (
    claim_next_job,
    complete_job,
    enqueue_analysis,
    fail_job,
    heartbeat_job,
)
from services.analyze_errors import classify_analyze_error, format_job_error
from services.entitlements import entitlements_for, require_capability
from services.security import (
    PASSWORD_MAX_LEN,
    PASSWORD_MIN_LEN,
    password_policy_error,
    safe_next_url,
    safe_same_origin_url,
)
from services.i18n import (
    DEFAULT_LOCALE,
    LANG_COOKIE,
    LANG_COOKIE_MAX_AGE,
    SUPPORTED_LOCALES,
    active_ui_locale,
    language_switcher_items,
    locale_meta,
    normalize_locale,
    select_locale,
)
from services.mailer import (
    build_email_verify_email,
    build_pack_email,
    build_password_reset_email,
    mail_configured,
    send_email,
    send_email_with_attachment,
)
from services.rate_limit import limiter
from services.rating import RATING_ORDER, compute_rating
from services.engine_breakdown import apply_measured_sov, compute_engine_breakdown
from services.signals import compare_with_previous
from services.sov_measured import should_run_measured
from services.prompt_bank import dump_prompt_bank, parse_prompt_bank, resolve_prompts
from services.api_auth import find_user_by_api_key, generate_api_key
from services.agency import (
    build_whitelabel_html,
    build_whitelabel_markdown,
    dump_agency_brand,
    parse_agency_brand,
)
from services.gsc import gsc_status
from services.js_crawl import js_crawl_available
from services.publish_verify import verify_published_pack
from services.citation_monitor import citation_monitor_available
from services.sov_graph import list_sov_snapshots, sov_series_for_chart
from services.edge_telemetry import record_edge_hit, top_crawlers_for_site
from services.vertical_packs import (
    apply_vertical_to_prompt_bank,
    list_verticals,
    vertical_checklist,
)
from services.edge_signals import (
    CACHE_CONTROL as EDGE_CACHE_CONTROL,
    build_live_robots_txt,
    build_signals_payload,
    cloudflare_worker_snippet,
    content_etag,
    edge_base_url,
    extract_jsonld_body,
    html_embed_snippet,
    is_ai_crawler,
    new_public_token,
    vercel_edge_config_snippet,
)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Piano Free: 1 sito + 2 analisi lifetime (nessun reset giornaliero).
FREE_TOTAL_ANALYSES = max(1, int(os.getenv("FREE_TOTAL_ANALYSES", "2")))
MAX_SITES_FREE = max(1, int(os.getenv("MAX_SITES_FREE", "1")))
PRO_DAILY_ANALYSES = max(FREE_TOTAL_ANALYSES, int(os.getenv("PRO_DAILY_ANALYSES", "200")))
MAX_SITES_PRO = max(MAX_SITES_FREE, int(os.getenv("MAX_SITES_PRO", "50")))
FREE_CRAWL_PAGES = max(1, min(20, int(os.getenv("FREE_CRAWL_PAGES", "8"))))
# Piano Plus: 0 = crawl intero sito (tetto operativo ABS_MAX_CRAWL_PAGES).
_PRO_CRAWL_RAW = int(os.getenv("PRO_CRAWL_PAGES", "0"))
PRO_CRAWL_UNLIMITED = _PRO_CRAWL_RAW <= 0
PRO_CRAWL_PAGES = (
    ABS_MAX_CRAWL_PAGES
    if PRO_CRAWL_UNLIMITED
    else max(FREE_CRAWL_PAGES, min(ABS_MAX_CRAWL_PAGES, _PRO_CRAWL_RAW))
)
FREE_HISTORY_LIMIT = max(5, int(os.getenv("FREE_HISTORY_LIMIT", "10")))
PRO_HISTORY_LIMIT = max(FREE_HISTORY_LIMIT, int(os.getenv("PRO_HISTORY_LIMIT", "100")))
PACK_EMAIL_DAILY_LIMIT = max(1, int(os.getenv("PACK_EMAIL_DAILY_LIMIT", "10")))
ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL") or "admin@centropic.ai").strip().lower()
# Nessun default in chiaro: se manca, l’admin non viene (ri)creato automaticamente.
ADMIN_PASSWORD = (os.getenv("ADMIN_PASSWORD") or "").strip()
ADMIN_NAME = os.getenv("ADMIN_NAME") or "Admin Centropic"
ADMIN_BOOTSTRAP = os.getenv("ADMIN_BOOTSTRAP", "0") == "1"
ASYNC_ANALYZE = os.getenv("ASYNC_ANALYZE", "1") == "1"
MEASURED_SOV_ON_ANALYZE = os.getenv("MEASURED_SOV_ON_ANALYZE", "1") == "1"
# Welcome credit granted only after email verification (anti-farming).
WELCOME_CREDIT_CENTS = max(0, int(os.getenv("WELCOME_CREDIT_CENTS", "200")))
EMAIL_VERIFY_HOURS = max(1, int(os.getenv("EMAIL_VERIFY_HOURS", "48")))
ANALYZE_BATCH_LIMIT = max(1, int(os.getenv("ANALYZE_BATCH_LIMIT", "5")))
PASSWORD_RESET_HOURS = max(1, int(os.getenv("PASSWORD_RESET_HOURS", "2")))
SITE_AUTHOR_NAME = (os.getenv("SITE_AUTHOR_NAME") or "Engineering Factory").strip()
SITE_AUTHOR_TITLE = (
    os.getenv("SITE_AUTHOR_TITLE") or "Proprietario · Responsabile contenuti e prodotto"
).strip()
SITE_AUTHOR_URL = (
    os.getenv("SITE_AUTHOR_URL") or "https://www.engineeringfactory.app/"
).strip().rstrip("/") + "/"
SITE_OWNER_NAME = (os.getenv("SITE_OWNER_NAME") or SITE_AUTHOR_NAME).strip()
SITE_OWNER_URL = (os.getenv("SITE_OWNER_URL") or SITE_AUTHOR_URL).strip()


def resolve_database_uri(raw: str | None) -> str:
    """Usa sempre un path assoluto per SQLite (evita instance/ di Flask)."""
    uri = (raw or "").strip() or ("sqlite:///" + os.path.join(BASE_DIR, "database.db"))
    if uri.startswith("sqlite:///") and not uri.startswith("sqlite:////"):
        rel = uri.removeprefix("sqlite:///")
        if rel != ":memory:" and not os.path.isabs(rel):
            uri = "sqlite:///" + os.path.join(BASE_DIR, rel)
    return uri


app = Flask(__name__)
_flask_secret = (os.getenv("FLASK_SECRET_KEY") or "").strip()
if not _flask_secret:
    if os.getenv("FLASK_DEBUG", "0") == "1":
        _flask_secret = secrets.token_hex(32)
    else:
        raise RuntimeError(
            "FLASK_SECRET_KEY obbligatoria in produzione (FLASK_DEBUG!=1)."
        )
app.config["SECRET_KEY"] = _flask_secret
app.config["SQLALCHEMY_DATABASE_URI"] = resolve_database_uri(os.getenv("DATABASE_URL"))
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# Secure cookies by default outside local debug.
_secure_default = "0" if os.getenv("FLASK_DEBUG", "0") == "1" else "1"
app.config["SESSION_COOKIE_SECURE"] = (
    os.getenv("SESSION_COOKIE_SECURE", _secure_default) == "1"
)
app.config["PREFERRED_URL_SCHEME"] = os.getenv(
    "PREFERRED_URL_SCHEME",
    "http" if os.getenv("FLASK_DEBUG", "0") == "1" else "https",
)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.config["WTF_CSRF_TIME_LIMIT"] = 3600
app.config["INSTANCE_RELATIVE_CONFIG"] = False
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024
app.config["BABEL_DEFAULT_LOCALE"] = "it"
app.config["BABEL_TRANSLATION_DIRECTORIES"] = os.path.join(BASE_DIR, "translations")

# Dietro Nginx: rispetta X-Forwarded-For / Proto / Prefix solo se TRUST_PROXY=1.
# Do NOT trust X-Forwarded-Host (x_host=0): forged Host enables
# password-reset and Stripe return URL phishing.
# Keep the app bound to 127.0.0.1 (see docker-compose) so clients cannot
# spoof XFF by hitting Gunicorn directly.
if os.getenv("TRUST_PROXY", "1").strip().lower() in {"1", "true", "yes", "on"}:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=0, x_prefix=1)

babel = Babel(app, locale_selector=select_locale)


@app.before_request
def _persist_lang_query() -> None:
    """Allow ?lang=xx on any page and remember it for the session."""
    forced = request.args.get("lang")
    if not forced:
        return
    loc = normalize_locale(forced)
    if loc in SUPPORTED_LOCALES:
        session["lang"] = loc

if os.getenv("FLASK_DEBUG", "0") != "1":
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

db = SQLAlchemy(app)
csrf = CSRFProtect(app)

from services.observability import configure_app_logging  # noqa: E402

configure_app_logging(app)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
PUBLIC_SITE_URL = (os.getenv("PUBLIC_SITE_URL") or "https://centropic.ai").rstrip("/")
GA4_MEASUREMENT_ID = (os.getenv("GA4_MEASUREMENT_ID") or "").strip()
GOOGLE_SITE_VERIFICATION = (os.getenv("GOOGLE_SITE_VERIFICATION") or "").strip()
ADSENSE_CLIENT_ID = (os.getenv("ADSENSE_CLIENT_ID") or "").strip()
ADS_TXT_CONTENT = (os.getenv("ADS_TXT_CONTENT") or "").strip()
# Google Ads conversions (optional). Example: AW-123456789
GOOGLE_ADS_ID = (os.getenv("GOOGLE_ADS_ID") or "").strip()
# Conversion labels only (suffix after /), e.g. AbCdEfGhIjKlMnOp
GOOGLE_ADS_SIGNUP_LABEL = (os.getenv("GOOGLE_ADS_SIGNUP_LABEL") or "").strip()
GOOGLE_ADS_ANALYZE_LABEL = (os.getenv("GOOGLE_ADS_ANALYZE_LABEL") or "").strip()
GOOGLE_ADS_TOPUP_LABEL = (os.getenv("GOOGLE_ADS_TOPUP_LABEL") or "").strip()
# CORS Edge: vuoto = nessun header ACAO (crawler non ne hanno bisogno).
# Imposta EDGE_CORS_ORIGIN=* o un origin esatto se serve embed browser.
EDGE_CORS_ORIGIN = (os.getenv("EDGE_CORS_ORIGIN") or "").strip()
EDGE_RATE_LIMIT = max(30, int(os.getenv("EDGE_RATE_LIMIT", "120")))
EDGE_RATE_WINDOW = max(60, int(os.getenv("EDGE_RATE_WINDOW", "60")))
MAX_CONCURRENT_ANALYZE_JOBS = max(1, int(os.getenv("MAX_CONCURRENT_ANALYZE_JOBS", "2")))
ALLOW_DROP_ANALYSIS_JOBS = os.getenv("ALLOW_DROP_ANALYSIS_JOBS", "0") == "1"


def _ads_send_to(label: str) -> str | None:
    if not GOOGLE_ADS_ID or not label:
        return None
    if "/" in label:
        return label  # already full AW-xxx/yyy
    return f"{GOOGLE_ADS_ID}/{label}"


def queue_analytics_event(name: str, params: dict[str, Any] | None = None) -> None:
    """Queue a GA4/Ads event for the next page render (session flash-style)."""
    if not name:
        return
    if not (GA4_MEASUREMENT_ID or GOOGLE_ADS_ID):
        return
    events = session.get("analytics_events") or []
    if not isinstance(events, list):
        events = []
    payload = dict(params or {})
    events.append({"name": name, "params": payload})
    # Cap to avoid session bloat
    session["analytics_events"] = events[-20:]


def pop_analytics_events() -> list[dict[str, Any]]:
    events = session.pop("analytics_events", None) or []
    return events if isinstance(events, list) else []



@app.after_request
def set_security_headers(response):
    # Header applicativi (nginx tiene HSTS; evitiamo duplicare X-* lì).
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["X-XSS-Protection"] = "0"
    script_src = ["'self'", "'unsafe-inline'"]
    img_src = ["'self'", "data:"]
    connect_src = ["'self'"]
    frame_src = ["'self'"]
    if paddle_enabled():
        script_src.append("https://cdn.paddle.com")
        connect_src.extend([
            "https://api.paddle.com",
            "https://sandbox-api.paddle.com",
            "https://checkout.paddle.com",
            "https://sandbox-checkout.paddle.com",
            "https://buy.paddle.com",
            "https://sandbox-buy.paddle.com",
        ])
        frame_src.extend([
            "https://checkout.paddle.com",
            "https://sandbox-checkout.paddle.com",
            "https://buy.paddle.com",
            "https://sandbox-buy.paddle.com",
            "https://cdn.paddle.com",
        ])
    if GA4_MEASUREMENT_ID or GOOGLE_ADS_ID:
        script_src.extend(["https://www.googletagmanager.com", "https://www.google-analytics.com"])
        connect_src.extend([
            "https://www.google-analytics.com",
            "https://region1.google-analytics.com",
            "https://www.google.com",
            "https://googleads.g.doubleclick.net",
        ])
        img_src.extend(["https://www.google-analytics.com", "https://www.google.com"])
    if ADSENSE_CLIENT_ID or GOOGLE_ADS_ID:
        script_src.extend([
            "https://pagead2.googlesyndication.com",
            "https://partner.googleadservices.com",
            "https://www.googleadservices.com",
        ])
        img_src.extend([
            "https://googleads.g.doubleclick.net",
            "https://pagead2.googlesyndication.com",
            "https://www.googleadservices.com",
        ])
        frame_src.extend([
            "https://googleads.g.doubleclick.net",
            "https://tpc.googlesyndication.com",
            "https://www.google.com",
        ])
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        f"script-src {' '.join(dict.fromkeys(script_src))}; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        f"img-src {' '.join(dict.fromkeys(img_src))}; "
        f"connect-src {' '.join(dict.fromkeys(connect_src))}; "
        f"frame-src {' '.join(dict.fromkeys(frame_src))}; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    # HSTS solo se secure; nginx può già inviarlo — ok se allineati
    if request.is_secure or app.config["SESSION_COOKIE_SECURE"]:
        response.headers["Strict-Transport-Security"] = (
            "max-age=15552000; includeSubDomains"
        )
    return response


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    company = db.Column(db.String(160))
    website_url = db.Column(db.String(500))
    phone = db.Column(db.String(40))
    role = db.Column(db.String(80))
    country = db.Column(db.String(80))
    plan = db.Column(db.String(40), nullable=False, default="free")  # free|plus|pro|admin
    password_hash = db.Column(db.String(255), nullable=False)
    stripe_customer_id = db.Column(db.String(120))
    stripe_subscription_id = db.Column(db.String(120))
    paddle_customer_id = db.Column(db.String(120))
    paddle_subscription_id = db.Column(db.String(120))
    reset_token_hash = db.Column(db.String(64))
    reset_token_expires = db.Column(db.DateTime)
    # GEO suite settings
    alert_email_enabled = db.Column(db.Boolean, nullable=False, default=True)
    webhook_url = db.Column(db.String(500))
    webhook_secret = db.Column(db.String(120))
    api_key_hash = db.Column(db.String(64))
    api_key_prefix = db.Column(db.String(16))
    prompt_bank_json = db.Column(db.Text, nullable=False, default="")
    agency_brand_json = db.Column(db.Text, nullable=False, default="")
    # Usage-based billing: prepaid credit balance in EUR cents (integer)
    credit_balance_cents = db.Column(db.Integer, nullable=False, default=0)
    credit_held_cents = db.Column(db.Integer, nullable=False, default=0)
    # Bumped on password change / reset to invalidate other browser sessions.
    session_version = db.Column(db.Integer, nullable=False, default=0)
    # Email verification (welcome credit gated on verify).
    email_verified_at = db.Column(db.DateTime)
    verify_token_hash = db.Column(db.String(64))
    verify_token_expires = db.Column(db.DateTime)
    welcome_credit_granted = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    sites = db.relationship("SiteAnalysis", back_populates="user", lazy="dynamic")
    jobs = db.relationship("AnalysisJob", back_populates="user", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)
        self.session_version = int(getattr(self, "session_version", 0) or 0) + 1

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def bump_session_version(self) -> None:
        """Invalidate all other sessions (keeps caller responsible for re-bind)."""
        self.session_version = int(getattr(self, "session_version", 0) or 0) + 1

    def clear_reset_token(self) -> None:
        self.reset_token_hash = None
        self.reset_token_expires = None

    def issue_reset_token(self, *, hours: int = PASSWORD_RESET_HOURS) -> str:
        raw = secrets.token_urlsafe(32)
        self.reset_token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        self.reset_token_expires = datetime.now(timezone.utc) + timedelta(hours=hours)
        return raw

    def matches_reset_token(self, raw_token: str) -> bool:
        if not raw_token or not self.reset_token_hash or not self.reset_token_expires:
            return False
        expires = self.reset_token_expires
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            return False
        digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        return secrets.compare_digest(digest, self.reset_token_hash)

    @property
    def email_verified(self) -> bool:
        return getattr(self, "email_verified_at", None) is not None

    def clear_verify_token(self) -> None:
        self.verify_token_hash = None
        self.verify_token_expires = None

    def issue_verify_token(self, *, hours: int = EMAIL_VERIFY_HOURS) -> str:
        raw = secrets.token_urlsafe(32)
        self.verify_token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        self.verify_token_expires = datetime.now(timezone.utc) + timedelta(hours=hours)
        return raw

    def matches_verify_token(self, raw_token: str) -> bool:
        if not raw_token or not self.verify_token_hash or not self.verify_token_expires:
            return False
        expires = self.verify_token_expires
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            return False
        digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        return secrets.compare_digest(digest, self.verify_token_hash)

    @property
    def is_admin(self) -> bool:
        return (self.plan or "").lower() == "admin" or (self.role or "") == "admin"

    @property
    def is_pro(self) -> bool:
        """Piano Plus (alias storici: pro) o Admin."""
        return self.is_admin or (self.plan or "").lower() in {"plus", "pro"}

    @property
    def plan_label(self) -> str:
        if self.is_admin:
            return "Admin"
        if self.is_pro:
            return "Plus"
        return "Free"

    @property
    def max_sites(self) -> int:
        return MAX_SITES_PRO if self.is_pro else MAX_SITES_FREE

    @property
    def daily_limit(self) -> int:
        """Plus: analisi / 24h. Free: tetto lifetime (nessun reset)."""
        return PRO_DAILY_ANALYSES if self.is_pro else FREE_TOTAL_ANALYSES

    @property
    def analysis_limit(self) -> int:
        return self.daily_limit

    @property
    def analysis_limit_lifetime(self) -> bool:
        return not self.is_pro

    @property
    def crawl_pages(self) -> int:
        return PRO_CRAWL_PAGES if self.is_pro else FREE_CRAWL_PAGES

    @property
    def crawl_unlimited(self) -> bool:
        return bool(self.is_pro and PRO_CRAWL_UNLIMITED)


class SiteAnalysis(db.Model):
    __tablename__ = "site_analyses"
    __table_args__ = (UniqueConstraint("user_id", "url", name="uq_user_url"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    url = db.Column(db.String(500), nullable=False)
    domain = db.Column(db.String(255), nullable=False)
    page_title = db.Column(db.String(500))
    aio_score = db.Column(db.Integer)
    geo_score = db.Column(db.Integer)
    findings_json = db.Column(db.Text, nullable=False, default="[]")
    analysis_notes = db.Column(db.Text)
    llms_txt = db.Column(db.Text, nullable=False, default="")
    json_ld_artifact = db.Column(db.Text, nullable=False, default="")
    faq_artifact = db.Column(db.Text, nullable=False, default="")
    meta_pack_artifact = db.Column(db.Text, nullable=False, default="")
    robots_artifact = db.Column(db.Text, nullable=False, default="")
    checklist_artifact = db.Column(db.Text, nullable=False, default="")
    before_after_artifact = db.Column(db.Text, nullable=False, default="")
    pages_analyzed = db.Column(db.Integer, nullable=False, default=1)
    crawl_pages_json = db.Column(db.Text, nullable=False, default="[]")
    rescan_interval = db.Column(db.String(20), nullable=False, default="off")
    rescan_hour = db.Column(db.Integer, nullable=False, default=DEFAULT_RESCAN_HOUR)
    next_rescan_at = db.Column(db.DateTime)
    last_rescan_at = db.Column(db.DateTime)
    last_rescan_error = db.Column(db.String(500))
    # Edge Signals hosting: token pubblico + flag + versione payload
    public_token = db.Column(db.String(48), unique=True, index=True)
    signals_hosted = db.Column(db.Boolean, nullable=False, default=False)
    signals_version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship("User", back_populates="sites")
    runs = db.relationship(
        "AnalysisRun",
        back_populates="site",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    @property
    def findings(self) -> list[dict[str, str]]:
        try:
            data = json.loads(self.findings_json or "[]")
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    @property
    def _crawl_blob(self) -> dict[str, Any] | list[Any]:
        try:
            return json.loads(self.crawl_pages_json or "[]")
        except json.JSONDecodeError:
            return []

    @property
    def crawl_pages(self) -> list[dict[str, Any]]:
        data = self._crawl_blob
        if isinstance(data, dict):
            pages = data.get("pages") or []
            return pages if isinstance(pages, list) else []
        return data if isinstance(data, list) else []

    @property
    def competitors(self) -> list[dict[str, Any]]:
        data = self._crawl_blob
        if isinstance(data, dict):
            comps = data.get("competitors") or []
            return comps if isinstance(comps, list) else []
        return []

    @property
    def robots_probed_text(self) -> str:
        """Testo /robots.txt osservato in probe (non il pack suggerito)."""
        data = self._crawl_blob
        if not isinstance(data, dict):
            return ""
        probes = data.get("probes") or {}
        if isinstance(probes, dict):
            robots = probes.get("robots") or {}
            if isinstance(robots, dict) and robots.get("snippet"):
                return str(robots.get("snippet") or "")
        return ""

    @property
    def signals(self) -> dict[str, Any]:
        data = self._crawl_blob
        if isinstance(data, dict):
            sig = data.get("signals") or {}
            return sig if isinstance(sig, dict) else {}
        return {}

    @property
    def rating(self) -> dict[str, Any]:
        return compute_rating(self.aio_score, self.geo_score, self.findings)

    @property
    def rescan_active(self) -> bool:
        return (self.rescan_interval or "off").lower() in {"daily", "weekly"}


class AnalysisJob(db.Model):
    """Coda analisi async (pending → running → done|error)."""

    __tablename__ = "analysis_jobs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    site_id = db.Column(db.Integer, db.ForeignKey("site_analyses.id"), index=True)
    url = db.Column(db.String(500), nullable=False)
    max_pages = db.Column(db.Integer, nullable=False, default=8)
    competitors_json = db.Column(db.Text, nullable=False, default="[]")
    # Persist measured SoV intent from confirm form through the async worker.
    run_measured = db.Column(db.Boolean, nullable=False, default=False)
    # Live progress for overlay ETA (updated during crawl / geo / pack).
    progress_done = db.Column(db.Integer, nullable=False, default=0)
    progress_total = db.Column(db.Integer, nullable=False, default=0)
    progress_phase = db.Column(db.String(20), nullable=False, default="")
    held_cents = db.Column(db.Integer, nullable=False, default=0)
    # Cumulative EUR cents already debited for this job (prevents soft-reclaim re-bill).
    billed_cents = db.Column(db.Integer, nullable=False, default=0)
    heartbeat_at = db.Column(db.DateTime)
    lease_token = db.Column(db.String(64))
    attempt_count = db.Column(db.Integer, nullable=False, default=0)
    analytics_complete_sent = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    error = db.Column(db.String(500))
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)

    user = db.relationship("User", back_populates="jobs")

    @property
    def competitors(self) -> list[str]:
        try:
            data = json.loads(self.competitors_json or "[]")
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []


class AnalysisRun(db.Model):
    """Storico append-only di ogni analisi (manuale o schedulata)."""

    __tablename__ = "analysis_runs"

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(
        db.Integer, db.ForeignKey("site_analyses.id"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    url = db.Column(db.String(500), nullable=False)
    domain = db.Column(db.String(255), nullable=False)
    page_title = db.Column(db.String(500))
    aio_score = db.Column(db.Integer)
    geo_score = db.Column(db.Integer)
    findings_json = db.Column(db.Text, nullable=False, default="[]")
    analysis_notes = db.Column(db.Text)
    llms_txt = db.Column(db.Text, nullable=False, default="")
    json_ld_artifact = db.Column(db.Text, nullable=False, default="")
    faq_artifact = db.Column(db.Text, nullable=False, default="")
    meta_pack_artifact = db.Column(db.Text, nullable=False, default="")
    robots_artifact = db.Column(db.Text, nullable=False, default="")
    checklist_artifact = db.Column(db.Text, nullable=False, default="")
    before_after_artifact = db.Column(db.Text, nullable=False, default="")
    pages_analyzed = db.Column(db.Integer, nullable=False, default=1)
    crawl_pages_json = db.Column(db.Text, nullable=False, default="[]")
    source = db.Column(db.String(20), nullable=False, default="manual")
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )

    site = db.relationship("SiteAnalysis", back_populates="runs")

    @property
    def findings(self) -> list[dict[str, str]]:
        try:
            data = json.loads(self.findings_json or "[]")
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    @property
    def _crawl_blob(self) -> dict[str, Any] | list[Any]:
        try:
            return json.loads(self.crawl_pages_json or "[]")
        except json.JSONDecodeError:
            return []

    @property
    def crawl_pages(self) -> list[dict[str, Any]]:
        data = self._crawl_blob
        if isinstance(data, dict):
            pages = data.get("pages") or []
            return pages if isinstance(pages, list) else []
        return data if isinstance(data, list) else []

    @property
    def competitors(self) -> list[dict[str, Any]]:
        data = self._crawl_blob
        if isinstance(data, dict):
            comps = data.get("competitors") or []
            return comps if isinstance(comps, list) else []
        return []

    @property
    def robots_probed_text(self) -> str:
        data = self._crawl_blob
        if not isinstance(data, dict):
            return ""
        probes = data.get("probes") or {}
        if isinstance(probes, dict):
            robots = probes.get("robots") or {}
            if isinstance(robots, dict) and robots.get("snippet"):
                return str(robots.get("snippet") or "")
        return ""

    @property
    def rating(self) -> dict[str, Any]:
        return compute_rating(self.aio_score, self.geo_score, self.findings)


class ProInterest(db.Model):
    """Waitlist interesse piano Pro (da Prenota l'interesse)."""

    __tablename__ = "pro_interests"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    company = db.Column(db.String(160))
    website_url = db.Column(db.String(500))
    note = db.Column(db.String(500))
    source = db.Column(db.String(80), nullable=False, default="pricing")
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class CreditLedger(db.Model):
    """Immutable ledger of every credit transaction (top-up or deduct)."""

    __tablename__ = "credit_ledger"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    analysis_run_id = db.Column(db.Integer, db.ForeignKey("analysis_runs.id"))
    # positive = top-up; negative = deduction
    amount_cents = db.Column(db.Integer, nullable=False)
    balance_after_cents = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(255), nullable=False, default="")
    stripe_payment_intent = db.Column(db.String(120))
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )


class UsageEvent(db.Model):
    """Token-level log of every AI API call for cost accounting."""

    __tablename__ = "usage_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    analysis_run_id = db.Column(db.Integer, db.ForeignKey("analysis_runs.id"), index=True)
    provider = db.Column(db.String(40), nullable=False)
    model = db.Column(db.String(80), nullable=False)
    input_tokens = db.Column(db.Integer, nullable=False, default=0)
    output_tokens = db.Column(db.Integer, nullable=False, default=0)
    # stored as integer µUSD (parts per million of a USD)
    raw_cost_usd_micro = db.Column(db.Integer, nullable=False, default=0)
    service_cost_eur_cents = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------


def validate_http_url(_form: FlaskForm, field: URLField) -> None:
    value = (field.data or "").strip()
    if not value:
        return
    parsed = urlparse(value if "://" in value else f"https://{value}")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError("Inserisci un URL http(s) valido.")


ROLE_CHOICES = [
    ("", "Seleziona il tuo ruolo"),
    ("founder", "Founder / Titolare"),
    ("marketing", "Marketing"),
    ("seo", "SEO / Content"),
    ("agency", "Agenzia / Consulente"),
    ("developer", "Developer"),
    ("other", "Altro"),
]


class RegisterForm(FlaskForm):
    name = StringField(
        "Nome e cognome",
        validators=[DataRequired(), Length(min=2, max=120)],
    )
    company = StringField(
        "Azienda / Brand",
        validators=[Optional(), Length(max=160)],
    )
    website_url = StringField(
        "Sito web principale",
        validators=[Optional(), Length(max=500), validate_http_url],
    )
    email = StringField(
        "Email lavorativa",
        validators=[
            DataRequired(),
            Email(message="Email non valida.", check_deliverability=False),
            Length(max=255),
        ],
    )
    phone = TelField(
        "Telefono",
        validators=[Optional(), Length(max=40)],
    )
    role = SelectField(
        "Ruolo",
        choices=ROLE_CHOICES,
        validators=[Optional()],
    )
    country = StringField(
        "Paese",
        validators=[Optional(), Length(max=80)],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=PASSWORD_MIN_LEN, max=PASSWORD_MAX_LEN)],
    )
    confirm = PasswordField(
        "Conferma password",
        validators=[
            DataRequired(),
            EqualTo("password", message="Le password non coincidono."),
        ],
    )
    accept_terms = BooleanField(
        "Accetto termini e privacy",
        validators=[DataRequired(message="Devi accettare termini e privacy.")],
    )
    submit = SubmitField("Crea account")

    def validate_password(self, field: PasswordField) -> None:
        err = password_policy_error(field.data)
        if err:
            raise ValidationError(err)

    def validate_email(self, field: StringField) -> None:
        # Intentionally no existence check here (anti-enumeration).
        # Duplicate emails are rejected at commit with a generic flash.
        return

    def validate_role(self, field: SelectField) -> None:
        raw = (field.data or "").strip()
        if not raw or raw == "":
            field.data = ""
            return
        allowed = {c[0] for c in ROLE_CHOICES if c[0]}
        if raw not in allowed:
            raise ValidationError("Seleziona un ruolo valido.")


class LoginForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[
            DataRequired(),
            Email(message="Email non valida.", check_deliverability=False),
            Length(max=255),
        ],
    )
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Resta connesso", default=False)
    submit = SubmitField("Accedi")


class ForgotPasswordForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[
            DataRequired(),
            Email(message="Email non valida.", check_deliverability=False),
            Length(max=255),
        ],
    )
    submit = SubmitField("Invia link di recupero")


class ResetPasswordForm(FlaskForm):
    password = PasswordField(
        "Nuova password",
        validators=[DataRequired(), Length(min=PASSWORD_MIN_LEN, max=PASSWORD_MAX_LEN)],
    )
    confirm = PasswordField(
        "Conferma password",
        validators=[
            DataRequired(),
            EqualTo("password", message="Le password non coincidono."),
        ],
    )
    submit = SubmitField("Salva nuova password")

    def validate_password(self, field: PasswordField) -> None:
        err = password_policy_error(field.data)
        if err:
            raise ValidationError(err)


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(
        "Password attuale",
        validators=[DataRequired()],
    )
    password = PasswordField(
        "Nuova password",
        validators=[DataRequired(), Length(min=PASSWORD_MIN_LEN, max=PASSWORD_MAX_LEN)],
    )
    confirm = PasswordField(
        "Conferma nuova password",
        validators=[
            DataRequired(),
            EqualTo("password", message="Le password non coincidono."),
        ],
    )
    submit = SubmitField("Aggiorna password")

    def validate_password(self, field: PasswordField) -> None:
        err = password_policy_error(field.data)
        if err:
            raise ValidationError(err)


class AnalyzeForm(FlaskForm):
    url = StringField(
        "URL del sito",
        validators=[DataRequired(), Length(max=500), validate_http_url],
    )
    competitors = TextAreaField(
        "Competitor (max 3 URL, uno per riga)",
        validators=[Optional(), Length(max=1500)],
    )
    submit = SubmitField("Analizza dominio")


class ProInterestForm(FlaskForm):
    name = StringField(
        "Nome e cognome",
        validators=[DataRequired(), Length(min=2, max=120)],
    )
    email = StringField(
        "Email",
        validators=[
            DataRequired(),
            Email(message="Email non valida.", check_deliverability=False),
            Length(max=255),
        ],
    )
    company = StringField(
        "Azienda / Brand",
        validators=[Optional(), Length(max=160)],
    )
    website_url = StringField(
        "Sito web",
        validators=[Optional(), Length(max=500), validate_http_url],
    )
    note = StringField(
        "Cosa ti serve da Plus",
        validators=[Optional(), Length(max=500)],
    )
    submit = SubmitField("Prenota l’interesse")


RESCAN_HOUR_CHOICES = [(str(h), f"{h:02d}:00 UTC") for h in range(24)]


class RescanScheduleForm(FlaskForm):
    analysis_id = HiddenField(validators=[DataRequired()])
    interval = SelectField(
        "Frequenza re-scan",
        choices=[
            ("off", "Disattivato"),
            ("daily", "Ogni giorno"),
            ("weekly", "Ogni settimana"),
        ],
        validators=[DataRequired()],
    )
    hour = SelectField(
        "Orario (UTC)",
        choices=RESCAN_HOUR_CHOICES,
        default=str(DEFAULT_RESCAN_HOUR),
        validators=[DataRequired()],
    )
    submit = SubmitField("Salva")


class AlertSettingsForm(FlaskForm):
    alert_email_enabled = BooleanField("Email alert su regressioni", default=True)
    webhook_url = StringField(
        "Webhook URL",
        validators=[Optional(), Length(max=500)],
    )
    webhook_secret = StringField(
        "Webhook secret (HMAC)",
        validators=[Optional(), Length(max=120)],
    )
    submit = SubmitField("Salva alert")


class PromptBankForm(FlaskForm):
    prompts = TextAreaField(
        "Prompt bank (un prompt per riga)",
        validators=[Optional(), Length(max=8000)],
    )
    submit = SubmitField("Salva prompt bank")


class VerticalPackForm(FlaskForm):
    vertical = SelectField(
        "Vertical pack",
        choices=[("", "— seleziona —")]
        + [(v["slug"], v["label"]) for v in list_verticals()],
        validators=[Optional()],
    )
    submit = SubmitField("Applica pack al prompt bank")


class AgencyBrandForm(FlaskForm):
    brand_name = StringField("Brand agenzia", validators=[Optional(), Length(max=80)])
    logo_url = StringField("Logo URL", validators=[Optional(), Length(max=300)])
    primary_color = StringField("Colore primario", validators=[Optional(), Length(max=20)])
    footer_note = StringField("Nota piè di pagina", validators=[Optional(), Length(max=200)])
    submit = SubmitField("Salva white-label")


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            flash("Accedi per continuare.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            flash("Accedi per continuare.", "warning")
            return redirect(url_for("login", next=request.path))
        if not user.is_admin:
            flash("Area riservata agli amministratori.", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)

    return wrapped


def pro_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            flash("Accedi per continuare.", "warning")
            return redirect(url_for("login", next=request.path))
        if not user.is_pro:
            flash(
                "Funzione Plus: attiva il piano Plus per re-scan, export e storico avanzato.",
                "warning",
            )
            return redirect(url_for("pricing"))
        return view(*args, **kwargs)

    return wrapped


def current_user() -> User | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = db.session.get(User, user_id)
    if user is None:
        session.clear()
        return None
    # Invalidate stale sessions after password reset/change.
    expected = int(getattr(user, "session_version", 0) or 0)
    got = session.get("session_version")
    if got is None or int(got) != expected:
        session.clear()
        return None
    return user


def _establish_session(user: User, *, permanent: bool = True) -> None:
    """Create a fresh authenticated session bound to the user's session_version."""
    session.clear()
    session["user_id"] = user.id
    session["session_version"] = int(getattr(user, "session_version", 0) or 0)
    session.permanent = permanent


def ensure_admin_user() -> User | None:
    """Crea l’admin solo se ADMIN_PASSWORD è impostata.

    - Nuovo utente: richiede ADMIN_PASSWORD.
    - Utente esistente: aggiorna metadati; reset password solo se
      ADMIN_BOOTSTRAP=1 (evita overwrite a ogni restart).
    """
    if not ADMIN_PASSWORD:
        app.logger.warning(
            "ADMIN_PASSWORD non impostata: skip ensure_admin_user "
            "(nessun default in chiaro)."
        )
        return User.query.filter_by(email=ADMIN_EMAIL).first()

    # Sentinel value for unlimited credit: max INT4 (~€21 M).
    # Admin users are never actually charged (see usage_billing.is_unlimited_user),
    # but we store a large value so the UI shows "credito illimitato".
    _ADMIN_CREDIT_SENTINEL = 2_147_483_647

    user = User.query.filter_by(email=ADMIN_EMAIL).first()
    if user is None:
        user = User(
            email=ADMIN_EMAIL,
            name=ADMIN_NAME,
            company="Centropic",
            website_url="https://centropic.ai/",
            role="admin",
            country="Italia",
            plan="admin",
            credit_balance_cents=_ADMIN_CREDIT_SENTINEL,
        )
        user.set_password(ADMIN_PASSWORD)
        db.session.add(user)
        app.logger.info("Admin creato: %s", ADMIN_EMAIL)
    else:
        user.name = ADMIN_NAME
        user.company = user.company or "Centropic"
        user.website_url = user.website_url or "https://centropic.ai/"
        user.role = "admin"
        user.plan = "admin"
        # Always keep admin credit at sentinel value so it never appears depleted.
        user.credit_balance_cents = _ADMIN_CREDIT_SENTINEL
        if ADMIN_BOOTSTRAP:
            user.set_password(ADMIN_PASSWORD)
            app.logger.warning(
                "ADMIN_BOOTSTRAP=1: password admin resettata per %s", ADMIN_EMAIL
            )
    db.session.commit()
    return user


def public_base_url() -> str:
    """Canonical public origin — never derived from the request Host header."""
    configured = (PUBLIC_SITE_URL or "").rstrip("/")
    if configured:
        return configured
    return "https://centropic.ai"


def absolute_url(endpoint: str, **values: Any) -> str:
    """Build an absolute URL under PUBLIC_SITE_URL (host-header safe)."""
    path = url_for(endpoint, **values)
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{public_base_url()}{path}"

@app.context_processor
def inject_globals() -> dict[str, Any]:
    base = public_base_url()
    path = request.path or "/"
    canonical = base if path == "/" else f"{base}{path}"
    ui_lang = active_ui_locale()
    meta = locale_meta(ui_lang)
    user = current_user()
    sidebar_balance = 0
    sidebar_credits_used = 0
    sidebar_credits_cap = 0
    sidebar_plan = "Free"
    sidebar_active = "dashboard"
    if user is not None:
        try:
            sidebar_balance = int(get_balance_cents(user) or 0)
        except Exception:
            sidebar_balance = int(getattr(user, "credit_balance_cents", 0) or 0)
        sidebar_plan = getattr(user, "plan_label", None) or str(
            getattr(user, "plan", "free")
        ).title()
        # Free: show lifetime analyses vs cap; Plus: EUR balance (no fake denominator).
        if not getattr(user, "is_pro", False):
            try:
                sidebar_credits_used = int(analyses_total(user.id))
            except Exception:
                sidebar_credits_used = 0
            sidebar_credits_cap = int(FREE_TOTAL_ANALYSES or 0)
        ep = (request.endpoint or "")
        if ep in {"dashboard_settings"}:
            sidebar_active = "settings"
        elif ep in {"dashboard_history", "site_history", "export_history_csv"}:
            sidebar_active = "history"
        elif ep in {"topup_credit_page"}:
            sidebar_active = "billing"
        elif ep in {"dashboard_verify", "dashboard_verify_rescan"}:
            sidebar_active = "geo"
        elif "history" in ep:
            sidebar_active = "history"
        else:
            sidebar_active = "dashboard"
    return {
        "current_user": user,
        "csrf_token": generate_csrf,
        "max_sites_free": MAX_SITES_FREE,
        "free_daily_analyses": FREE_TOTAL_ANALYSES,
        "free_total_analyses": FREE_TOTAL_ANALYSES,
        "free_crawl_pages": FREE_CRAWL_PAGES,
        "pro_crawl_pages": PRO_CRAWL_PAGES,
        "pro_crawl_unlimited": PRO_CRAWL_UNLIMITED,
        "abs_max_crawl_pages": ABS_MAX_CRAWL_PAGES,
        "mail_ready": mail_configured(),
        "now_year": datetime.now(timezone.utc).year,
        "rating_scale": RATING_ORDER,
        "canonical_base": base,
        "canonical_url": canonical,
        "admin_email": ADMIN_EMAIL,
        "stripe_ready": payments_enabled(),
        "paddle_ready": paddle_enabled(),
        "payments_ready": payments_enabled(),
        "payments_provider": payments_provider(),
        "paddle_overlay": paddle_overlay_ready(),
        "paddle_config": paddle_client_config(),
        "ga4_measurement_id": GA4_MEASUREMENT_ID,
        "google_site_verification": GOOGLE_SITE_VERIFICATION,
        "adsense_client_id": ADSENSE_CLIENT_ID,
        "google_ads_id": GOOGLE_ADS_ID,
        "analytics_events": pop_analytics_events(),
        "site_author_name": SITE_AUTHOR_NAME,
        "site_author_title": SITE_AUTHOR_TITLE,
        "site_author_url": SITE_AUTHOR_URL,
        "site_owner_name": SITE_OWNER_NAME,
        "site_owner_url": SITE_OWNER_URL,
        "async_analyze": ASYNC_ANALYZE,
        "ui_lang": ui_lang,
        "ui_locale_og": meta["og"],
        "ui_languages": language_switcher_items(ui_lang),
        "supported_locales": SUPPORTED_LOCALES,
        "_": _,
        "sidebar_balance_cents": sidebar_balance,
        "sidebar_credits_used": sidebar_credits_used,
        "sidebar_credits_cap": sidebar_credits_cap,
        "sidebar_plan": sidebar_plan,
        "sidebar_active": sidebar_active,
    }


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------



class SovSnapshot(db.Model):
    """Share-of-voice time series for measurement graph / agency reports."""

    __tablename__ = "sov_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(
        db.Integer, db.ForeignKey("site_analyses.id"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    run_id = db.Column(
        db.Integer, db.ForeignKey("analysis_runs.id"), nullable=True, index=True
    )
    brand_mention_rate = db.Column(db.Float, nullable=True)
    evidence = db.Column(db.String(40), nullable=True)
    engines_json = db.Column(db.Text, nullable=True)
    source = db.Column(db.String(40), nullable=False, default="analyze")
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class EdgeHit(db.Model):
    """Edge crawler / bot hit telemetry for /e/<token> endpoints."""

    __tablename__ = "edge_hits"

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(
        db.Integer, db.ForeignKey("site_analyses.id"), nullable=True, index=True
    )
    token = db.Column(db.String(64), nullable=False, index=True)
    path = db.Column(db.String(200), nullable=False)
    user_agent = db.Column(db.String(500), nullable=True)
    crawler = db.Column(db.String(80), nullable=True, index=True)
    ip_hash = db.Column(db.String(64), nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class AlertDelivery(db.Model):
    """Audit log of citation / SoV alert deliveries."""

    __tablename__ = "alert_deliveries"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    site_url = db.Column(db.String(500), nullable=True)
    channel = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    body = db.Column(db.Text, nullable=True)
    ok = db.Column(db.Boolean, default=False, nullable=False)
    detail = db.Column(db.String(500), nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


def ensure_schema() -> None:
    """create_all + colonne nuove su SQLite già esistente."""
    try:
        db.create_all()
    except Exception as exc:
        # Gunicorn multi-worker race: two boots CREATE TABLE at once.
        msg = str(exc).lower()
        if "already exists" not in msg and "duplicate" not in msg:
            raise
        app.logger.warning("ensure_schema create_all race ignored: %s", exc)
    with db.engine.begin() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA synchronous=NORMAL"))
        conn.execute(text("PRAGMA busy_timeout=5000"))

    def _add_column(table: str, name: str, col_type: str) -> None:
        """ADD COLUMN idempotente (race-safe tra worker Gunicorn)."""
        try:
            with db.engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {col_type}"))
        except Exception as exc:
            msg = str(exc).lower()
            if "duplicate column" in msg or "already exists" in msg:
                return
            raise

    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    if "site_analyses" in tables:
        existing = {col["name"] for col in inspector.get_columns("site_analyses")}
        alters = {
            "aio_score": "INTEGER",
            "geo_score": "INTEGER",
            "findings_json": "TEXT DEFAULT '[]'",
            "analysis_notes": "TEXT",
            "json_ld_artifact": "TEXT DEFAULT ''",
            "faq_artifact": "TEXT DEFAULT ''",
            "meta_pack_artifact": "TEXT DEFAULT ''",
            "robots_artifact": "TEXT DEFAULT ''",
            "checklist_artifact": "TEXT DEFAULT ''",
            "before_after_artifact": "TEXT DEFAULT ''",
            "pages_analyzed": "INTEGER DEFAULT 1",
            "crawl_pages_json": "TEXT DEFAULT '[]'",
            "rescan_interval": "TEXT DEFAULT 'off'",
            "rescan_hour": f"INTEGER DEFAULT {DEFAULT_RESCAN_HOUR}",
            "next_rescan_at": "DATETIME",
            "last_rescan_at": "DATETIME",
            "last_rescan_error": "TEXT",
            "public_token": "TEXT",
            "signals_hosted": "BOOLEAN DEFAULT 0",
            "signals_version": "INTEGER DEFAULT 1",
        }
        for name, col_type in alters.items():
            if name not in existing:
                _add_column("site_analyses", name, col_type)
        try:
            with db.engine.begin() as conn:
                conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS "
                        "ix_site_analyses_public_token ON site_analyses(public_token)"
                    )
                )
        except Exception:
            pass

    if "users" in tables:
        user_cols = {col["name"] for col in inspector.get_columns("users")}
        user_alters = {
            "company": "TEXT",
            "website_url": "TEXT",
            "phone": "TEXT",
            "role": "TEXT",
            "country": "TEXT",
            "plan": "TEXT DEFAULT 'free'",
            "stripe_customer_id": "TEXT",
            "stripe_subscription_id": "TEXT",
            "paddle_customer_id": "TEXT",
            "paddle_subscription_id": "TEXT",
            "reset_token_hash": "TEXT",
            "reset_token_expires": "DATETIME",
            "alert_email_enabled": "BOOLEAN DEFAULT 1",
            "webhook_url": "TEXT",
            "webhook_secret": "TEXT",
            "api_key_hash": "TEXT",
            "api_key_prefix": "TEXT",
            "prompt_bank_json": "TEXT DEFAULT ''",
            "agency_brand_json": "TEXT DEFAULT ''",
            "credit_balance_cents": "INTEGER DEFAULT 0",
            "credit_held_cents": "INTEGER DEFAULT 0",
            "session_version": "INTEGER DEFAULT 0",
            "email_verified_at": "DATETIME",
            "verify_token_hash": "TEXT",
            "verify_token_expires": "DATETIME",
            "welcome_credit_granted": "BOOLEAN DEFAULT 0",
        }
        for name, col_type in user_alters.items():
            if name not in user_cols:
                _add_column("users", name, col_type)

    if "analysis_runs" in tables:
        run_cols = {col["name"] for col in inspector.get_columns("analysis_runs")}
        run_alters = {
            "pages_analyzed": "INTEGER DEFAULT 1",
            "crawl_pages_json": "TEXT DEFAULT '[]'",
            "faq_artifact": "TEXT DEFAULT ''",
            "checklist_artifact": "TEXT DEFAULT ''",
            "before_after_artifact": "TEXT DEFAULT ''",
        }
        for name, col_type in run_alters.items():
            if name not in run_cols:
                _add_column("analysis_runs", name, col_type)

    if "analysis_jobs" in tables:
        job_cols = {col["name"] for col in inspector.get_columns("analysis_jobs")}
        legacy = {"progress", "message", "payload_json", "result_site_id"} & job_cols
        needed = {"max_pages", "competitors_json"}
        if legacy or not needed.issubset(job_cols):
            # DROP solo se esplicitamente permesso (coda volatile) — evita wipe accidentale.
            if not ALLOW_DROP_ANALYSIS_JOBS:
                app.logger.error(
                    "analysis_jobs schema legacy rilevato ma "
                    "ALLOW_DROP_ANALYSIS_JOBS=0: skip DROP. "
                    "Imposta ALLOW_DROP_ANALYSIS_JOBS=1 per ricreare la coda."
                )
            else:
                app.logger.warning(
                    "Ricreo analysis_jobs (legacy schema, ALLOW_DROP_ANALYSIS_JOBS=1)"
                )
                with db.engine.begin() as conn:
                    conn.execute(text("DROP TABLE IF EXISTS analysis_jobs"))
                try:
                    inspect(db.engine).clear_cache()
                except Exception:
                    pass
                db.create_all()
                try:
                    inspect(db.engine).clear_cache()
                except Exception:
                    pass
                cols_after = {
                    col["name"]
                    for col in inspect(db.engine).get_columns("analysis_jobs")
                }
                if {"progress", "message"} & cols_after:
                    with db.engine.begin() as conn:
                        conn.execute(text("DROP TABLE IF EXISTS analysis_jobs"))
                    AnalysisJob.__table__.create(db.engine, checkfirst=False)
        else:
            job_alters = {
                "site_id": "INTEGER",
                "max_pages": "INTEGER DEFAULT 8",
                "competitors_json": "TEXT DEFAULT '[]'",
                "run_measured": "BOOLEAN DEFAULT 0",
                "progress_done": "INTEGER DEFAULT 0",
                "progress_total": "INTEGER DEFAULT 0",
                "progress_phase": "TEXT DEFAULT ''",
                "held_cents": "INTEGER DEFAULT 0",
                "billed_cents": "INTEGER DEFAULT 0",
                "heartbeat_at": "DATETIME",
                "lease_token": "TEXT",
                "attempt_count": "INTEGER DEFAULT 0",
                "analytics_complete_sent": "BOOLEAN DEFAULT 0",
                "status": "TEXT DEFAULT 'pending'",
                "error": "TEXT",
                "created_at": "DATETIME",
                "started_at": "DATETIME",
                "finished_at": "DATETIME",
                "url": "TEXT",
                "user_id": "INTEGER",
            }
            for name, col_type in job_alters.items():
                if name not in job_cols:
                    _add_column("analysis_jobs", name, col_type)

    backfill_analysis_runs()

    # Usage-based billing tables (additive — never drop)
    db.create_all()  # creates credit_ledger and usage_events if absent

    # Unique Stripe payment intent → prevents double-credit on webhook races.
    try:
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_ledger_stripe_pi "
                    "ON credit_ledger (stripe_payment_intent) "
                    "WHERE stripe_payment_intent IS NOT NULL "
                    "AND stripe_payment_intent != ''"
                )
            )
    except Exception:
        # SQLite versions / dialects without partial indexes: best-effort only.
        app.logger.exception("credit_ledger stripe unique index skipped")


def process_pending_analyze_jobs(
    *,
    limit: int = 5,
    openai_api_key: str | None = None,
    openai_model: str | None = None,
) -> dict[str, int]:
    """Claim e processa job pending. Usato da worker e thread kick."""
    stats = {"ok": 0, "error": 0, "empty": 0}
    api_key = openai_api_key if openai_api_key is not None else OPENAI_API_KEY
    model = openai_model or OPENAI_MODEL

    def _on_abandon(abandoned_job: AnalysisJob) -> None:
        """Release credit hold when a stale job is permanently failed."""
        held = int(getattr(abandoned_job, "held_cents", 0) or 0)
        if held <= 0:
            abandoned_job.held_cents = 0
            return
        owner = db.session.get(User, abandoned_job.user_id)
        release_job_hold(db.session, owner, abandoned_job)
        app.logger.warning(
            "Released hold %s cent for abandoned job %s",
            held,
            abandoned_job.id,
        )

    for _ in range(max(1, limit)):
        job = claim_next_job(db.session, AnalysisJob, on_abandon=_on_abandon)
        if job is None:
            stats["empty"] += 1
            break
        lease_token = getattr(job, "lease_token", None)
        user = User.query.get(job.user_id)
        if user is None:
            fail_job(db.session, job, "Utente non trovato")
            # User row gone → hold row is gone too; clear job marker only.
            if int(getattr(job, "held_cents", 0) or 0):
                job.held_cents = 0
                db.session.commit()
            stats["error"] += 1
            continue
        try:
            run_measured_job = should_run_measured(
                user=user,
                requested=bool(getattr(job, "run_measured", False)) or MEASURED_SOV_ON_ANALYZE,
                env_enabled=MEASURED_SOV_ON_ANALYZE,
            )
            est = estimate_analysis_cost(
                openai_model=model,
                anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
                perplexity_model=os.getenv("PERPLEXITY_MODEL", "sonar"),
                run_measured=run_measured_job,
                n_prompts=5,
                has_openai=bool(api_key),
                has_perplexity=bool(os.getenv("PERPLEXITY_API_KEY")),
                has_anthropic=bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")),
                has_gemini=bool(
                    os.getenv("GEMINI_API_KEY")
                    or os.getenv("GOOGLE_AI_API_KEY")
                    or os.getenv("GOOGLE_API_KEY")
                ),
                gemini_model=os.getenv("GEMINI_MODEL", "gemini-flash-latest"),
                has_xai=bool(os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")),
                xai_model=os.getenv("XAI_MODEL") or os.getenv("GROK_MODEL") or "grok-4-1-fast-non-reasoning",
                has_azure=bool(
                    os.getenv("AZURE_AI_PROJECT_ENDPOINT")
                    or os.getenv("FOUNDRY_PROJECT_ENDPOINT")
                ),
                azure_model=os.getenv("AZURE_AI_MODEL")
                or os.getenv("FOUNDRY_MODEL_NAME")
                or "gpt-4o-mini",
            )
            preflight = check_page_word_budget(
                url=job.url,
                base_cost_cents=est.service_cost_eur_cents,
                balance_cents=get_balance_cents(user)
                + int(getattr(job, "held_cents", 0) or 0),
                unlimited=is_unlimited_user(user),
            )
            if preflight.is_giant:
                if fail_job(db.session, job, preflight.message[:500]):
                    release_job_hold(db.session, user, job)
                    db.session.commit()
                stats["error"] += 1
                continue
            est.service_cost_eur_cents = preflight.required_cost_cents
            job_reserved = int(getattr(job, "held_cents", 0) or 0)
            if not has_sufficient_credit_for_job(user, est, reserved_cents=job_reserved):
                required_with_grace = required_credit_with_grace_cents(est.service_cost_eur_cents)
                available = get_balance_cents(user) + job_reserved
                if fail_job(
                    db.session,
                    job,
                    (
                        f"Credito insufficiente: saldo €{available/100:.4f}, "
                        f"richiesto con margine €{required_with_grace/100:.4f}"
                    )[:500],
                ):
                    release_job_hold(db.session, user, job)
                    db.session.commit()
                stats["error"] += 1
                continue

            def _hb(phase=None, done=None, total=None):
                ok = heartbeat_job(
                    db.session,
                    job,
                    progress_phase=phase,
                    progress_done=done,
                    progress_total=total,
                )
                if not ok:
                    raise RuntimeError("job lease lost during heartbeat")
                return ok

            def _job_usage_cb(*, provider: str, model: str, input_tokens: int, output_tokens: int):
                # Persist usage then debit only while this worker still owns the lease
                # (BEGIN IMMEDIATE + FOR UPDATE inside debit_leased_job_usage).
                charged = record_actual_usage(
                    db.session,
                    UsageEvent,
                    user_id=user.id,
                    analysis_run_id=None,
                    provider=provider,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
                debit_cents = debit_cents_from_usage(charged)
                if debit_cents <= 0:
                    return
                debit_leased_job_usage(
                    db.session,
                    CreditLedger,
                    AnalysisJob,
                    user,
                    job,
                    lease_token=lease_token,
                    cost_eur_cents=debit_cents,
                    description=f"JOB usage realtime {provider}:{model}",
                )
                db.session.commit()

            analysis = run_analysis_pipeline(
                db_session=db.session,
                SiteAnalysis=SiteAnalysis,
                AnalysisRun=AnalysisRun,
                user=user,
                url=job.url,
                openai_api_key=api_key,
                openai_model=model,
                competitor_urls=job.competitors,
                run_measured=run_measured_job,
                measured_env_enabled=MEASURED_SOV_ON_ANALYZE,
                source="job",
                public_base=PUBLIC_SITE_URL or "https://centropic.ai",
                usage_callback=_job_usage_cb,
                max_pages=job.max_pages,
                heartbeat_callback=_hb,
                SovSnapshot=SovSnapshot,
                AlertDelivery=AlertDelivery,
            )
            # Restore lease on in-memory job after pipeline commits/refreshes.
            if not getattr(job, "lease_token", None):
                job.lease_token = lease_token
            finished = complete_job(db.session, job, site_id=getattr(analysis, "id", None))
            if finished:
                release_job_hold(db.session, user, job)
                # Analytics event can't use session flash queue in worker —
                # leave analytics_complete_sent=False for dashboard_job_status.
                db.session.commit()
                stats["ok"] += 1
            else:
                # Lease lost mid-run: do not release hold (new owner / reclaim path).
                app.logger.warning(
                    "Analyze job %s completed locally but lease was lost — skip hold release",
                    job.id,
                )
                stats["error"] += 1
        except Exception as exc:
            app.logger.exception("Analyze job %s failed", job.id)
            # Undo partial realtime usage/credit flushes from a failed run.
            try:
                failed_job_id = job.id
                db.session.rollback()
                job = db.session.get(AnalysisJob, failed_job_id)
                user = db.session.get(User, user.id) if user is not None else None
            except Exception:
                app.logger.exception("rollback after job failure failed")
            if job is not None:
                # Pass the original lease explicitly — never write it back onto
                # the ORM row (autoflush could overwrite a reclaimed lease).
                if fail_job(
                    db.session,
                    job,
                    format_job_error(exc),
                    lease_token=lease_token,
                ):
                    if user is not None:
                        release_job_hold(db.session, user, job)
                        db.session.commit()
            stats["error"] += 1
    return stats


def kick_analyze_worker() -> None:
    """Avvia un worker one-shot in background (daemon)."""

    def _run() -> None:
        try:
            with app.app_context():
                process_pending_analyze_jobs(limit=1)
        except Exception:
            app.logger.exception("kick_analyze_worker failed")

    threading.Thread(target=_run, daemon=True, name="analyze-kick").start()


def render_guide(slug: str):
    guide = GUIDES.get(slug)
    if not guide:
        return redirect(url_for("methodology"))
    date_iso = "2026-07-27"
    return render_template(
        "article.html",
        article_path=guide["path"],
        article_eyebrow=guide["eyebrow"],
        article_title=guide["title"],
        article_description=guide["description"],
        article_lede=guide["lede"],
        article_body=guide["body"],
        article_date=date_iso,
        article_date_human="27 luglio 2026",
    )


def backfill_analysis_runs() -> None:
    """Crea un AnalysisRun iniziale per ogni SiteAnalysis senza storico."""
    sites = SiteAnalysis.query.all()
    created = 0
    for site in sites:
        if AnalysisRun.query.filter_by(site_id=site.id).count() > 0:
            continue
        db.session.add(
            AnalysisRun(
                site_id=site.id,
                user_id=site.user_id,
                url=site.url,
                domain=site.domain,
                page_title=site.page_title,
                aio_score=site.aio_score,
                geo_score=site.geo_score,
                findings_json=site.findings_json or "[]",
                analysis_notes=site.analysis_notes,
                llms_txt=site.llms_txt or "",
                json_ld_artifact=site.json_ld_artifact or "",
                faq_artifact=getattr(site, "faq_artifact", None) or "",
                meta_pack_artifact=site.meta_pack_artifact or "",
                robots_artifact=site.robots_artifact or "",
                pages_analyzed=getattr(site, "pages_analyzed", None) or 1,
                crawl_pages_json=getattr(site, "crawl_pages_json", None) or "[]",
                source="manual",
                created_at=site.created_at or datetime.now(timezone.utc),
            )
        )
        created += 1
    if created:
        db.session.commit()
        app.logger.info("Backfilled %s analysis_runs", created)


def client_ip() -> str:
    """Client IP for rate limits.

    Use ProxyFix-adjusted ``remote_addr`` only. Never read ``X-Real-IP`` /
    first ``X-Forwarded-For`` from the client — those are forgeable when the
    app is reachable without a stripping reverse proxy.
    """
    return (request.remote_addr or "unknown").strip() or "unknown"


def analyses_today(user_id: int) -> int:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        AnalysisRun.query.filter(
            AnalysisRun.user_id == user_id,
            AnalysisRun.created_at >= start,
        ).count()
    )


def analyses_total(user_id: int) -> int:
    """Conteggio lifetime di AnalysisRun per account (piano Free)."""
    return AnalysisRun.query.filter_by(user_id=user_id).count()


def analyses_used_for_quota(user: User) -> int:
    if user.is_pro:
        return analyses_today(user.id)
    return analyses_total(user.id)


def free_site_count(user_id: int) -> int:
    return SiteAnalysis.query.filter_by(user_id=user_id).count()


def free_analyses_exhausted(user: User) -> bool:
    """True solo se Free non può avviare nulla di nuovo e non ha siti da ri-analizzare."""
    if user.is_pro:
        return False
    if free_site_count(user.id) > 0:
        # Può sempre ri-misurare il sito già registrato (loop attivazione).
        return False
    return analyses_total(user.id) >= FREE_TOTAL_ANALYSES


def free_upsell_suggested(user: User) -> bool:
    """Soft upsell dopo le analisi Free iniziali (senza bloccare il remesure)."""
    if user.is_pro:
        return False
    return analyses_total(user.id) >= FREE_TOTAL_ANALYSES


def wants_json_response() -> bool:
    if request.path.startswith("/api/"):
        return True
    if request.is_json:
        return True
    accept = request.accept_mimetypes
    best = accept.best_match(["application/json", "text/html"])
    return bool(
        best == "application/json"
        and accept[best] >= accept["text/html"]
    )


FREE_QUOTA_BANNER = (
    "Hai usato le analisi Free iniziali. Puoi continuare a ri-analizzare il tuo sito; "
    "passa a Plus per più brand, crawl completo e monitoraggio"
)


def quota_block_response(
    *,
    message: str,
    code: str = "quota_exceeded",
) -> Any:
    """HTTP 423 (JSON) oppure redirect a /prezzi (HTML)."""
    upgrade = url_for("pro_interest") if not payments_enabled() else url_for("pricing")
    if wants_json_response():
        return (
            jsonify(
                {
                    "ok": False,
                    "error": code,
                    "message": message,
                    "upgrade_url": upgrade,
                }
            ),
            423,
        )
    flash(message, "warning")
    return redirect(upgrade if code.startswith("free_") else url_for("pricing"))


def enforce_analyze_limits(
    user: User,
    *,
    url: str,
    existing: SiteAnalysis | None,
) -> Any | None:
    """
    Controlla siti + quota analisi.
    Free: ri-analisi dello stesso URL non consuma la quota lifetime.
    Plus: tetto giornaliero su AnalysisRun (DB).
    Nota: la race residua è mitigata da UniqueConstraint(user_id,url) e
    dal rate limiter SQLite condiviso su API/dashboard.
    """
    site_count = SiteAnalysis.query.filter_by(user_id=user.id).count()
    max_sites = user.max_sites
    if existing is None and site_count >= max_sites:
        msg = (
            f"Piano {user.plan_label}: massimo {max_sites} "
            f"{'sito' if max_sites == 1 else 'siti'}. "
            "Riusa un URL già analizzato o passa a Plus."
        )
        return quota_block_response(message=msg, code="site_limit_exceeded")

    if user.is_pro:
        if analyses_today(user.id) >= user.daily_limit:
            msg = (
                f"Limite raggiunto: max {user.daily_limit} analisi ogni 24 ore "
                f"(piano {user.plan_label})."
            )
            return quota_block_response(message=msg, code="daily_limit_exceeded")
        return None

    # Free remesure of an existing site: always allowed (activation loop).
    if existing is not None:
        return None

    used = analyses_total(user.id)
    if used >= FREE_TOTAL_ANALYSES:
        return quota_block_response(
            message=FREE_QUOTA_BANNER + ".",
            code="free_analyses_exhausted",
        )
    return None


def history_limit_for(user: User) -> int:
    return plan_entitlements(user).history_limit


def plan_entitlements(user: User | None):
    """Resolved Free/Plus entitlements for the current user."""
    return entitlements_for(
        user,
        max_sites_free=MAX_SITES_FREE,
        max_sites_pro=MAX_SITES_PRO,
        free_total_analyses=FREE_TOTAL_ANALYSES,
        pro_daily_analyses=PRO_DAILY_ANALYSES,
        free_crawl_pages=FREE_CRAWL_PAGES,
        pro_crawl_pages=PRO_CRAWL_PAGES,
        pro_crawl_unlimited=PRO_CRAWL_UNLIMITED,
        free_history_limit=FREE_HISTORY_LIMIT,
        pro_history_limit=PRO_HISTORY_LIMIT,
    )


def flash_analyze_error(exc: BaseException) -> None:
    info = classify_analyze_error(exc)
    flash(f"{info['title']}. {info['message']} {info['hint']}", "error")


def start_first_analysis_if_needed(user: User, website: str | None) -> int | None:
    """Enqueue first diagnosis after signup when website_url is present."""
    if not website:
        return None
    try:
        url = normalize_url(website)
    except ValueError:
        return None
    existing = SiteAnalysis.query.filter_by(user_id=user.id, url=url).first()
    blocked = enforce_analyze_limits(user, url=url, existing=existing)
    if blocked is not None:
        return None

    # Prepaid gate: welcome credit should cover basic first diagnosis.
    if not is_unlimited_user(user):
        est = estimate_analysis_cost(
            openai_model=OPENAI_MODEL,
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
            perplexity_model=os.getenv("PERPLEXITY_MODEL", "sonar"),
            run_measured=False,
            has_openai=bool(OPENAI_API_KEY),
            has_perplexity=False,
            has_anthropic=False,
        )
        if not has_sufficient_credit(user, est):
            app.logger.info(
                "Onboarding analyze skipped for user %s: insufficient credit",
                user.id,
            )
            return None

    def _onboarding_usage_cb(*, provider: str, model: str, input_tokens: int, output_tokens: int):
        charged = record_actual_usage(
            db.session,
            UsageEvent,
            user_id=user.id,
            analysis_run_id=None,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        debit_cents = debit_cents_from_usage(charged)
        if debit_cents <= 0:
            return
        deduct_credit(
            db.session,
            CreditLedger,
            user,
            analysis_run_id=None,
            cost_eur_cents=debit_cents,
            description=f"Onboarding usage realtime {provider}:{model}",
        )

    if ASYNC_ANALYZE:
        required = required_credit_with_grace_cents(est.service_cost_eur_cents)
        held = 0
        try:
            held = hold_credit(
                db.session,
                CreditLedger,
                user,
                amount_cents=required,
                description="Riserva analisi",
            )
        except InsufficientCreditError:
            app.logger.info(
                "Onboarding analyze skipped for user %s: insufficient credit for hold",
                user.id,
            )
            return None
        job = enqueue_analysis(
            db.session,
            AnalysisJob,
            user_id=user.id,
            url=url,
            max_pages=user.crawl_pages,
            competitor_urls=[],
            run_measured=False,
            held_cents=held,
        )
        kick_analyze_worker()
        return int(job.id)
    try:
        run_analysis_pipeline(
            db_session=db.session,
            SiteAnalysis=SiteAnalysis,
            AnalysisRun=AnalysisRun,
            user=user,
            url=url,
            openai_api_key=OPENAI_API_KEY,
            openai_model=OPENAI_MODEL,
            competitor_urls=[],
            run_measured=False,
            measured_env_enabled=MEASURED_SOV_ON_ANALYZE,
            source="onboarding",
            usage_callback=_onboarding_usage_cb,
            SovSnapshot=SovSnapshot,
            AlertDelivery=AlertDelivery,
        )
    except Exception as exc:
        app.logger.exception("Onboarding analyze failed")
        try:
            db.session.rollback()
        except Exception:
            pass
        flash_analyze_error(exc)
    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
@csrf.exempt
def health():
    db_ok = True
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    status = 200 if db_ok else 503
    payload: dict[str, Any] = {
        "ok": db_ok,
        "service": "centropic",
        "time": datetime.now(timezone.utc).isoformat(),
    }
    # Dettaglio stack solo con token o per admin autenticato (evita leak pubblici).
    detail_token = (os.getenv("HEALTH_DETAIL_TOKEN") or "").strip()
    want_detail = False
    provided = (request.args.get("token") or "").strip()
    if detail_token and provided and secrets.compare_digest(detail_token, provided):
        want_detail = True
    else:
        user = current_user()
        if user is not None and user.is_admin:
            want_detail = True
    if want_detail:
        payload.update(
            {
                "openai": bool(OPENAI_API_KEY),
                "perplexity": bool((os.getenv("PERPLEXITY_API_KEY") or "").strip()),
                "anthropic": bool(
                    (
                        os.getenv("ANTHROPIC_API_KEY")
                        or os.getenv("CLAUDE_API_KEY")
                        or ""
                    ).strip()
                ),
                "gemini": bool(
                    (
                        os.getenv("GEMINI_API_KEY")
                        or os.getenv("GOOGLE_AI_API_KEY")
                        or os.getenv("GOOGLE_API_KEY")
                        or ""
                    ).strip()
                ),
                "xai": bool(
                    (
                        os.getenv("XAI_API_KEY")
                        or os.getenv("GROK_API_KEY")
                        or ""
                    ).strip()
                ),
                "azure_copilot": bool(
                    (
                        os.getenv("AZURE_AI_PROJECT_ENDPOINT")
                        or os.getenv("FOUNDRY_PROJECT_ENDPOINT")
                        or ""
                    ).strip()
                ),
                "citation_monitor": citation_monitor_available(),
                "stripe": stripe_enabled(),
                "paddle": paddle_enabled(),
                "payments": payments_enabled(),
                "payments_provider": payments_provider(),
                "measured_sov": MEASURED_SOV_ON_ANALYZE and citation_monitor_available(),
                "measured_sov_plus_only": True,
                "async_analyze": ASYNC_ANALYZE,
            }
        )
    return jsonify(payload), status


@app.route("/llms.txt")
def llms_txt():
    return send_from_directory(
        app.static_folder, "llms.txt", mimetype="text/plain; charset=utf-8"
    )


def _edge_site_or_404(token: str) -> SiteAnalysis:
    analysis = SiteAnalysis.query.filter_by(
        public_token=token, signals_hosted=True
    ).first()
    if analysis is None:
        abort(404)
    return analysis


def _edge_client_key() -> str:
    """Trusted client identity for Edge rate limits.

    Prefer ProxyFix ``remote_addr`` (last trusted hop). Never use the first
    ``X-Forwarded-For`` value — clients can forge it and bypass budgets.
    """
    return (request.remote_addr or client_ip() or "unknown").strip() or "unknown"


def _edge_rate_limited(token: str) -> bool:
    """True se il client ha superato il budget Edge."""
    return not limiter.allow(
        f"edge:{token}:{_edge_client_key()}",
        limit=EDGE_RATE_LIMIT,
        window_seconds=EDGE_RATE_WINDOW,
    )


def _edge_response(
    body: str | bytes,
    *,
    mimetype: str,
    etag_seed: str,
    analysis: SiteAnalysis,
    path: str = "",
    token: str = "",
) -> Response:
    version = int(getattr(analysis, "signals_version", 1) or 1)
    if path and token:
        try:
            ip = _edge_client_key()
            ip_hash = hashlib.sha256(f"{ip}:{token}".encode("utf-8")).hexdigest()[:32]
            record_edge_hit(
                db.session,
                EdgeHit=EdgeHit,
                site_id=analysis.id,
                token=token,
                path=path,
                user_agent=request.headers.get("User-Agent"),
                ip_hash=ip_hash,
            )
        except Exception:
            app.logger.exception("edge hit telemetry failed")
    etag = f'W/"{content_etag(etag_seed, str(version), str(analysis.id))}"'
    if request.headers.get("If-None-Match") == etag:
        return Response(status=304)
    resp = Response(body, mimetype=mimetype)
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = EDGE_CACHE_CONTROL
    resp.headers["X-GeoPulse-Edge"] = "1"
    resp.headers["X-GeoPulse-Version"] = str(version)
    if is_ai_crawler(request.headers.get("User-Agent")):
        resp.headers["X-GeoPulse-Bot"] = "1"
    if EDGE_CORS_ORIGIN:
        resp.headers["Access-Control-Allow-Origin"] = EDGE_CORS_ORIGIN
    return resp


def _edge_full_access(analysis: SiteAnalysis) -> bool:
    """Plus/Admin: artifact completi (robots + JSON-LD). Free: llms + signals."""
    owner = db.session.get(User, analysis.user_id)
    return bool(owner and owner.is_pro)


@app.route("/e/<token>/llms.txt")
@csrf.exempt
def edge_llms_txt(token: str):
    if _edge_rate_limited(token):
        return Response("rate_limited", status=429, mimetype="text/plain")
    analysis = _edge_site_or_404(token)
    body = analysis.llms_txt or f"# {analysis.domain}\n\n_Hosted by Centropic Edge Signals_\n"
    return _edge_response(
        body,
        mimetype="text/plain; charset=utf-8",
        etag_seed=body[:2000],
        analysis=analysis,
        path="llms.txt",
        token=token,
    )


@app.route("/e/<token>/robots.txt")
@csrf.exempt
def edge_robots_txt(token: str):
    if _edge_rate_limited(token):
        return Response("rate_limited", status=429, mimetype="text/plain")
    analysis = _edge_site_or_404(token)
    if not _edge_full_access(analysis):
        return jsonify(
            {
                "error": "plus_required",
                "message": "robots.txt Edge completo è riservato al piano Plus.",
            }
        ), 402
    # Sempre live dalla lista crawler (non ZIP statico).
    body = build_live_robots_txt(analysis.url or f"https://{analysis.domain}")
    return _edge_response(
        body,
        mimetype="text/plain; charset=utf-8",
        etag_seed=body,
        analysis=analysis,
        path="robots.txt",
        token=token,
    )


@app.route("/e/<token>/organization.jsonld")
@csrf.exempt
def edge_organization_jsonld(token: str):
    if _edge_rate_limited(token):
        return jsonify({"error": "rate_limited"}), 429
    analysis = _edge_site_or_404(token)
    if not _edge_full_access(analysis):
        return jsonify(
            {
                "error": "plus_required",
                "message": "JSON-LD Edge completo è riservato al piano Plus.",
            }
        ), 402
    body = extract_jsonld_body(analysis.json_ld_artifact or "")
    return _edge_response(
        body,
        mimetype="application/ld+json; charset=utf-8",
        etag_seed=body[:4000],
        analysis=analysis,
        path="organization.jsonld",
        token=token,
    )


@app.route("/e/<token>/signals.json")
@csrf.exempt
def edge_signals_json(token: str):
    if _edge_rate_limited(token):
        return jsonify({"error": "rate_limited"}), 429
    analysis = _edge_site_or_404(token)
    full = _edge_full_access(analysis)
    payload = build_signals_payload(
        analysis=analysis,
        public_base=public_base_url(),
        token=token,
        version=int(getattr(analysis, "signals_version", 1) or 1),
        full=full,
    )
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    return _edge_response(
        body,
        mimetype="application/json; charset=utf-8",
        etag_seed=body[:4000],
        analysis=analysis,
        path="signals.json",
        token=token,
    )


@app.route("/e/<token>/meta")
@csrf.exempt
def edge_meta(token: str):
    if _edge_rate_limited(token):
        return jsonify({"error": "rate_limited"}), 429
    analysis = _edge_site_or_404(token)
    try:
        ip = _edge_client_key()
        ip_hash = hashlib.sha256(f"{ip}:{token}".encode("utf-8")).hexdigest()[:32]
        record_edge_hit(
            db.session,
            EdgeHit=EdgeHit,
            site_id=analysis.id,
            token=token,
            path="meta",
            user_agent=request.headers.get("User-Agent"),
            ip_hash=ip_hash,
        )
    except Exception:
        app.logger.exception("edge meta telemetry failed")
    full = _edge_full_access(analysis)
    base = edge_base_url(public_base_url(), token)
    return jsonify(
        {
            "ok": True,
            "hosted": True,
            "tier": "full" if full else "basic",
            "version": int(getattr(analysis, "signals_version", 1) or 1),
            "domain": analysis.domain,
            "base": base,
            "endpoints": {
                "llms_txt": f"{base}/llms.txt",
                "signals_json": f"{base}/signals.json",
                **(
                    {
                        "robots_txt": f"{base}/robots.txt",
                        "organization_jsonld": f"{base}/organization.jsonld",
                    }
                    if full
                    else {}
                ),
            },
        }
    )


@app.route("/dashboard/edge/<int:analysis_id>/enable", methods=["POST"])
@login_required
def edge_enable(analysis_id: int):
    user = current_user()
    analysis = SiteAnalysis.query.filter_by(id=analysis_id, user_id=user.id).first()
    if analysis is None:
        flash("Analisi non trovata.", "error")
        return redirect(url_for("dashboard"))
    if not analysis.public_token:
        analysis.public_token = new_public_token()
    analysis.signals_hosted = True
    analysis.signals_version = int(getattr(analysis, "signals_version", 1) or 1)
    if analysis.signals_version < 1:
        analysis.signals_version = 1
    db.session.commit()
    flash(
        "Edge Signals attivo: gli artifact sono serviti dinamicamente da Centropic.",
        "success",
    )
    return redirect(url_for("dashboard") + "#edge-signals")


@app.route("/dashboard/edge/<int:analysis_id>/disable", methods=["POST"])
@login_required
def edge_disable(analysis_id: int):
    user = current_user()
    analysis = SiteAnalysis.query.filter_by(id=analysis_id, user_id=user.id).first()
    if analysis is None:
        flash("Analisi non trovata.", "error")
        return redirect(url_for("dashboard"))
    analysis.signals_hosted = False
    db.session.commit()
    flash("Edge Signals disattivato. Gli URL pubblici non rispondono più.", "success")
    return redirect(url_for("dashboard") + "#edge-signals")


@app.route("/dashboard/edge/<int:analysis_id>/rotate", methods=["POST"])
@login_required
def edge_rotate(analysis_id: int):
    user = current_user()
    analysis = SiteAnalysis.query.filter_by(id=analysis_id, user_id=user.id).first()
    if analysis is None:
        flash("Analisi non trovata.", "error")
        return redirect(url_for("dashboard"))
    analysis.public_token = new_public_token()
    analysis.signals_version = int(getattr(analysis, "signals_version", 1) or 1) + 1
    if not analysis.signals_hosted:
        analysis.signals_hosted = True
    db.session.commit()
    flash("Token Edge rigenerato. Aggiorna Worker / rewrite con il nuovo URL.", "success")
    return redirect(url_for("dashboard") + "#edge-signals")


@app.route("/ai.txt")
def ai_txt():
    return send_from_directory(
        app.static_folder, "ai.txt", mimetype="text/plain; charset=utf-8"
    )


@app.route("/humans.txt")
def humans_txt():
    return send_from_directory(
        app.static_folder, "humans.txt", mimetype="text/plain; charset=utf-8"
    )


@app.route("/.well-known/security.txt")
@app.route("/security.txt")
def security_txt():
    return send_from_directory(
        app.static_folder, "security.txt", mimetype="text/plain; charset=utf-8"
    )


@app.route("/robots.txt")
def robots_txt():
    base = public_base_url()
    ads_line = f"# Ads auth: {base}/ads.txt\n" if ADS_TXT_CONTENT else ""
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /dashboard\n"
        "Disallow: /dashboard/\n"
        "Disallow: /logout\n"
        "Disallow: /admin\n"
        "Disallow: /lang\n"
        "Disallow: /lang/\n"
        "Disallow: /crediti\n"
        "Disallow: /crediti/\n"
        "\n"
        "User-agent: GPTBot\n"
        "Allow: /\n"
        "\n"
        "User-agent: ChatGPT-User\n"
        "Allow: /\n"
        "\n"
        "User-agent: OAI-SearchBot\n"
        "Allow: /\n"
        "\n"
        "User-agent: ClaudeBot\n"
        "Allow: /\n"
        "\n"
        "User-agent: anthropic-ai\n"
        "Allow: /\n"
        "\n"
        "User-agent: PerplexityBot\n"
        "Allow: /\n"
        "\n"
        "User-agent: Google-Extended\n"
        "Allow: /\n"
        "\n"
        "User-agent: Applebot-Extended\n"
        "Allow: /\n"
        "\n"
        "User-agent: Amazonbot\n"
        "Allow: /\n"
        "\n"
        "User-agent: Bytespider\n"
        "Allow: /\n"
        "\n"
        "User-agent: CCBot\n"
        "Allow: /\n"
        "\n"
        "User-agent: cohere-ai\n"
        "Allow: /\n"
        "\n"
        f"# AI policy: {base}/ai.txt\n"
        f"# LLMs guide: {base}/llms.txt\n"
        f"{ads_line}"
        f"# Humans: {base}/humans.txt\n"
        f"# Methodology: {base}/metodologia\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )
    return Response(body, mimetype="text/plain; charset=utf-8")


@app.route("/sitemap.xml")
def sitemap_xml():
    base = public_base_url()
    pages = [
        ("/", "1.0", "weekly"),
        ("/prodotto", "0.9", "weekly"),
        ("/prezzi", "0.8", "weekly"),
        ("/metodologia", "0.9", "monthly"),
        ("/guide/llms-txt", "0.8", "monthly"),
        ("/guide/schema-ai", "0.8", "monthly"),
        ("/guide/score-vs-sov", "0.8", "monthly"),
        ("/faq", "0.8", "monthly"),
        ("/chi-siamo", "0.7", "monthly"),
        ("/contatti", "0.7", "monthly"),
        ("/llms.txt", "0.7", "weekly"),
        ("/ai.txt", "0.6", "weekly"),
        ("/humans.txt", "0.4", "monthly"),
        ("/privacy", "0.4", "yearly"),
        ("/termini", "0.4", "yearly"),
        ("/rimborsi", "0.4", "yearly"),
        ("/interesse-pro", "0.5", "monthly"),
    ]
    if ADS_TXT_CONTENT:
        pages.insert(12, ("/ads.txt", "0.5", "monthly"))
    today = datetime.now(timezone.utc).date().isoformat()
    urls = []
    for path, priority, freq in pages:
        loc = base if path == "/" else f"{base}{path}"
        urls.append(
            "  <url>\n"
            f"    <loc>{loc}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>{freq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            "  </url>"
        )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
    return Response(body, mimetype="application/xml; charset=utf-8")


@app.route("/ads.txt")
def ads_txt():
    """AdSense authorization file for crawler validation."""
    if ADS_TXT_CONTENT:
        body = ADS_TXT_CONTENT.strip() + "\n"
        return Response(body, mimetype="text/plain; charset=utf-8")
    if ADSENSE_CLIENT_ID and ADSENSE_CLIENT_ID.startswith("ca-pub-"):
        body = f"google.com, {ADSENSE_CLIENT_ID}, DIRECT, f08c47fec0942fa0\n"
        return Response(body, mimetype="text/plain; charset=utf-8")
    return Response("# ads.txt not configured\n", mimetype="text/plain; charset=utf-8", status=404)


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/terms")
@app.route("/termini")
def terms():
    return render_template("termini.html")


@app.route("/refund")
@app.route("/refund-policy")
@app.route("/rimborsi")
def refunds():
    return render_template("rimborsi.html")


@app.route("/chi-siamo")
def about():
    return render_template("about.html")


@app.route("/contatti")
def contact():
    return render_template("contact.html")


@app.route("/metodologia")
def methodology():
    return render_guide("metodologia")


@app.route("/guide/llms-txt")
def guide_llms_txt():
    return render_guide("llms-txt")


@app.route("/guide/schema-ai")
def guide_schema_ai():
    return render_guide("schema-ai")


@app.route("/guide/score-vs-sov")
def guide_score_vs_sov():
    return render_guide("score-vs-sov")


@app.route("/")
def index():
    return render_template("landing.html")


@app.route("/lang/<code>", methods=["GET", "POST"])
def set_language(code: str):
    """Persist UI language (cookie + session) and return to the previous page."""
    loc = normalize_locale(code)
    if loc not in SUPPORTED_LOCALES:
        loc = DEFAULT_LOCALE
    session["lang"] = loc
    nxt = safe_next_url(request.args.get("next") or request.form.get("next"), fallback="")
    if not nxt:
        nxt = safe_same_origin_url(request.referrer, request) or url_for("index")
    resp = make_response(redirect(nxt))
    # Language switcher URLs are not content pages — keep them out of indexes.
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    resp.set_cookie(
        LANG_COOKIE,
        loc,
        max_age=LANG_COOKIE_MAX_AGE,
        httponly=False,
        samesite="Lax",
        secure=bool(app.config.get("SESSION_COOKIE_SECURE")),
        path="/",
    )
    return resp


@app.route("/favicon.svg")
def favicon_svg():
    return redirect(url_for("static", filename="favicon.svg"), code=302)


@app.route("/favicon.ico")
def favicon_ico():
    # Prefer ICO if present; otherwise fall back to PNG mark.
    ico = os.path.join(app.static_folder or "", "favicon.ico")
    if os.path.isfile(ico):
        return redirect(url_for("static", filename="favicon.ico"), code=302)
    return redirect(url_for("static", filename="img/logo.png"), code=302)


@app.route("/prodotto")
def product():
    return render_template("product.html")


@app.route("/prezzi")
def pricing():
    return render_template(
        "pricing.html",
        stripe_ready=payments_enabled(),
        payments_ready=payments_enabled(),
        payments_provider=payments_provider(),
        paddle_overlay=paddle_overlay_ready(),
    )


@app.route("/billing/checkout", methods=["POST"])
@login_required
def billing_checkout():
    user = current_user()
    if not limiter.allow(f"billing-checkout:{user.id}", limit=10, window_seconds=3600):
        flash("Troppe richieste di checkout. Riprova tra poco.", "warning")
        return redirect(url_for("pricing"))
    if not payments_enabled():
        flash("Checkout non ancora attivo. Prenota l’interesse Plus.", "warning")
        return redirect(url_for("pro_interest"))
    if user.is_pro and not user.is_admin:
        flash("Hai già un piano Plus attivo.", "success")
        return redirect(url_for("dashboard"))

    provider = payments_provider()
    if provider == "paddle":
        # Overlay is preferred; server transaction is the fallback when only API key is set.
        if paddle_overlay_ready() and request.form.get("overlay") == "1":
            return jsonify({"ok": True, "provider": "paddle", "mode": "overlay"})
        try:
            tx = paddle_create_plus_checkout(
                user_id=user.id,
                email=user.email,
                customer_id=getattr(user, "paddle_customer_id", None),
                success_url=absolute_url("billing_success"),
            )
            if tx.get("customer_id") and not getattr(user, "paddle_customer_id", None):
                user.paddle_customer_id = str(tx["customer_id"])
                db.session.commit()
            url = tx.get("url")
            if not url:
                flash(
                    "Checkout Paddle creato ma senza URL. Verifica Default payment link "
                    "nel dashboard Paddle.",
                    "error",
                )
                return redirect(url_for("pricing"))
            return redirect(url)
        except Exception:
            app.logger.exception("Paddle Plus checkout failed")
            flash("Impossibile avviare il checkout Paddle. Riprova o contattaci.", "error")
            return redirect(url_for("pricing"))

    try:
        session_data = create_checkout_session(
            user_id=user.id,
            email=user.email,
            name=user.name,
            customer_id=user.stripe_customer_id,
            success_url=absolute_url("billing_success")
            + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=absolute_url("pricing"),
        )
        if session_data.get("customer_id") and not user.stripe_customer_id:
            user.stripe_customer_id = session_data["customer_id"]
            db.session.commit()
        return redirect(session_data["url"])
    except Exception:
        app.logger.exception("Stripe checkout failed")
        flash("Impossibile avviare il checkout. Riprova o contattaci.", "error")
        return redirect(url_for("pricing"))


@app.route("/billing/portal", methods=["POST"])
@login_required
def billing_portal():
    user = current_user()
    if payments_provider() == "paddle":
        flash(
            "Per gestire l’abbonamento Plus usa il link nella ricevuta Paddle "
            "o scrivi a info@centropic.ai.",
            "info",
        )
        return redirect(url_for("dashboard"))
    if not stripe_enabled() or not user.stripe_customer_id:
        flash("Portale abbonamento non disponibile.", "warning")
        return redirect(url_for("pricing"))
    try:
        url = create_portal_session(
            customer_id=user.stripe_customer_id,
            return_url=absolute_url("dashboard"),
        )
        return redirect(url)
    except Exception:
        app.logger.exception("Stripe portal failed")
        flash("Impossibile aprire il portale abbonamento.", "error")
        return redirect(url_for("dashboard"))


@app.route("/billing/success")
@login_required
def billing_success():
    flash(
        "Pagamento ricevuto. Il piano Plus si attiva entro pochi secondi via webhook.",
        "success",
    )
    return redirect(url_for("dashboard"))


@app.route("/billing/paddle-webhook", methods=["POST"])
@csrf.exempt
def billing_paddle_webhook():
    """Paddle Billing notifications: Plus activation + credit top-ups."""
    payload = request.get_data()
    sig = request.headers.get("Paddle-Signature", "")
    if not paddle_verify_webhook_signature(payload, sig):
        app.logger.warning("Paddle webhook signature reject")
        return jsonify({"ok": False}), 400
    try:
        event = paddle_parse_webhook_event(payload)
    except Exception as exc:
        app.logger.warning("Paddle webhook parse failed: %s", exc)
        return jsonify({"ok": False}), 400

    etype = (event.get("event_type") or event.get("eventType") or "").strip()
    data = event.get("data") or {}

    def _user_from_paddle(obj: dict) -> User | None:
        uid = paddle_extract_user_id(obj.get("custom_data"))
        if uid:
            return db.session.get(User, uid)
        cust = obj.get("customer_id") or (obj.get("customer") or {}).get("id")
        if cust:
            return User.query.filter_by(paddle_customer_id=str(cust)).first()
        sub = obj.get("subscription_id") or obj.get("id")
        if sub and etype.startswith("subscription."):
            return User.query.filter_by(paddle_subscription_id=str(sub)).first()
        return None

    try:
        if etype in {
            "subscription.activated",
            "subscription.created",
            "subscription.trialing",
            "subscription.updated",
            "subscription.canceled",
            "subscription.past_due",
            "subscription.paused",
        }:
            user = _user_from_paddle(data)
            if user is None and data.get("customer_id"):
                user = User.query.filter_by(
                    paddle_customer_id=str(data.get("customer_id"))
                ).first()
            if user is not None and (user.plan or "").lower() != "admin":
                if data.get("customer_id"):
                    user.paddle_customer_id = str(data.get("customer_id"))
                sub_id = data.get("id")
                if sub_id:
                    user.paddle_subscription_id = str(sub_id)
                status = data.get("status")
                past_due_at = None
                if (status or "").lower() == "past_due":
                    raw_ts = (
                        event.get("occurred_at")
                        or data.get("updated_at")
                        or data.get("status_changed_at")
                    )
                    if raw_ts:
                        try:
                            past_due_at = datetime.fromisoformat(
                                str(raw_ts).replace("Z", "+00:00")
                            )
                        except ValueError:
                            past_due_at = datetime.now(timezone.utc)
                    else:
                        past_due_at = datetime.now(timezone.utc)
                user.plan = plan_from_paddle_subscription_status(
                    status, past_due_at=past_due_at
                )
                db.session.commit()

        elif etype in {"transaction.completed", "transaction.paid"}:
            status = (data.get("status") or "").lower()
            if status and status not in {"completed", "paid", "billed"}:
                return jsonify({"ok": True, "ignored": status})

            # Trust only settled price_id from Paddle — never custom_data.product /
            # topup_cents (overlay checkout is client-controlled).
            user = _user_from_paddle(data)

            if transaction_grants_plus(data):
                if user is not None and (user.plan or "").lower() != "admin":
                    if data.get("customer_id"):
                        user.paddle_customer_id = str(data.get("customer_id"))
                    sub = data.get("subscription_id")
                    if sub:
                        user.paddle_subscription_id = str(sub)
                    user.plan = "plus"
                    db.session.commit()
                return jsonify({"ok": True})

            topup_cents = topup_cents_for_transaction(data)
            if not topup_cents:
                return jsonify({"ok": True, "ignored": "not_topup"})

            gross = transaction_gross_cents(data)
            if gross is not None and int(gross) != int(topup_cents):
                app.logger.warning(
                    "Paddle top-up catalog/gross mismatch catalog=%s gross=%s txn=%s",
                    topup_cents,
                    gross,
                    data.get("id"),
                )
                return jsonify({"ok": False, "error": "amount_mismatch"}), 400

            txn_id = str(data.get("id") or "").strip()
            if not txn_id:
                return jsonify({"ok": False, "error": "missing_txn"}), 400
            pi = f"paddle:{txn_id}"
            if not user:
                return jsonify({"ok": True, "ignored": "no_user"})
            already = CreditLedger.query.filter_by(stripe_payment_intent=pi).first()
            if already is not None:
                return jsonify({"ok": True, "duplicate": True})
            try:
                topup_credit(
                    db.session,
                    CreditLedger,
                    user,
                    amount_eur_cents=int(topup_cents),
                    description=f"Ricarica €{topup_cents/100:.2f} via Paddle",
                    stripe_payment_intent=pi,
                )
                if data.get("customer_id"):
                    user.paddle_customer_id = str(data.get("customer_id"))
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                return jsonify({"ok": True, "duplicate": True})
    except Exception:
        app.logger.exception("Paddle webhook handler failed")
        return jsonify({"ok": False}), 500

    return jsonify({"ok": True})


@app.route("/billing/webhook", methods=["POST"])
@csrf.exempt
def billing_webhook():
    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe_construct_event(payload, sig)
    except Exception as exc:
        app.logger.warning("Stripe webhook reject: %s", exc)
        return jsonify({"ok": False}), 400

    etype = event.get("type") or ""
    data = (event.get("data") or {}).get("object") or {}

    def _user_from_meta(obj: dict) -> User | None:
        meta = obj.get("metadata") or {}
        uid = meta.get("geopulse_user_id") or obj.get("client_reference_id")
        if uid:
            try:
                return User.query.get(int(uid))
            except (TypeError, ValueError):
                return None
        customer = obj.get("customer")
        if customer:
            return User.query.filter_by(stripe_customer_id=str(customer)).first()
        return None

    try:
        if etype == "checkout.session.completed":
            # Subscription checkout only — never upgrade from one-time top-ups
            # (mode=payment) or unpaid/async sessions.
            mode = (data.get("mode") or "").strip()
            pay_status = (data.get("payment_status") or "").strip()
            if mode != "subscription":
                app.logger.info(
                    "billing webhook ignore checkout mode=%s", mode or "?"
                )
            elif pay_status not in {"paid", "no_payment_required"}:
                app.logger.info(
                    "billing webhook ignore payment_status=%s", pay_status or "?"
                )
            else:
                user = _user_from_meta(data)
                if user is not None:
                    cust = data.get("customer")
                    sub = data.get("subscription")
                    if cust:
                        user.stripe_customer_id = str(cust)
                    if sub:
                        user.stripe_subscription_id = str(sub)
                    if (user.plan or "").lower() != "admin":
                        user.plan = "plus"
                    db.session.commit()
        elif etype in {
            "customer.subscription.updated",
            "customer.subscription.deleted",
        }:
            user = _user_from_meta(data)
            if user is None and data.get("customer"):
                user = User.query.filter_by(
                    stripe_customer_id=str(data.get("customer"))
                ).first()
            if user is not None and (user.plan or "").lower() != "admin":
                user.plan = plan_from_subscription_status(data.get("status"))
                sub_id = data.get("id")
                if sub_id:
                    user.stripe_subscription_id = str(sub_id)
                db.session.commit()
    except Exception:
        app.logger.exception("Stripe webhook handler failed")
        return jsonify({"ok": False}), 500

    return jsonify({"ok": True})


@app.route("/interesse-pro", methods=["GET", "POST"])
def pro_interest():
    """Raccoglie interesse piano Pro nella tabella pro_interests."""
    form = ProInterestForm()
    if current_user():
        user = current_user()
        if request.method == "GET":
            form.name.data = user.name
            form.email.data = user.email
            form.company.data = user.company or ""
            form.website_url.data = user.website_url or ""

    if form.validate_on_submit():
        if not limiter.allow(
            f"pro-interest:{client_ip()}", limit=8, window_seconds=3600
        ):
            flash("Troppe richieste da questo IP. Riprova più tardi.", "error")
            return render_template("pro_interest.html", form=form)

        email = form.email.data.strip().lower()
        website = ""
        if form.website_url.data:
            try:
                website = normalize_url(form.website_url.data)
            except ValueError:
                website = form.website_url.data.strip()

        # Evita duplicati ravvicinati sulla stessa email
        recent = (
            ProInterest.query.filter_by(email=email)
            .order_by(ProInterest.created_at.desc())
            .first()
        )
        if recent and recent.created_at:
            created = recent.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - created < timedelta(hours=24):
                flash(
                    "Abbiamo già ricevuto il tuo interesse Pro nelle ultime 24 ore. "
                    "Ti contatteremo a breve.",
                    "success",
                )
                return redirect(url_for("pricing"))

        lead = ProInterest(
            name=form.name.data.strip(),
            email=email,
            company=(form.company.data or "").strip() or None,
            website_url=website or None,
            note=(form.note.data or "").strip() or None,
            source="pricing",
        )
        db.session.add(lead)
        db.session.commit()
        app.logger.info(
            "Pro interest saved id=%s email=%s company=%s",
            lead.id,
            lead.email,
            lead.company,
        )
        flash(
            "Interesse Plus registrato. Ti contatteremo a "
            f"{email} appena il piano sarà disponibile "
            "(o scrivici a info@centropic.ai).",
            "success",
        )
        return redirect(url_for("pricing"))

    return render_template("pro_interest.html", form=form)


@app.route("/faq")
def faq():
    return render_template("faq.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user() is not None:
        return redirect(url_for("dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        # Stricter anti-farming limits (H3).
        if not limiter.allow(
            f"register:{client_ip()}", limit=3, window_seconds=3600
        ):
            flash("Troppe registrazioni da questo IP. Riprova più tardi.", "error")
            return render_template("register.html", form=form)
        if not limiter.allow(
            f"register-day:{client_ip()}", limit=8, window_seconds=86400
        ):
            flash("Troppe registrazioni da questo IP. Riprova più tardi.", "error")
            return render_template("register.html", form=form)
        email = form.email.data.strip().lower()
        # Anti-enumeration (M1): never reveal whether the email already exists.
        generic_ok = (
            "Se l’indirizzo non era già registrato, l’account è stato creato. "
            "Controlla la casella email per confermare l’indirizzo "
            "(richiesto per il credito di benvenuto)."
        )
        if User.query.filter_by(email=email).first():
            flash(generic_ok, "success")
            return redirect(url_for("login"))
        try:
            website = None
            if (form.website_url.data or "").strip():
                website = normalize_url(form.website_url.data)
            role_val = (form.role.data or "").strip() or None
            user = User(
                email=email,
                name=form.name.data.strip(),
                company=(form.company.data or "").strip() or None,
                website_url=website,
                phone=(form.phone.data or "").strip() or None,
                role=role_val,
                country=(form.country.data or "").strip() or None,
                plan="free",
                credit_balance_cents=0,
                welcome_credit_granted=False,
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.flush()
            # H3: never grant welcome credit at register — only after email verify,
            # and only when outbound mail is configured (otherwise farming is free).
            verify_raw = None
            if mail_configured():
                verify_raw = user.issue_verify_token(hours=EMAIL_VERIFY_HOURS)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash(generic_ok, "success")
            return redirect(url_for("login"))
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("register.html", form=form)

        if verify_raw and mail_configured():
            try:
                verify_url = absolute_url("verify_email", token=verify_raw)
                welcome_eur = (
                    WELCOME_CREDIT_CENTS / 100.0 if WELCOME_CREDIT_CENTS > 0 else None
                )
                subject, text_body, html_body = build_email_verify_email(
                    user_name=user.name,
                    verify_url=verify_url,
                    expires_hours=EMAIL_VERIFY_HOURS,
                    welcome_eur=welcome_eur,
                )
                send_email(
                    to_email=user.email,
                    subject=subject,
                    text_body=text_body,
                    html_body=html_body,
                )
            except Exception:
                app.logger.exception("Verify email failed for %s", email)

        _establish_session(user, permanent=False)
        signup_params: dict[str, Any] = {
            "method": "email",
            "event_category": "auth",
        }
        send_to = _ads_send_to(GOOGLE_ADS_SIGNUP_LABEL)
        if send_to:
            signup_params["send_to"] = send_to
        queue_analytics_event("sign_up", signup_params)

        if mail_configured():
            flash(
                "Account creato. Conferma l’email per sbloccare il credito di benvenuto "
                "e avviare la prima diagnosi."
                + (
                    f" (fino a €{WELCOME_CREDIT_CENTS/100:.2f})"
                    if WELCOME_CREDIT_CENTS > 0
                    else ""
                ),
                "success",
            )
        else:
            flash(
                "Account creato. Il credito di benvenuto richiede conferma email "
                "(invio mail non attivo su questo server).",
                "warning",
            )
        # Defer first analysis until welcome credit is granted via verify.
        return redirect(url_for("dashboard"))

    return render_template("register.html", form=form)


@app.route("/verify-email/<token>", methods=["GET"])
def verify_email(token: str):
    token = (token or "").strip()
    user = None
    if token:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        candidate = User.query.filter_by(verify_token_hash=digest).first()
        if candidate is not None and candidate.matches_verify_token(token):
            user = candidate

    if user is None:
        flash(
            "Link di conferma non valido o scaduto. Accedi e richiedi un nuovo invio "
            "dalle impostazioni, oppure registrati di nuovo.",
            "error",
        )
        return redirect(url_for("login"))

    already = user.email_verified
    user.email_verified_at = datetime.now(timezone.utc)
    user.clear_verify_token()

    granted_now = False
    if WELCOME_CREDIT_CENTS > 0 and mail_configured():
        # Atomic grant: conditional flag + unique ledger key (welcome:{user_id}).
        pi = f"welcome:{user.id}"
        already = CreditLedger.query.filter_by(stripe_payment_intent=pi).first()
        if already is None and not bool(getattr(user, "welcome_credit_granted", False)):
            claimed = (
                User.query.filter_by(id=user.id, welcome_credit_granted=False)
                .update({"welcome_credit_granted": True}, synchronize_session=False)
            )
            if claimed == 1:
                try:
                    topup_credit(
                        db.session,
                        CreditLedger,
                        user,
                        amount_eur_cents=WELCOME_CREDIT_CENTS,
                        description=(
                            f"Credito di benvenuto €{WELCOME_CREDIT_CENTS/100:.2f}"
                        ),
                        stripe_payment_intent=pi,
                    )
                    user.welcome_credit_granted = True
                    granted_now = True
                except IntegrityError:
                    db.session.rollback()
                    user = db.session.get(User, user.id)
                    if user is not None:
                        user.email_verified_at = datetime.now(timezone.utc)
                        user.clear_verify_token()
                        user.welcome_credit_granted = True

    db.session.commit()
    _establish_session(user, permanent=False)

    website = getattr(user, "website_url", None)
    job_id = None
    if granted_now or already:
        job_id = start_first_analysis_if_needed(user, website)

    if granted_now:
        msg = f"Email confermata. Credito di benvenuto: €{WELCOME_CREDIT_CENTS/100:.2f}."
        if job_id:
            msg += " Prima diagnosi avviata."
        flash(msg, "success")
    else:
        flash("Email confermata.", "success")
    if job_id:
        return redirect(url_for("dashboard", job=job_id))
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user() is not None:
        return redirect(url_for("dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        if not limiter.allow(f"login:{client_ip()}", limit=20, window_seconds=900):
            flash("Troppi tentativi di accesso. Attendi qualche minuto.", "error")
            return render_template("login.html", form=form)
        email = form.email.data.strip().lower()
        if not limiter.allow(f"login:email:{email}", limit=10, window_seconds=900):
            flash("Troppi tentativi di accesso. Attendi qualche minuto.", "error")
            return render_template("login.html", form=form)
        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(form.password.data):
            flash("Credenziali non valide.", "error")
        else:
            # Persistent cookie only when the user opts into "Resta connesso".
            _establish_session(user, permanent=bool(form.remember_me.data))
            flash("Accesso effettuato.", "success")
            next_url = safe_next_url(request.args.get("next"), fallback="")
            if next_url:
                return redirect(next_url)
            return redirect(url_for("dashboard"))

    return render_template("login.html", form=form)


@app.route("/recupero-password", methods=["GET", "POST"])
def forgot_password():
    if current_user() is not None:
        return redirect(url_for("dashboard"))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        if not limiter.allow(
            f"forgot:{client_ip()}", limit=8, window_seconds=3600
        ):
            flash("Troppe richieste di recupero. Riprova più tardi.", "error")
            return render_template("forgot_password.html", form=form)

        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        # M1: always the same success message — never reveal existence or mail status.
        generic_ok = (
            "Se l’email è registrata e l’invio mail è attivo, "
            "riceverai un link per reimpostare la password."
        )

        if user is None:
            flash(generic_ok, "success")
            return redirect(url_for("login"))

        if not mail_configured():
            app.logger.warning(
                "Password reset requested but mail not configured (email=%s)", email
            )
            flash(generic_ok, "success")
            return redirect(url_for("login"))

        try:
            raw_token = user.issue_reset_token(hours=PASSWORD_RESET_HOURS)
            db.session.commit()
            reset_url = absolute_url("reset_password", token=raw_token)
            subject, text_body, html_body = build_password_reset_email(
                user_name=user.name,
                reset_url=reset_url,
                expires_hours=PASSWORD_RESET_HOURS,
            )
            send_email(
                to_email=user.email,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
            )
        except Exception:
            db.session.rollback()
            app.logger.exception("Password reset email failed for %s", email)
            # Still generic — do not reveal send failure tied to a known account.
            flash(generic_ok, "success")
            return redirect(url_for("login"))

        flash(generic_ok, "success")
        return redirect(url_for("login"))

    return render_template("forgot_password.html", form=form)


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    if current_user() is not None:
        return redirect(url_for("dashboard"))

    token = (token or "").strip()
    user = None
    if token:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        candidate = User.query.filter_by(reset_token_hash=digest).first()
        if candidate is not None and candidate.matches_reset_token(token):
            user = candidate

    if user is None:
        flash(
            "Link di recupero non valido o scaduto. Richiedine uno nuovo.",
            "error",
        )
        return redirect(url_for("forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        if not limiter.allow(
            f"reset:{client_ip()}", limit=10, window_seconds=3600
        ):
            flash("Troppi tentativi. Riprova più tardi.", "error")
            return render_template("reset_password.html", form=form)

        user.set_password(form.password.data)
        user.clear_reset_token()
        db.session.commit()
        session.clear()
        flash("Password aggiornata. Ora puoi accedere.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", form=form)


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("Sei uscito dall’account.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    user = current_user()
    form = AnalyzeForm()
    if request.method == "GET" and not form.url.data and user and user.website_url:
        form.url.data = user.website_url
    latest: SiteAnalysis | None = (
        SiteAnalysis.query.filter_by(user_id=user.id)
        .order_by(SiteAnalysis.created_at.desc())
        .first()
    )
    pending_job = (
        AnalysisJob.query.filter(
            AnalysisJob.user_id == user.id,
            AnalysisJob.status.in_(("pending", "running")),
        )
        .order_by(AnalysisJob.created_at.desc())
        .first()
    )

    if form.validate_on_submit():
        if not limiter.allow(
            f"analyze:user:{user.id}", limit=20, window_seconds=3600
        ):
            flash(
                "Troppe analisi in poco tempo. Attendi qualche minuto e riprova.",
                "warning",
            )
            return redirect(url_for("dashboard"))
        if not limiter.allow(
            f"analyze:ip:{client_ip()}", limit=40, window_seconds=3600
        ):
            flash(
                "Limite di richieste raggiunto da questo IP. Riprova più tardi.",
                "warning",
            )
            return redirect(url_for("dashboard"))
        try:
            url = normalize_url(form.url.data)
            existing = SiteAnalysis.query.filter_by(user_id=user.id, url=url).first()
            blocked = enforce_analyze_limits(user, url=url, existing=existing)
            if blocked is not None:
                return blocked
            competitor_urls: list[str] = []
            raw_comp = (form.competitors.data or "").strip()
            if raw_comp and user.is_pro:
                for line in re.split(r"[\n,;]+", raw_comp):
                    line = line.strip()
                    if line:
                        competitor_urls.append(line)

            # ── Usage billing: stima + pagina conferma ──────────────────────
            run_meas = should_run_measured(
                user=user,
                requested=MEASURED_SOV_ON_ANALYZE,
                env_enabled=MEASURED_SOV_ON_ANALYZE,
            )
            cost = estimate_analysis_cost(
                openai_model=OPENAI_MODEL,
                anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
                perplexity_model=os.getenv("PERPLEXITY_MODEL", "sonar"),
                run_measured=run_meas,
                n_prompts=5,
                has_openai=bool(OPENAI_API_KEY),
                has_perplexity=bool(os.getenv("PERPLEXITY_API_KEY")),
                has_anthropic=bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")),
                has_gemini=bool(
                    os.getenv("GEMINI_API_KEY")
                    or os.getenv("GOOGLE_AI_API_KEY")
                    or os.getenv("GOOGLE_API_KEY")
                ),
                gemini_model=os.getenv("GEMINI_MODEL", "gemini-flash-latest"),
                has_xai=bool(os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")),
                xai_model=os.getenv("XAI_MODEL") or os.getenv("GROK_MODEL") or "grok-4-1-fast-non-reasoning",
                has_azure=bool(
                    os.getenv("AZURE_AI_PROJECT_ENDPOINT")
                    or os.getenv("FOUNDRY_PROJECT_ENDPOINT")
                ),
                azure_model=os.getenv("AZURE_AI_MODEL")
                or os.getenv("FOUNDRY_MODEL_NAME")
                or "gpt-4o-mini",
            )
            # Preventive word-count guard before any AI request
            preflight = check_page_word_budget(
                url=url,
                base_cost_cents=cost.service_cost_eur_cents,
                balance_cents=get_balance_cents(user),
                unlimited=is_unlimited_user(user),
            )
            if preflight.is_giant:
                flash(
                    "Richiesta bloccata prima dell'analisi AI. "
                    + preflight.message
                    + " Ricarica il credito o riduci la pagina da analizzare.",
                    "warning",
                )
                return redirect(url_for("topup_credit_page"))
            cost.service_cost_eur_cents = preflight.required_cost_cents
            improvement = estimate_improvement(
                existing_site=existing,
                run_measured=run_meas,
                crawl_pages=user.crawl_pages,
            )
            return render_template(
                "confirm_analyze.html",
                url=url,
                cost=cost,
                improvement=improvement,
                balance_cents=get_balance_cents(user),
                required_cents=required_credit_with_grace_cents(cost.service_cost_eur_cents),
                grace_margin_pct=round(GRACE_MARGIN * 100, 1),
                run_measured=run_meas,
                competitors_raw=raw_comp,
            )
        except ValueError as exc:
            flash(str(exc), "error")
        except Exception as exc:
            app.logger.exception("Dashboard estimate failed")
            flash_analyze_error(exc)

    job_id_q = request.args.get("job", type=int)
    if job_id_q and (
        pending_job is None
        or pending_job.id != job_id_q
    ):
        qjob = AnalysisJob.query.filter_by(id=job_id_q, user_id=user.id).first()
        if qjob is not None and qjob.status in {"pending", "running"}:
            pending_job = qjob
        elif pending_job is None:
            pending_job = qjob

    # Refresh latest after possible async completion
    latest = (
        SiteAnalysis.query.filter_by(user_id=user.id)
        .order_by(SiteAnalysis.created_at.desc())
        .first()
    )

    schedule_form = RescanScheduleForm()
    if latest and not schedule_form.is_submitted():
        schedule_form.analysis_id.data = str(latest.id)
        schedule_form.interval.data = latest.rescan_interval or "off"
        schedule_form.hour.data = str(
            clamp_hour(getattr(latest, "rescan_hour", DEFAULT_RESCAN_HOUR))
        )

    used_today = analyses_today(user.id)
    analyses_used = analyses_used_for_quota(user)
    free_exhausted = free_analyses_exhausted(user)
    free_upsell = free_upsell_suggested(user)
    run_diff = None
    if latest is not None:
        recent_runs = (
            AnalysisRun.query.filter_by(site_id=latest.id, user_id=user.id)
            .order_by(AnalysisRun.created_at.desc())
            .limit(2)
            .all()
        )
        if len(recent_runs) >= 2:
            run_diff = compare_with_previous(
                aio_score=recent_runs[0].aio_score,
                geo_score=recent_runs[0].geo_score,
                findings=recent_runs[0].findings,
                previous=recent_runs[1],
            )
        elif recent_runs:
            diff_findings = [
                f
                for f in recent_runs[0].findings
                if str(f.get("category") or "").lower() == "diff"
            ]
            if diff_findings:
                run_diff = {
                    "has_previous": True,
                    "findings": diff_findings,
                    "delta_aio": None,
                    "delta_geo": None,
                }

    crawl_pages_view = (
        critical_crawl_pages(latest.crawl_pages) if latest is not None else []
    )
    crawl_crit_n = sum(1 for p in crawl_pages_view if p.get("severity") == "critical")
    crawl_warn_n = sum(1 for p in crawl_pages_view if p.get("severity") == "warn")
    pages_analyzed_n = (
        int(latest.pages_analyzed or 0)
        if latest is not None
        else 0
    )
    if latest is not None and not pages_analyzed_n:
        pages_analyzed_n = len(latest.crawl_pages or [])

    findings_all = list(latest.findings or []) if latest is not None else []
    findings_critical = [
        f
        for f in findings_all
        if str((f or {}).get("severity") or "").lower() in {"critical", "warn"}
    ]
    findings_ok_n = sum(
        1
        for f in findings_all
        if str((f or {}).get("severity") or "").lower() == "ok"
    )

    engine_breakdown = None
    geo_suite = {}
    if latest is not None:
        engine_breakdown = compute_engine_breakdown(
            aio_score=latest.aio_score,
            geo_score=latest.geo_score,
            findings=findings_all,
            robots_text=latest.robots_probed_text or "",
            competitors=latest.competitors,
        )
        measured = (latest.signals or {}).get("sov_measured")
        # Overlay SoV measured solo per Plus: Free resta su proxy.
        if user.is_pro and isinstance(measured, dict):
            engine_breakdown = apply_measured_sov(engine_breakdown, measured)
        geo_suite = {
            "entity_graph": (latest.signals or {}).get("entity_graph") or {},
            "citability": (latest.signals or {}).get("citability") or {},
            "schema_quality": (latest.signals or {}).get("schema_quality") or {},
            "locales": (latest.signals or {}).get("locales") or {},
            "publish_verify": (latest.signals or {}).get("publish_verify") or {},
            "llms_lint": (latest.signals or {}).get("llms_lint") or {},
            "local_pack": (latest.signals or {}).get("local_pack") or {},
            "sov_measured": (
                measured
                if user.is_pro and isinstance(measured, dict)
                else {}
            ),
        }

    edge_ctx: dict[str, Any] | None = None
    if latest is not None and getattr(latest, "signals_hosted", False) and latest.public_token:
        base = edge_base_url(public_base_url(), latest.public_token)
        signals_url = f"{base}/signals.json"
        edge_ctx = {
            "base": base,
            "llms_url": f"{base}/llms.txt",
            "robots_url": f"{base}/robots.txt",
            "jsonld_url": f"{base}/organization.jsonld",
            "signals_url": signals_url,
            "meta_url": f"{base}/meta",
            "version": int(getattr(latest, "signals_version", 1) or 1),
            "worker": cloudflare_worker_snippet(
                origin_edge_base=base,
                site_origin=latest.url or f"https://{latest.domain}",
            ),
            "vercel": vercel_edge_config_snippet(origin_edge_base=base),
            "embed": html_embed_snippet(signals_url=signals_url),
            "crawlers": top_crawlers_for_site(EdgeHit, site_id=latest.id, limit=8),
        }

    return render_template(
        "dashboard.html",
        form=form,
        schedule_form=schedule_form,
        latest=latest,
        run_diff=run_diff,
        engine_breakdown=engine_breakdown,
        geo_suite=geo_suite,
        edge=edge_ctx,
        openai_ready=bool(OPENAI_API_KEY),
        citation_ready=citation_monitor_available(),
        js_crawl_ready=js_crawl_available(),
        gsc=gsc_status(),
        used_today=used_today,
        analyses_used=analyses_used,
        daily_limit=user.daily_limit,
        analysis_limit_lifetime=user.analysis_limit_lifetime,
        free_exhausted=free_exhausted,
        free_upsell=free_upsell,
        free_quota_banner=FREE_QUOTA_BANNER,
        max_sites=user.max_sites,
        crawl_pages_limit=user.crawl_pages,
        crawl_unlimited=user.crawl_unlimited,
        crawl_pages_view=crawl_pages_view,
        crawl_crit_n=crawl_crit_n,
        crawl_warn_n=crawl_warn_n,
        pages_analyzed_n=pages_analyzed_n,
        findings_critical=findings_critical,
        findings_all_n=len(findings_all),
        findings_ok_n=findings_ok_n,
        site_count=SiteAnalysis.query.filter_by(user_id=user.id).count(),
        user_plan=user.plan_label,
        is_pro=user.is_pro,
        pending_job=pending_job,
        stripe_ready=payments_enabled(),
        payments_ready=payments_enabled(),
        payments_provider=payments_provider(),
    )


@app.route("/dashboard/analyze/confirmed", methods=["POST"])
@login_required
def dashboard_analyze_confirmed():
    """Step 2: user confirmed cost+improvement → check credit → run analysis."""
    user = current_user()
    url_raw = (request.form.get("url") or "").strip()
    run_measured_flag = request.form.get("run_measured") == "1"
    competitors_raw = (request.form.get("competitors") or "").strip()
    # Ignore client cost_cents — recomputed server-side below.

    if not url_raw:
        flash("URL mancante.", "error")
        return redirect(url_for("dashboard"))

    try:
        url = normalize_url(url_raw)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("dashboard"))

    # Rate limit (idempotent check)
    if not limiter.allow(f"analyze:user:{user.id}", limit=20, window_seconds=3600):
        flash("Troppe analisi in poco tempo. Attendi qualche minuto e riprova.", "warning")
        return redirect(url_for("dashboard"))

    # Recompute cost server-side — never trust client-supplied cost_cents.
    run_meas = should_run_measured(
        user=user,
        requested=run_measured_flag and MEASURED_SOV_ON_ANALYZE,
        env_enabled=MEASURED_SOV_ON_ANALYZE,
    )
    cost = estimate_analysis_cost(
        openai_model=OPENAI_MODEL,
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
        perplexity_model=os.getenv("PERPLEXITY_MODEL", "sonar"),
        run_measured=run_meas,
        n_prompts=5,
        has_openai=bool(OPENAI_API_KEY),
        has_perplexity=bool(os.getenv("PERPLEXITY_API_KEY")),
        has_anthropic=bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")),
        has_gemini=bool(
            os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_AI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        ),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-flash-latest"),
        has_xai=bool(os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")),
        xai_model=os.getenv("XAI_MODEL") or os.getenv("GROK_MODEL") or "grok-4-1-fast-non-reasoning",
        has_azure=bool(
            os.getenv("AZURE_AI_PROJECT_ENDPOINT")
            or os.getenv("FOUNDRY_PROJECT_ENDPOINT")
        ),
        azure_model=os.getenv("AZURE_AI_MODEL")
        or os.getenv("FOUNDRY_MODEL_NAME")
        or "gpt-4o-mini",
    )
    balance = get_balance_cents(user)
    preflight = check_page_word_budget(
        url=url,
        base_cost_cents=cost.service_cost_eur_cents,
        balance_cents=balance,
        unlimited=is_unlimited_user(user),
    )
    if preflight.is_giant:
        flash(
            "Richiesta bloccata prima dell'analisi AI. "
            + preflight.message
            + " Ricarica il credito o riduci la pagina target.",
            "warning",
        )
        return redirect(url_for("topup_credit_page"))
    cost.service_cost_eur_cents = preflight.required_cost_cents
    cost_cents = cost.service_cost_eur_cents

    competitor_urls: list[str] = []
    if competitors_raw and user.is_pro:
        for line in re.split(r"[\n,;]+", competitors_raw):
            line = line.strip()
            if line:
                competitor_urls.append(line)

    def _usage_cb(*, provider: str, model: str, input_tokens: int, output_tokens: int):
        charged = record_actual_usage(
            db.session,
            UsageEvent,
            user_id=user.id,
            analysis_run_id=None,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        debit_cents = debit_cents_from_usage(charged)
        if debit_cents <= 0:
            return
        deduct_credit(
            db.session,
            CreditLedger,
            user,
            analysis_run_id=None,
            cost_eur_cents=debit_cents,
            description=f"AI usage realtime {provider}:{model}",
        )

    existing = SiteAnalysis.query.filter_by(user_id=user.id, url=url).first()
    blocked = enforce_analyze_limits(user, url=url, existing=existing)
    if blocked is not None:
        return blocked

    # Atomic lock: re-check credit + concurrent job cap under row lock.
    try:
        assert_can_start_analysis(
            db.session,
            user,
            AnalysisJob=AnalysisJob,
            required_cents=required_credit_with_grace_cents(cost_cents),
            max_concurrent_jobs=MAX_CONCURRENT_ANALYZE_JOBS,
        )
    except ConcurrentAnalysisError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("dashboard"))
    except InsufficientCreditError:
        balance = get_balance_cents(user)
        required_with_grace = required_credit_with_grace_cents(cost_cents)
        shortage = max(0, required_with_grace - balance)
        flash(
            f"Credito insufficiente: hai €{balance/100:.4f}, "
            f"servono €{required_with_grace/100:.4f} (include margine sicurezza {round(GRACE_MARGIN*100,1):.1f}%). "
            f"Ricarica almeno €{shortage/100:.4f}.",
            "error",
        )
        return redirect(url_for("topup_credit_page"))

    if ASYNC_ANALYZE:
        required = required_credit_with_grace_cents(cost_cents)
        held = 0
        try:
            held = hold_credit(
                db.session,
                CreditLedger,
                user,
                amount_cents=required,
                description="Riserva analisi",
            )
        except InsufficientCreditError:
            balance = get_balance_cents(user)
            required_with_grace = required
            shortage = max(0, required_with_grace - balance)
            flash(
                f"Credito insufficiente: hai €{balance/100:.4f}, "
                f"servono €{required_with_grace/100:.4f} (include margine sicurezza {round(GRACE_MARGIN*100,1):.1f}%). "
                f"Ricarica almeno €{shortage/100:.4f}.",
                "error",
            )
            return redirect(url_for("topup_credit_page"))
        job = enqueue_analysis(
            db.session,
            AnalysisJob,
            user_id=user.id,
            url=url,
            max_pages=user.crawl_pages,
            competitor_urls=competitor_urls[:3],
            run_measured=run_meas,
            held_cents=held,
        )
        kick_analyze_worker()
        flash("Analisi in coda. I crediti saranno scalati in tempo reale durante l'esecuzione.", "success")
        return redirect(url_for("dashboard", job=job.id))

    try:
        latest = run_analysis_pipeline(
            db_session=db.session,
            SiteAnalysis=SiteAnalysis,
            AnalysisRun=AnalysisRun,
            user=user,
            url=url,
            openai_api_key=OPENAI_API_KEY,
            openai_model=OPENAI_MODEL,
            competitor_urls=competitor_urls[:3],
            run_measured=run_meas,
            measured_env_enabled=MEASURED_SOV_ON_ANALYZE,
            source="manual",
            usage_callback=_usage_cb,
            SovSnapshot=SovSnapshot,
            AlertDelivery=AlertDelivery,
        )
        db.session.commit()

        pages_n = int(latest.pages_analyzed or 1)
        new_balance = get_balance_cents(user)
        flash(
            f"Analisi completata su {pages_n} pagine — score, findings e pack pronti. "
            f"Credito residuo: €{new_balance/100:.4f}.",
            "success",
        )
    except InsufficientCreditError as exc:
        try:
            db.session.rollback()
        except Exception:
            pass
        flash(str(exc), "error")
        return redirect(url_for("topup_credit_page"))
    except Exception as exc:
        app.logger.exception("Confirmed analyze failed")
        try:
            db.session.rollback()
        except Exception:
            pass
        flash_analyze_error(exc)

    return redirect(url_for("dashboard"))


# ── Top-up pages & Stripe payment ──────────────────────────────────────────

_TOPUP_PACKAGES = [
    {"cents": 100,   "label": "Starter",    "analyses": "~30"},
    {"cents": 500,   "label": "Piccolo",    "analyses": "~150"},
    {"cents": 1000,  "label": "Standard",   "analyses": "~300"},
    {"cents": 5000,  "label": "Avanzato",   "analyses": "1.500+"},
    {"cents": 10000, "label": "Pro",        "analyses": "3.000+"},
]

STRIPE_TOPUP_SUCCESS_URL = os.getenv("STRIPE_TOPUP_SUCCESS_URL", "")
STRIPE_TOPUP_CANCEL_URL  = os.getenv("STRIPE_TOPUP_CANCEL_URL",  "")


@app.route("/crediti", methods=["GET"])
@login_required
def topup_credit_page():
    user = current_user()
    ledger = (
        CreditLedger.query.filter_by(user_id=user.id)
        .order_by(CreditLedger.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template(
        "topup.html",
        balance_cents=get_balance_cents(user),
        ledger=ledger,
        packages=_TOPUP_PACKAGES,
    )


@app.route("/crediti/checkout", methods=["POST"])
@login_required
def topup_stripe_checkout():
    """Create a payment checkout for a credit top-up (Paddle preferred, Stripe fallback)."""
    user = current_user()
    if not limiter.allow(f"topup-checkout:{user.id}", limit=10, window_seconds=3600):
        flash("Troppe richieste di ricarica. Riprova tra poco.", "warning")
        return redirect(url_for("topup_credit_page"))
    amount_cents = int(request.form.get("amount_cents") or 0)
    if amount_cents not in {pkg["cents"] for pkg in _TOPUP_PACKAGES}:
        flash("Importo non valido.", "error")
        return redirect(url_for("topup_credit_page"))

    provider = payments_provider()
    if provider == "paddle" and paddle_topup_price_id(amount_cents):
        if paddle_overlay_ready() and request.form.get("overlay") == "1":
            return jsonify({"ok": True, "provider": "paddle", "mode": "overlay"})
        try:
            tx = paddle_create_topup_checkout(
                user_id=user.id,
                email=user.email,
                amount_cents=amount_cents,
                customer_id=getattr(user, "paddle_customer_id", None),
                success_url=absolute_url("topup_success"),
            )
            if tx.get("customer_id") and not getattr(user, "paddle_customer_id", None):
                user.paddle_customer_id = str(tx["customer_id"])
                db.session.commit()
            url = tx.get("url")
            if not url:
                flash(
                    "Checkout Paddle creato ma senza URL. Verifica Default payment link.",
                    "error",
                )
                return redirect(url_for("topup_credit_page"))
            return redirect(url)
        except Exception:
            app.logger.exception("Paddle topup checkout failed")
            flash("Errore durante la creazione del pagamento Paddle. Riprova.", "error")
            return redirect(url_for("topup_credit_page"))

    if not stripe_enabled():
        # Dev fallback: add credits directly only when FLASK_DEBUG=1
        if os.getenv("FLASK_DEBUG", "0") == "1":
            topup_credit(
                db.session,
                CreditLedger,
                user,
                amount_eur_cents=amount_cents,
                description=f"Ricarica test {amount_cents} cent",
            )
            db.session.commit()
            flash(f"[DEBUG] Credito di €{amount_cents/100:.2f} aggiunto.", "success")
            return redirect(url_for("topup_credit_page"))
        if provider == "paddle":
            flash(
                "Pacchetto non configurato su Paddle. Imposta PADDLE_PRICE_TOPUP_* "
                "o contattaci a info@centropic.ai.",
                "warning",
            )
        else:
            flash("Pagamenti non ancora attivi. Contattaci a info@centropic.ai.", "warning")
        return redirect(url_for("topup_credit_page"))

    try:
        import stripe as _stripe
        _stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
        from services.billing import ensure_customer
        cid = ensure_customer(
            user_id=user.id,
            email=user.email,
            name=user.name or user.email,
            customer_id=user.stripe_customer_id,
        )
        if cid != user.stripe_customer_id:
            user.stripe_customer_id = cid
            db.session.commit()

        success_url = STRIPE_TOPUP_SUCCESS_URL or absolute_url("topup_success")
        cancel_url = STRIPE_TOPUP_CANCEL_URL or absolute_url("topup_credit_page")

        session_obj = _stripe.checkout.Session.create(
            mode="payment",
            customer=cid,
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "unit_amount": amount_cents,
                    "product_data": {"name": f"Crediti Centropic — €{amount_cents/100:.2f}"},
                },
                "quantity": 1,
            }],
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            client_reference_id=str(user.id),
            metadata={"centropic_user_id": str(user.id), "topup_cents": str(amount_cents)},
        )
        return redirect(session_obj["url"])
    except Exception:
        app.logger.exception("topup checkout failed")
        flash("Errore durante la creazione del pagamento. Riprova.", "error")
        return redirect(url_for("topup_credit_page"))


@app.route("/crediti/successo")
@login_required
def topup_success():
    topup_params: dict[str, Any] = {
        "event_category": "billing",
        "currency": "EUR",
    }
    send_to = _ads_send_to(GOOGLE_ADS_TOPUP_LABEL)
    if send_to:
        topup_params["send_to"] = send_to
    queue_analytics_event("purchase", topup_params)
    queue_analytics_event("topup_success", {"event_category": "billing"})
    flash("Pagamento completato! Il credito sarà disponibile a breve.", "success")
    return redirect(url_for("topup_credit_page"))


@app.route("/billing/topup-webhook", methods=["POST"])
@csrf.exempt
def billing_topup_webhook():
    """Stripe webhook for one-time payment (credit top-up)."""
    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature", "")
    topup_secret = (os.getenv("STRIPE_TOPUP_WEBHOOK_SECRET") or "").strip()
    if not topup_secret:
        return jsonify({"ok": False, "error": "webhook not configured"}), 503
    try:
        from services.billing import construct_event as _construct
        event = _construct(payload, sig, webhook_secret=topup_secret)
    except Exception as exc:
        app.logger.warning("topup webhook sig invalid: %s", exc)
        return jsonify({"ok": False, "error": "invalid signature"}), 400

    if event["type"] == "checkout.session.completed":
        sess = event["data"]["object"]
        if sess.get("payment_status") == "paid":
            meta = sess.get("metadata") or {}
            user_id = int(meta.get("centropic_user_id") or 0)
            # Prefer Stripe-settled amount over client/metadata (anti-tamper).
            amount_total = int(sess.get("amount_total") or 0)
            meta_cents = int(meta.get("topup_cents") or 0)
            allowed = {pkg["cents"] for pkg in _TOPUP_PACKAGES}
            topup_cents = amount_total if amount_total in allowed else 0
            if topup_cents == 0 and meta_cents in allowed and amount_total == meta_cents:
                topup_cents = meta_cents
            pi = (sess.get("payment_intent") or "").strip()
            if not pi:
                # Fallback to session id — still unique per Checkout session.
                pi = f"cs:{(sess.get('id') or '').strip()}"
            if not pi or pi == "cs:":
                app.logger.error("topup webhook missing payment identity")
                return jsonify({"ok": False, "error": "missing_payment_id"}), 400
            if user_id and topup_cents:
                already = (
                    CreditLedger.query.filter_by(stripe_payment_intent=pi).first()
                )
                if already is not None:
                    return jsonify({"ok": True, "duplicate": True})
                u = db.session.get(User, user_id)
                if u:
                    try:
                        topup_credit(
                            db.session,
                            CreditLedger,
                            u,
                            amount_eur_cents=topup_cents,
                            description=f"Ricarica €{topup_cents/100:.2f} via Stripe",
                            stripe_payment_intent=pi,
                        )
                        db.session.commit()
                    except IntegrityError:
                        db.session.rollback()
                        return jsonify({"ok": True, "duplicate": True})
                    app.logger.info("topup: user %s +%d cent", user_id, topup_cents)
            elif user_id and amount_total and amount_total not in allowed:
                app.logger.warning(
                    "topup webhook rejected amount_total=%s user=%s",
                    amount_total,
                    user_id,
                )

    return jsonify({"ok": True})


# ── Admin: top-up crediti manuale ──────────────────────────────────────────

# Allowlisted admin top-up amounts (must match admin.html select options).
ADMIN_TOPUP_AMOUNTS_CENTS = frozenset({1000, 5000, 10000})


@app.route("/admin/topup/<int:user_id>", methods=["POST"])
@admin_required
def admin_topup_user(user_id: int):
    u = db.session.get(User, user_id)
    if not u:
        flash("Utente non trovato.", "error")
        return redirect(url_for("admin_home"))
    try:
        amount = int(request.form.get("amount_cents") or 0)
    except (TypeError, ValueError):
        amount = 0
    if amount not in ADMIN_TOPUP_AMOUNTS_CENTS:
        flash("Importo non consentito.", "error")
        return redirect(url_for("admin_home"))
    topup_credit(
        db.session,
        CreditLedger,
        u,
        amount_eur_cents=amount,
        description=f"Ricarica admin: {amount} cent",
    )
    db.session.commit()
    flash(f"Aggiunto €{amount/100:.4f} a {u.email}.", "success")
    return redirect(url_for("admin_home"))


@app.route("/dashboard/jobs/<int:job_id>")
@login_required
def dashboard_job_status(job_id: int):
    user = current_user()
    job = AnalysisJob.query.filter_by(id=job_id, user_id=user.id).first()
    if job is None:
        return jsonify({"ok": False, "error": "not_found"}), 404
    eta = compute_analyze_eta(
        status=job.status,
        max_pages=getattr(job, "max_pages", None),
        run_measured=bool(getattr(job, "run_measured", False)),
        competitor_count=len(job.competitors or []),
        progress_done=getattr(job, "progress_done", 0),
        progress_total=getattr(job, "progress_total", 0),
        progress_phase=getattr(job, "progress_phase", None) or None,
        started_at=job.started_at,
        created_at=job.created_at,
    )
    payload: dict[str, Any] = {
        "ok": True,
        "id": job.id,
        "status": job.status,
        "url": job.url,
        "error": job.error,
        "error_info": classify_analyze_error(job.error) if job.error else None,
        "site_id": job.site_id,
        "max_pages": getattr(job, "max_pages", None),
        "run_measured": bool(getattr(job, "run_measured", False)),
        "phase": (
            "in_coda"
            if job.status == "pending"
            else (
                eta.get("progress", {}).get("phase")
                or (
                    "in_esecuzione"
                    if job.status == "running"
                    else job.status
                )
            )
        ),
        "hint": eta.get("hint"),
        "eta_seconds": eta.get("eta_seconds"),
        "eta_label": eta.get("eta_label"),
        "eta_total_seconds": eta.get("eta_total_seconds"),
        "elapsed_seconds": eta.get("elapsed_seconds"),
        "progress": eta.get("progress"),
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }
    if job.status == "done" and not bool(getattr(job, "analytics_complete_sent", False)):
        job.analytics_complete_sent = True
        db.session.commit()
        payload["emit_analyze_complete"] = True
    return jsonify(payload)


@app.route("/dashboard/guida")
@login_required
def dashboard_guide():
    return render_template("guide.html")


@app.route("/dashboard/impostazioni", methods=["GET", "POST"])
@login_required
def dashboard_settings():
    user = current_user()
    alert_form = AlertSettingsForm(
        alert_email_enabled=bool(getattr(user, "alert_email_enabled", True)),
        webhook_url=getattr(user, "webhook_url", None) or "",
        webhook_secret=getattr(user, "webhook_secret", None) or "",
    )
    prompt_form = PromptBankForm(
        prompts="\n".join(parse_prompt_bank(getattr(user, "prompt_bank_json", None)))
    )
    vertical_form = VerticalPackForm()
    agency = parse_agency_brand(getattr(user, "agency_brand_json", None))
    agency_form = AgencyBrandForm(
        brand_name=agency.get("brand_name") or "",
        logo_url=agency.get("logo_url") or "",
        primary_color=agency.get("primary_color") or "",
        footer_note=agency.get("footer_note") or "",
    )
    password_form = ChangePasswordForm()

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        if action == "password" and password_form.validate_on_submit():
            if not user.check_password(password_form.current_password.data or ""):
                flash("Password attuale non corretta.", "error")
                return redirect(url_for("dashboard_settings"))
            user.set_password(password_form.password.data)
            db.session.commit()
            _establish_session(user, permanent=bool(session.permanent))
            flash("Password aggiornata. Le altre sessioni sono state chiuse.", "success")
            return redirect(url_for("dashboard_settings"))
        if action == "logout_all":
            user.bump_session_version()
            db.session.commit()
            _establish_session(user, permanent=bool(session.permanent))
            flash("Tutte le altre sessioni sono state invalidate.", "success")
            return redirect(url_for("dashboard_settings"))
        if action == "resend_verify":
            if user.email_verified:
                flash("Email già confermata.", "success")
                return redirect(url_for("dashboard_settings"))
            if not mail_configured():
                flash("Invio email non attivo su questo server.", "warning")
                return redirect(url_for("dashboard_settings"))
            if not limiter.allow(
                f"verify-resend:{user.id}", limit=3, window_seconds=3600
            ):
                flash("Troppe richieste. Riprova più tardi.", "error")
                return redirect(url_for("dashboard_settings"))
            try:
                raw = user.issue_verify_token(hours=EMAIL_VERIFY_HOURS)
                db.session.commit()
                verify_url = absolute_url("verify_email", token=raw)
                welcome_eur = (
                    WELCOME_CREDIT_CENTS / 100.0 if WELCOME_CREDIT_CENTS > 0 else None
                )
                subject, text_body, html_body = build_email_verify_email(
                    user_name=user.name,
                    verify_url=verify_url,
                    expires_hours=EMAIL_VERIFY_HOURS,
                    welcome_eur=welcome_eur,
                )
                send_email(
                    to_email=user.email,
                    subject=subject,
                    text_body=text_body,
                    html_body=html_body,
                )
                flash("Email di conferma reinviata.", "success")
            except Exception:
                db.session.rollback()
                app.logger.exception("Resend verify failed for user %s", user.id)
                flash("Invio non riuscito. Riprova tra poco.", "error")
            return redirect(url_for("dashboard_settings"))
        if action == "alerts" and alert_form.validate_on_submit():
            user.alert_email_enabled = bool(alert_form.alert_email_enabled.data)
            raw_hook = (alert_form.webhook_url.data or "").strip() or None
            if raw_hook:
                from services.ssrf import UnsafeURLError, assert_public_http_url

                try:
                    safe = assert_public_http_url(raw_hook, resolve=True)
                    if not safe.startswith("https://"):
                        flash("Webhook: è richiesto HTTPS pubblico.", "error")
                        return redirect(url_for("dashboard_settings"))
                    user.webhook_url = safe
                except UnsafeURLError:
                    flash(
                        "Webhook URL non consentito (solo HTTPS pubblici, no IP privati).",
                        "error",
                    )
                    return redirect(url_for("dashboard_settings"))
            else:
                user.webhook_url = None
            user.webhook_secret = (alert_form.webhook_secret.data or "").strip() or None
            db.session.commit()
            flash("Impostazioni alert salvate.", "success")
            return redirect(url_for("dashboard_settings"))
        if action == "prompts" and prompt_form.validate_on_submit():
            blocked = require_capability(plan_entitlements(user), "prompt_bank")
            if blocked:
                flash(blocked, "warning")
                return redirect(url_for("pricing"))
            lines = [
                ln.strip()
                for ln in (prompt_form.prompts.data or "").splitlines()
                if ln.strip()
            ]
            user.prompt_bank_json = dump_prompt_bank(lines)
            db.session.commit()
            flash("Prompt bank aggiornato.", "success")
            return redirect(url_for("dashboard_settings"))
        if action == "vertical" and vertical_form.validate_on_submit():
            blocked = require_capability(plan_entitlements(user), "prompt_bank")
            if blocked:
                flash(blocked, "warning")
                return redirect(url_for("pricing"))
            slug = (vertical_form.vertical.data or "").strip()
            dumped = apply_vertical_to_prompt_bank(slug)
            if not dumped:
                flash("Vertical pack non valido.", "error")
                return redirect(url_for("dashboard_settings"))
            user.prompt_bank_json = dumped
            db.session.commit()
            flash(f"Vertical pack '{slug}' applicato al prompt bank.", "success")
            return redirect(url_for("dashboard_settings"))
        if action == "agency" and agency_form.validate_on_submit():
            blocked = require_capability(plan_entitlements(user), "agency_whitelabel")
            if blocked:
                flash(blocked, "warning")
                return redirect(url_for("pricing"))
            user.agency_brand_json = dump_agency_brand(
                {
                    "brand_name": agency_form.brand_name.data or "",
                    "logo_url": agency_form.logo_url.data or "",
                    "primary_color": agency_form.primary_color.data or "",
                    "footer_note": agency_form.footer_note.data or "",
                }
            )
            db.session.commit()
            flash("White-label salvato.", "success")
            return redirect(url_for("dashboard_settings"))
        if action == "api_key":
            blocked = require_capability(plan_entitlements(user), "api_access")
            if blocked:
                flash(blocked, "warning")
                return redirect(url_for("pricing"))
            raw, prefix, digest = generate_api_key()
            user.api_key_hash = digest
            user.api_key_prefix = prefix
            db.session.commit()
            flash(
                "Nuova API key generata. Copiala ora: non sarà più mostrata per intero.",
                "success",
            )
            # One-time reveal in this response only (never via flash/session cookie).
            ents = plan_entitlements(user)
            return render_template(
                "settings.html",
                alert_form=alert_form,
                prompt_form=prompt_form,
                vertical_form=vertical_form,
                agency_form=agency_form,
                password_form=password_form,
                email_verified=user.email_verified,
                api_key_prefix=prefix,
                api_key_once=raw,
                verticals=list_verticals(),
                vertical_checklist=vertical_checklist(vertical_form.vertical.data),
                citation_ready=citation_monitor_available(),
                gsc=gsc_status(),
                js_crawl_ready=js_crawl_available(),
                default_prompts=resolve_prompts(user=None, locale="it", max_prompts=5),
                is_pro=user.is_pro,
                can_api=ents.can("api_access"),
                can_agency=ents.can("agency_whitelabel"),
                can_prompt_bank=ents.can("prompt_bank"),
            )

    ents = plan_entitlements(user)
    return render_template(
        "settings.html",
        alert_form=alert_form,
        prompt_form=prompt_form,
        vertical_form=vertical_form,
        agency_form=agency_form,
        password_form=password_form,
        email_verified=user.email_verified,
        api_key_prefix=getattr(user, "api_key_prefix", None),
        api_key_once=None,
        verticals=list_verticals(),
        vertical_checklist=[],
        citation_ready=citation_monitor_available(),
        gsc=gsc_status(),
        js_crawl_ready=js_crawl_available(),
        default_prompts=resolve_prompts(user=None, locale="it", max_prompts=5),
        is_pro=user.is_pro,
        can_api=ents.can("api_access"),
        can_agency=ents.can("agency_whitelabel"),
        can_prompt_bank=ents.can("prompt_bank"),
    )


@app.route("/dashboard/verify/<int:analysis_id>")
@login_required
def dashboard_verify(analysis_id: int):
    user = current_user()
    analysis = SiteAnalysis.query.filter_by(id=analysis_id, user_id=user.id).first()
    if analysis is None:
        flash("Sito non trovato.", "error")
        return redirect(url_for("dashboard"))
    probes = {}
    blob = analysis._crawl_blob
    if isinstance(blob, dict):
        probes = blob.get("probes") or {}
    verify = verify_published_pack(
        probes=probes,
        previous_run=None,
        scraped={"has_json_ld": bool(analysis.json_ld_artifact), "domain": analysis.domain},
    )
    # live re-probe quick
    try:
        from services.analyzer import probe_path

        base = analysis.url if analysis.url.endswith("/") else analysis.url + "/"
        live = {
            "llms": probe_path(base, "/llms.txt"),
            "robots": probe_path(base, "/robots.txt"),
            "ai": probe_path(base, "/ai.txt"),
            "sitemap": probe_path(base, "/sitemap.xml"),
        }
        verify = verify_published_pack(
            probes=live,
            previous_run=None,
            scraped={"has_json_ld": True, "domain": analysis.domain},
        )
        verify["live"] = True
    except Exception as exc:
        verify["live_error"] = str(exc)[:160]

    # SoV delta vs last snapshot (publish → verify → measure loop)
    sov_delta = None
    try:
        rows = list_sov_snapshots(
            SovSnapshot, site_id=analysis.id, user_id=user.id, limit=2
        )
        series = sov_series_for_chart(rows)
        if len(series) >= 2:
            a, b = series[-2], series[-1]
            if a.get("rate") is not None and b.get("rate") is not None:
                sov_delta = {
                    "from": float(a["rate"]),
                    "to": float(b["rate"]),
                    "delta": float(b["rate"]) - float(a["rate"]),
                }
    except Exception:
        app.logger.exception("verify sov_delta failed")

    return render_template(
        "verify.html",
        analysis=analysis,
        verify=verify,
        sov_delta=sov_delta,
        is_pro=user.is_pro,
    )


@app.route("/dashboard/verify/<int:analysis_id>/rescan", methods=["POST"])
@login_required
def dashboard_verify_rescan(analysis_id: int):
    """Enqueue a measured re-scan after publish verify (Plus)."""
    user = current_user()
    analysis = SiteAnalysis.query.filter_by(id=analysis_id, user_id=user.id).first()
    if analysis is None:
        flash("Sito non trovato.", "error")
        return redirect(url_for("dashboard"))
    if not user.is_pro:
        flash("Re-scan measured dopo verify è riservato a Plus.", "warning")
        return redirect(url_for("pricing"))
    # Reuse dashboard analyze flow via redirect with prefilled URL
    session["verify_rescan_url"] = analysis.url
    flash(
        "Apri Analizza in dashboard e conferma il re-scan (SoV measured attivo su Plus).",
        "success",
    )
    return redirect(url_for("dashboard", url=analysis.url, measured=1))


@app.route("/dashboard/export/whitelabel/<int:analysis_id>.md")
@login_required
@pro_required
def download_whitelabel(analysis_id: int):
    user = current_user()
    analysis = SiteAnalysis.query.filter_by(id=analysis_id, user_id=user.id).first()
    if analysis is None:
        flash("Sito non trovato.", "error")
        return redirect(url_for("dashboard"))
    series = sov_series_for_chart(
        list_sov_snapshots(SovSnapshot, site_id=analysis.id, user_id=user.id, limit=30)
    )
    md = build_whitelabel_markdown(
        site=analysis,
        agency=parse_agency_brand(getattr(user, "agency_brand_json", None)),
        sov_series=series,
    )
    buf = io.BytesIO(md.encode("utf-8"))
    buf.seek(0)
    return send_file(
        buf,
        as_attachment=True,
        download_name=f"centropic-{analysis.domain}-report.md",
        mimetype="text/markdown; charset=utf-8",
    )


@app.route("/dashboard/export/whitelabel/<int:analysis_id>.html")
@login_required
@pro_required
def download_whitelabel_html(analysis_id: int):
    user = current_user()
    analysis = SiteAnalysis.query.filter_by(id=analysis_id, user_id=user.id).first()
    if analysis is None:
        flash("Sito non trovato.", "error")
        return redirect(url_for("dashboard"))
    series = sov_series_for_chart(
        list_sov_snapshots(SovSnapshot, site_id=analysis.id, user_id=user.id, limit=30)
    )
    html = build_whitelabel_html(
        site=analysis,
        agency=parse_agency_brand(getattr(user, "agency_brand_json", None)),
        sov_series=series,
    )
    buf = io.BytesIO(html.encode("utf-8"))
    buf.seek(0)
    return send_file(
        buf,
        as_attachment=True,
        download_name=f"centropic-{analysis.domain}-report.html",
        mimetype="text/html; charset=utf-8",
    )


@app.route("/api/v1/analyze", methods=["POST"])
@csrf.exempt
def api_v1_analyze():
    """Public API: Authorization Bearer gp_xxx or X-Api-Key."""
    auth = request.headers.get("Authorization") or ""
    raw = ""
    if auth.lower().startswith("bearer "):
        raw = auth[7:].strip()
    raw = raw or (request.headers.get("X-Api-Key") or "").strip()
    user = find_user_by_api_key(User, raw)
    if user is None:
        return jsonify({"ok": False, "error": "invalid_api_key"}), 401
    if not user.is_pro:
        return jsonify({"ok": False, "error": "plus_required"}), 403
    if not limiter.allow(f"api_analyze:{user.id}", limit=30, window_seconds=3600):
        return jsonify({"ok": False, "error": "rate_limited"}), 429
    payload = request.get_json(silent=True) or {}
    url_raw = (payload.get("url") or "").strip()
    if not url_raw:
        return jsonify({"ok": False, "error": "url_required"}), 400
    try:
        url = normalize_url(url_raw)
    except Exception as exc:
        return jsonify({"ok": False, "error": "invalid_url"}), 400
    existing = SiteAnalysis.query.filter_by(user_id=user.id, url=url).first()
    blocked = enforce_analyze_limits(user, url=url, existing=existing)
    if blocked is not None:
        if isinstance(blocked, tuple):
            return blocked
        return jsonify({"ok": False, "error": "quota_exceeded"}), 423
    comps = payload.get("competitors") or []
    if not isinstance(comps, list):
        comps = []
    want_measured = should_run_measured(
        user=user,
        requested=bool(payload.get("measured")),
        env_enabled=MEASURED_SOV_ON_ANALYZE,
    )

    # Usage billing: cost estimate + credit check for API callers
    api_cost = estimate_analysis_cost(
        openai_model=OPENAI_MODEL,
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
        perplexity_model=os.getenv("PERPLEXITY_MODEL", "sonar"),
        run_measured=want_measured,
        n_prompts=5,
        has_openai=bool(OPENAI_API_KEY),
        has_perplexity=bool(os.getenv("PERPLEXITY_API_KEY")),
        has_anthropic=bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")),
        has_gemini=bool(
            os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_AI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        ),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-flash-latest"),
        has_xai=bool(os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")),
        xai_model=os.getenv("XAI_MODEL") or os.getenv("GROK_MODEL") or "grok-4-1-fast-non-reasoning",
        has_azure=bool(
            os.getenv("AZURE_AI_PROJECT_ENDPOINT")
            or os.getenv("FOUNDRY_PROJECT_ENDPOINT")
        ),
        azure_model=os.getenv("AZURE_AI_MODEL")
        or os.getenv("FOUNDRY_MODEL_NAME")
        or "gpt-4o-mini",
    )
    preflight = check_page_word_budget(
        url=url,
        base_cost_cents=api_cost.service_cost_eur_cents,
        balance_cents=get_balance_cents(user),
        unlimited=is_unlimited_user(user),
    )
    if preflight.is_giant:
        return jsonify(
            {
                "ok": False,
                "error": "page_too_large_credit_required",
                "message": preflight.message,
                "word_count": preflight.word_count,
                "required_credit_eur": round(preflight.required_cost_cents / 100, 4),
            }
        ), 413
    api_cost.service_cost_eur_cents = preflight.required_cost_cents
    try:
        assert_can_start_analysis(
            db.session,
            user,
            AnalysisJob=AnalysisJob,
            required_cents=required_credit_with_grace_cents(api_cost.service_cost_eur_cents),
            max_concurrent_jobs=MAX_CONCURRENT_ANALYZE_JOBS,
        )
    except ConcurrentAnalysisError as exc:
        return jsonify({"ok": False, "error": "too_many_jobs", "message": str(exc)}), 429
    except InsufficientCreditError:
        required_with_grace = required_credit_with_grace_cents(api_cost.service_cost_eur_cents)
        return jsonify({
            "ok": False,
            "error": "insufficient_credit",
            "message": (
                f"Credito insufficiente: hai €{get_balance_cents(user)/100:.4f}, "
                f"servono €{required_with_grace/100:.4f} (include margine sicurezza {round(GRACE_MARGIN*100,1):.1f}%). "
                "Ricarica su https://centropic.ai/crediti"
            ),
            "cost_estimate": api_cost.as_dict(),
            "required_credit_eur": round(required_with_grace / 100, 4),
        }), 402

    required_hold = required_credit_with_grace_cents(api_cost.service_cost_eur_cents)
    try:
        api_held = hold_credit(
            db.session,
            CreditLedger,
            user,
            amount_cents=required_hold,
            description="Riserva API analyze",
        )
        db.session.commit()
    except InsufficientCreditError:
        db.session.rollback()
        required_with_grace = required_hold
        return jsonify({
            "ok": False,
            "error": "insufficient_credit",
            "message": (
                f"Credito insufficiente: hai €{get_balance_cents(user)/100:.4f}, "
                f"servono €{required_with_grace/100:.4f} (include margine sicurezza {round(GRACE_MARGIN*100,1):.1f}%). "
                "Ricarica su https://centropic.ai/crediti"
            ),
            "cost_estimate": api_cost.as_dict(),
            "required_credit_eur": round(required_with_grace / 100, 4),
        }), 402

    # Track remaining hold across usage callbacks; on rollback restore full api_held.
    hold_state = {"remaining": int(api_held or 0), "released": False}

    def _release_api_hold(amount: int) -> None:
        if hold_state["released"] or amount <= 0:
            return
        try:
            db.session.refresh(user)
            release_hold(db.session, user, amount_cents=amount)
            db.session.commit()
            hold_state["released"] = True
            hold_state["remaining"] = 0
        except Exception:
            db.session.rollback()
            app.logger.exception("api analyze: failed to release credit hold")

    def _api_usage_cb(*, provider: str, model: str, input_tokens: int, output_tokens: int):
        charged = record_actual_usage(
            db.session,
            UsageEvent,
            user_id=user.id,
            analysis_run_id=None,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        debit_cents = debit_cents_from_usage(charged)
        if debit_cents <= 0:
            return
        held_now = int(hold_state["remaining"] or 0)
        deduct_credit(
            db.session,
            CreditLedger,
            user,
            analysis_run_id=None,
            cost_eur_cents=debit_cents,
            description=f"API usage realtime {provider}:{model}",
            reserved_cents=held_now,
        )
        if held_now > 0:
            consumed = consume_hold(
                db.session, user, amount_cents=min(debit_cents, held_now)
            )
            hold_state["remaining"] = max(0, held_now - int(consumed or 0))

    analysis = None
    try:
        analysis = run_analysis_pipeline(
            db_session=db.session,
            SiteAnalysis=SiteAnalysis,
            AnalysisRun=AnalysisRun,
            user=user,
            url=url,
            openai_api_key=OPENAI_API_KEY,
            openai_model=OPENAI_MODEL,
            competitor_urls=[str(c) for c in comps[:3]],
            run_measured=want_measured,
            measured_env_enabled=MEASURED_SOV_ON_ANALYZE,
            source="api",
            public_base=public_base_url(),
            usage_callback=_api_usage_cb,
            SovSnapshot=SovSnapshot,
            AlertDelivery=AlertDelivery,
        )
        db.session.commit()
    except InsufficientCreditError as exc:
        try:
            db.session.rollback()
        except Exception:
            pass
        # Rollback restores the full hold — release the original reservation.
        _release_api_hold(int(api_held or 0))
        return jsonify({"ok": False, "error": "insufficient_credit", "message": str(exc)}), 402
    except Exception as exc:
        app.logger.exception("api analyze failed")
        try:
            db.session.rollback()
        except Exception:
            pass
        _release_api_hold(int(api_held or 0))
        info = classify_analyze_error(exc)
        return (
            jsonify(
                {
                    "ok": False,
                    "error": info["code"],
                    "message": info["message"],
                    "hint": info["hint"],
                    "title": info["title"],
                }
            ),
            502,
        )

    # Success: release unused remainder of the hold.
    _release_api_hold(int(hold_state["remaining"] or 0))

    return jsonify(
        {
            "ok": True,
            "site_id": analysis.id,
            "url": analysis.url,
            "aio_score": analysis.aio_score,
            "geo_score": analysis.geo_score,
            "rating": analysis.rating,
            "findings": analysis.findings[:50],
            "signals": {
                k: analysis.signals.get(k)
                for k in (
                    "entity_graph",
                    "citability",
                    "publish_verify",
                    "sov_measured",
                    "schema_quality",
                )
                if analysis.signals.get(k)
            },
            "billing": {
                "cost_eur_cents": api_cost.service_cost_eur_cents,
                "cost_eur": round(api_cost.service_cost_eur, 4),
                "credit_balance_eur": round(get_balance_cents(user) / 100, 4),
            },
        }
    )


@app.route("/api/v1/sites", methods=["GET"])
@csrf.exempt
def api_v1_sites():
    auth = request.headers.get("Authorization") or ""
    raw = ""
    if auth.lower().startswith("bearer "):
        raw = auth[7:].strip()
    raw = raw or (request.headers.get("X-Api-Key") or "").strip()
    user = find_user_by_api_key(User, raw)
    if user is None:
        return jsonify({"ok": False, "error": "invalid_api_key"}), 401
    if not user.is_pro:
        return jsonify({"ok": False, "error": "plus_required"}), 403
    if not limiter.allow(f"api_sites:{user.id}", limit=60, window_seconds=3600):
        return jsonify({"ok": False, "error": "rate_limited"}), 429
    sites = (
        SiteAnalysis.query.filter_by(user_id=user.id)
        .order_by(SiteAnalysis.created_at.desc())
        .limit(50)
        .all()
    )
    return jsonify(
        {
            "ok": True,
            "sites": [
                {
                    "id": s.id,
                    "url": s.url,
                    "domain": s.domain,
                    "aio_score": s.aio_score,
                    "geo_score": s.geo_score,
                    "rating": (s.rating or {}).get("code"),
                    "updated_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in sites
            ],
        }
    )


@app.route("/dashboard/storico")
@login_required
def dashboard_history():
    user = current_user()
    hist_limit = history_limit_for(user)
    if user.is_pro:
        history = (
            AnalysisRun.query.filter_by(user_id=user.id)
            .order_by(AnalysisRun.created_at.desc())
            .limit(hist_limit)
            .all()
        )
    else:
        history = (
            SiteAnalysis.query.filter_by(user_id=user.id)
            .order_by(SiteAnalysis.created_at.desc())
            .limit(hist_limit)
            .all()
        )
    return render_template(
        "history.html",
        history=history,
        history_limit=hist_limit,
        history_is_runs=user.is_pro,
        is_pro=user.is_pro,
    )


@app.route("/admin")
@admin_required
def admin_home():
    now_utc = datetime.now(timezone.utc)
    month_ago = now_utc - timedelta(days=30)

    users_total = User.query.count()
    users_admin = User.query.filter(
        (User.plan == "admin") | (User.role == "admin")
    ).count()
    users_plus = User.query.filter(User.plan.in_(["plus", "pro"])).count()
    users_free = max(0, users_total - users_plus - users_admin)

    sites_total = SiteAnalysis.query.count()
    runs_total = AnalysisRun.query.count()
    runs_30d = AnalysisRun.query.filter(AnalysisRun.created_at >= month_ago).count()

    jobs_pending = AnalysisJob.query.filter_by(status="pending").count()
    jobs_running = AnalysisJob.query.filter_by(status="running").count()
    jobs_error = AnalysisJob.query.filter_by(status="error").count()

    topup_30d = int(
        db.session.query(func.coalesce(func.sum(CreditLedger.amount_cents), 0))
        .filter(CreditLedger.created_at >= month_ago, CreditLedger.amount_cents > 0)
        .scalar()
        or 0
    )
    charged_30d = int(
        db.session.query(func.coalesce(func.sum(CreditLedger.amount_cents), 0))
        .filter(CreditLedger.created_at >= month_ago, CreditLedger.amount_cents < 0)
        .scalar()
        or 0
    )
    input_tokens_30d, output_tokens_30d = (
        db.session.query(
            func.coalesce(func.sum(UsageEvent.input_tokens), 0),
            func.coalesce(func.sum(UsageEvent.output_tokens), 0),
        )
        .filter(UsageEvent.created_at >= month_ago)
        .first()
        or (0, 0)
    )

    leads = (
        ProInterest.query.order_by(ProInterest.created_at.desc()).limit(100).all()
    )
    users = User.query.order_by(User.created_at.desc()).limit(120).all()
    recent_runs = AnalysisRun.query.order_by(AnalysisRun.created_at.desc()).limit(50).all()
    recent_jobs = AnalysisJob.query.order_by(AnalysisJob.created_at.desc()).limit(50).all()
    recent_ledger = CreditLedger.query.order_by(CreditLedger.created_at.desc()).limit(80).all()
    recent_sites = SiteAnalysis.query.order_by(SiteAnalysis.created_at.desc()).limit(40).all()
    return render_template(
        "admin.html",
        leads=leads,
        users=users,
        recent_runs=recent_runs,
        recent_jobs=recent_jobs,
        recent_ledger=recent_ledger,
        recent_sites=recent_sites,
        lead_count=ProInterest.query.count(),
        user_count=users_total,
        stats={
            "users_total": users_total,
            "users_free": users_free,
            "users_plus": users_plus,
            "users_admin": users_admin,
            "sites_total": sites_total,
            "runs_total": runs_total,
            "runs_30d": runs_30d,
            "jobs_pending": jobs_pending,
            "jobs_running": jobs_running,
            "jobs_error": jobs_error,
            "topup_30d_cents": topup_30d,
            "charged_30d_cents": abs(charged_30d),
            "input_tokens_30d": int(input_tokens_30d or 0),
            "output_tokens_30d": int(output_tokens_30d or 0),
        },
        grace_margin_pct=round(GRACE_MARGIN * 100, 1),
        now_utc=now_utc,
    )


@app.route("/admin/set-plan/<int:user_id>/<plan>", methods=["POST"])
@admin_required
def admin_set_plan(user_id: int, plan: str):
    plan = (plan or "").strip().lower()
    if plan == "pro":
        plan = "plus"
    if plan not in {"free", "plus", "admin"}:
        flash("Piano non valido.", "error")
        return redirect(url_for("admin_home"))
    target = db.session.get(User, user_id)
    if target is None:
        flash("Utente non trovato.", "error")
        return redirect(url_for("admin_home"))
    # Non degradare l’admin principale per errore
    if target.email == ADMIN_EMAIL and plan != "admin":
        flash("L’admin principale deve restare piano admin.", "warning")
        return redirect(url_for("admin_home"))
    target.plan = plan
    if plan == "admin":
        target.role = "admin"
    elif (target.role or "").lower() == "admin":
        # Demotion must revoke admin privileges (is_admin checks role OR plan).
        target.role = None
    db.session.commit()
    flash(f"Piano di {target.email} aggiornato a {plan}.", "success")
    return redirect(url_for("admin_home"))


@app.route("/admin/jobs/<int:job_id>/retry", methods=["POST"])
@admin_required
def admin_retry_job(job_id: int):
    job = db.session.get(AnalysisJob, job_id)
    if job is None:
        flash("Job non trovato.", "error")
        return redirect(url_for("admin_home"))
    if job.status not in {"error", "done"}:
        flash("Puoi riaccodare solo job completati o in errore.", "warning")
        return redirect(url_for("admin_home"))
    job.status = "pending"
    job.error = None
    job.started_at = None
    job.finished_at = None
    db.session.commit()
    flash(f"Job #{job.id} rimesso in coda.", "success")
    return redirect(url_for("admin_home"))


@app.route("/admin/jobs/<int:job_id>/cancel", methods=["POST"])
@admin_required
def admin_cancel_job(job_id: int):
    job = db.session.get(AnalysisJob, job_id)
    if job is None:
        flash("Job non trovato.", "error")
        return redirect(url_for("admin_home"))
    updated = (
        AnalysisJob.query.filter(
            AnalysisJob.id == job_id,
            AnalysisJob.status.in_(["pending", "running"]),
        )
        .update(
            {
                "status": "error",
                "error": "Annullato da admin",
                "finished_at": datetime.now(timezone.utc),
                "lease_token": None,
            },
            synchronize_session=False,
        )
    )
    if updated == 1:
        db.session.refresh(job)
        owner = db.session.get(User, job.user_id)
        release_job_hold(db.session, owner, job)
        db.session.commit()
        flash(f"Job #{job_id} annullato.", "success")
    else:
        db.session.rollback()
        flash("Job non cancellabile in questo stato.", "warning")
    return redirect(url_for("admin_home"))


@app.route("/dashboard/download/<int:analysis_id>.zip")
@login_required
def download_pack(analysis_id: int):
    user = current_user()
    analysis = SiteAnalysis.query.filter_by(id=analysis_id, user_id=user.id).first()
    if analysis is None:
        flash("Analisi non trovata.", "error")
        return redirect(url_for("dashboard"))

    buffer = io.BytesIO(pack_zip_bytes(analysis))
    filename = f"centropic-{analysis.domain.replace(':', '_')}.zip"
    return send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
    )


@app.route("/dashboard/email-pack/<int:analysis_id>", methods=["POST"])
@login_required
def email_pack(analysis_id: int):
    """Invia il pack ZIP all’email dell’account registrato."""
    user = current_user()
    analysis = SiteAnalysis.query.filter_by(id=analysis_id, user_id=user.id).first()
    if analysis is None:
        flash("Analisi non trovata.", "error")
        return redirect(url_for("dashboard"))

    if not mail_configured():
        flash(
            "Invio email non ancora attivo su questo server. "
            "Puoi scaricare lo ZIP intanto.",
            "error",
        )
        return redirect(url_for("dashboard"))

    if not limiter.allow(
        f"pack-email:{user.id}",
        limit=PACK_EMAIL_DAILY_LIMIT,
        window_seconds=24 * 3600,
    ):
        flash(
            f"Limite raggiunto: massimo {PACK_EMAIL_DAILY_LIMIT} invii pack / 24h.",
            "error",
        )
        return redirect(url_for("dashboard"))

    zip_bytes = pack_zip_bytes(analysis)
    filename = f"centropic-{analysis.domain.replace(':', '_')}.zip"
    subject, text_body, html_body = build_pack_email(
        user_name=user.name,
        domain=analysis.domain,
        aio_score=analysis.aio_score,
        geo_score=analysis.geo_score,
    )
    try:
        send_email_with_attachment(
            to_email=user.email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            attachment_filename=filename,
            attachment_bytes=zip_bytes,
        )
    except Exception:
        app.logger.exception("Pack email failed user_id=%s analysis_id=%s", user.id, analysis_id)
        flash(
            "Invio email non riuscito. Riprova tra poco o scarica lo ZIP.",
            "error",
        )
        return redirect(url_for("dashboard"))

    flash(f"Pack inviato a {user.email}.", "success")
    return redirect(url_for("dashboard"))


@app.route("/dashboard/schedule", methods=["POST"])
@login_required
@pro_required
def set_rescan_schedule():
    user = current_user()
    form = RescanScheduleForm()
    if not form.validate_on_submit():
        flash("Schedule non valido.", "error")
        return redirect(url_for("dashboard"))

    try:
        analysis_id = int(form.analysis_id.data)
    except (TypeError, ValueError):
        flash("Sito non valido.", "error")
        return redirect(url_for("dashboard"))

    interval = (form.interval.data or "off").strip().lower()
    if interval not in RESCAN_INTERVALS:
        flash("Frequenza non valida.", "error")
        return redirect(url_for("dashboard"))

    analysis = SiteAnalysis.query.filter_by(id=analysis_id, user_id=user.id).first()
    if analysis is None:
        flash("Sito non trovato.", "error")
        return redirect(url_for("dashboard"))

    hour = clamp_hour(form.hour.data)
    analysis.rescan_interval = interval
    analysis.rescan_hour = hour
    if interval == "off":
        analysis.next_rescan_at = None
        analysis.last_rescan_error = None
        flash(f"Re-scan disattivato per {analysis.domain}.", "success")
    else:
        analysis.next_rescan_at = next_rescan_after(interval, hour=hour)
        analysis.last_rescan_error = None
        label = "giornaliero" if interval == "daily" else "settimanale"
        flash(
            f"Re-scan {label} alle {hour:02d}:00 UTC per {analysis.domain}. "
            f"Prossimo: {analysis.next_rescan_at.strftime('%d/%m/%Y %H:%M')} UTC.",
            "success",
        )
    db.session.commit()
    next_url = safe_next_url(
        request.form.get("next") or request.args.get("next"),
        fallback=url_for("dashboard"),
    )
    return redirect(next_url)


@app.route("/dashboard/history/<int:analysis_id>")
@login_required
@pro_required
def site_history(analysis_id: int):
    user = current_user()
    analysis = SiteAnalysis.query.filter_by(id=analysis_id, user_id=user.id).first()
    if analysis is None:
        flash("Sito non trovato.", "error")
        return redirect(url_for("dashboard"))

    runs = (
        AnalysisRun.query.filter_by(site_id=analysis.id, user_id=user.id)
        .order_by(AnalysisRun.created_at.desc())
        .limit(PRO_HISTORY_LIMIT)
        .all()
    )
    schedule_form = RescanScheduleForm(
        analysis_id=str(analysis.id),
        interval=analysis.rescan_interval or "off",
        hour=str(clamp_hour(getattr(analysis, "rescan_hour", DEFAULT_RESCAN_HOUR))),
    )
    sov_rows = list_sov_snapshots(
        SovSnapshot, site_id=analysis.id, user_id=user.id, limit=30
    )
    sov_series = sov_series_for_chart(sov_rows)
    return render_template(
        "site_history.html",
        analysis=analysis,
        runs=runs,
        schedule_form=schedule_form,
        history_limit=PRO_HISTORY_LIMIT,
        sov_series=sov_series,
    )


@app.route("/dashboard/download/run/<int:run_id>.zip")
@login_required
@pro_required
def download_run_pack(run_id: int):
    user = current_user()
    run = AnalysisRun.query.filter_by(id=run_id, user_id=user.id).first()
    if run is None:
        flash("Run non trovata.", "error")
        return redirect(url_for("dashboard"))

    buffer = io.BytesIO(pack_zip_bytes(run))
    stamp = run.created_at.strftime("%Y%m%d-%H%M") if run.created_at else "run"
    filename = f"centropic-{run.domain.replace(':', '_')}-{stamp}.zip"
    return send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
    )


@app.route("/dashboard/export/history.csv")
@login_required
@pro_required
def export_history_csv():
    user = current_user()
    runs = (
        AnalysisRun.query.filter_by(user_id=user.id)
        .order_by(AnalysisRun.created_at.desc())
        .limit(PRO_HISTORY_LIMIT)
        .all()
    )
    data = runs_to_csv(runs)
    return send_file(
        io.BytesIO(data),
        mimetype="text/csv; charset=utf-8",
        as_attachment=True,
        download_name=f"centropic-storico-{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv",
    )


@app.route("/dashboard/export/sites.zip")
@login_required
@pro_required
def export_all_sites_zip():
    user = current_user()
    sites = (
        SiteAnalysis.query.filter_by(user_id=user.id)
        .order_by(SiteAnalysis.domain.asc())
        .all()
    )
    if not sites:
        flash("Nessun sito da esportare.", "warning")
        return redirect(url_for("dashboard"))
    buffer = io.BytesIO(multi_site_zip(sites))
    return send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"centropic-siti-{datetime.now(timezone.utc).strftime('%Y%m%d')}.zip",
    )


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


with app.app_context():
    ensure_schema()
    try:
        ensure_admin_user()
    except Exception:
        # Evita crash al boot se il DB non è ancora montato
        app.logger.exception("ensure_admin_user failed")


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=debug)
