"""
GeoPulse (geopulse.it) — SaaS per ottimizzazione GEO/AIO dei siti web.
Analisi score + findings + generazione pack artifact (llms.txt, JSON-LD, meta, robots).
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
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
from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect, FlaskForm
from flask_wtf.csrf import generate_csrf
from sqlalchemy import UniqueConstraint, inspect, text
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
from services.analyzer import (
    ABS_MAX_CRAWL_PAGES,
    critical_crawl_pages,
    normalize_url,
)
from services.billing import (
    construct_event as stripe_construct_event,
    create_checkout_session,
    create_portal_session,
    plan_from_subscription_status,
    stripe_enabled,
)
from services.export import multi_site_zip, pack_zip_bytes, runs_to_csv
from services.guides import GUIDES
from services.jobs import claim_next_job, complete_job, enqueue_analysis, fail_job
from services.mailer import (
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

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FREE_DAILY_ANALYSES = max(1, int(os.getenv("FREE_DAILY_ANALYSES", "10")))
MAX_SITES_FREE = max(1, int(os.getenv("MAX_SITES_FREE", "5")))
PRO_DAILY_ANALYSES = max(FREE_DAILY_ANALYSES, int(os.getenv("PRO_DAILY_ANALYSES", "200")))
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
ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL") or "admin@geopulse.it").strip().lower()
# Nessun default in chiaro: se manca, l’admin non viene (ri)creato automaticamente.
ADMIN_PASSWORD = (os.getenv("ADMIN_PASSWORD") or "").strip()
ADMIN_NAME = os.getenv("ADMIN_NAME") or "Admin GeoPulse"
ADMIN_BOOTSTRAP = os.getenv("ADMIN_BOOTSTRAP", "0") == "1"
ASYNC_ANALYZE = os.getenv("ASYNC_ANALYZE", "1") == "1"
MEASURED_SOV_ON_ANALYZE = os.getenv("MEASURED_SOV_ON_ANALYZE", "1") == "1"
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
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY") or os.urandom(32)
app.config["SQLALCHEMY_DATABASE_URI"] = resolve_database_uri(os.getenv("DATABASE_URL"))
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
app.config["PREFERRED_URL_SCHEME"] = os.getenv("PREFERRED_URL_SCHEME", "http")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.config["WTF_CSRF_TIME_LIMIT"] = 3600
app.config["INSTANCE_RELATIVE_CONFIG"] = False
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

# Dietro Nginx: rispetta X-Forwarded-*
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

if os.getenv("FLASK_DEBUG", "0") != "1":
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

db = SQLAlchemy(app)
csrf = CSRFProtect(app)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
PUBLIC_SITE_URL = (os.getenv("PUBLIC_SITE_URL") or "https://geopulse.it").rstrip("/")


@app.after_request
def set_security_headers(response):
    # Header applicativi (nginx tiene HSTS; evitiamo duplicare X-* lì).
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
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
    reset_token_hash = db.Column(db.String(64))
    reset_token_expires = db.Column(db.DateTime)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    sites = db.relationship("SiteAnalysis", back_populates="user", lazy="dynamic")
    jobs = db.relationship("AnalysisJob", back_populates="user", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

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
        return PRO_DAILY_ANALYSES if self.is_pro else FREE_DAILY_ANALYSES

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


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------


def validate_http_url(_form: FlaskForm, field: URLField) -> None:
    value = (field.data or "").strip()
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
        validators=[DataRequired(), Length(min=2, max=160)],
    )
    website_url = StringField(
        "Sito web principale",
        validators=[DataRequired(), Length(max=500), validate_http_url],
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
        validators=[DataRequired(message="Seleziona un ruolo.")],
    )
    country = StringField(
        "Paese",
        validators=[DataRequired(), Length(min=2, max=80)],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=8, max=128)],
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

    def validate_email(self, field: StringField) -> None:
        email = (field.data or "").strip().lower()
        if not email:
            return
        existing = User.query.filter_by(email=email).first()
        if existing is not None:
            raise ValidationError(
                "Questa email è già registrata. Accedi o recupera la password."
            )


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
        validators=[DataRequired(), Length(min=8, max=128)],
    )
    confirm = PasswordField(
        "Conferma password",
        validators=[
            DataRequired(),
            EqualTo("password", message="Le password non coincidono."),
        ],
    )
    submit = SubmitField("Salva nuova password")


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


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
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
    return db.session.get(User, user_id)


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

    user = User.query.filter_by(email=ADMIN_EMAIL).first()
    if user is None:
        user = User(
            email=ADMIN_EMAIL,
            name=ADMIN_NAME,
            company="GeoPulse",
            website_url="https://geopulse.it/",
            role="admin",
            country="Italia",
            plan="admin",
        )
        user.set_password(ADMIN_PASSWORD)
        db.session.add(user)
        app.logger.info("Admin creato: %s", ADMIN_EMAIL)
    else:
        user.name = ADMIN_NAME
        user.company = user.company or "GeoPulse"
        user.website_url = user.website_url or "https://geopulse.it/"
        user.role = "admin"
        user.plan = "admin"
        if ADMIN_BOOTSTRAP:
            user.set_password(ADMIN_PASSWORD)
            app.logger.warning(
                "ADMIN_BOOTSTRAP=1: password admin resettata per %s", ADMIN_EMAIL
            )
    db.session.commit()
    return user


def public_base_url() -> str:
    """Base canonica del sito (preferisce PUBLIC_SITE_URL)."""
    configured = PUBLIC_SITE_URL
    if configured and "geopulse.it" in configured:
        return configured
    return (request.url_root or configured or "https://geopulse.it").rstrip("/")


@app.context_processor
def inject_globals() -> dict[str, Any]:
    base = public_base_url()
    path = request.path or "/"
    canonical = base if path == "/" else f"{base}{path}"
    return {
        "current_user": current_user(),
        "csrf_token": generate_csrf,
        "max_sites_free": MAX_SITES_FREE,
        "free_daily_analyses": FREE_DAILY_ANALYSES,
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
        "stripe_ready": stripe_enabled(),
        "site_author_name": SITE_AUTHOR_NAME,
        "site_author_title": SITE_AUTHOR_TITLE,
        "site_author_url": SITE_AUTHOR_URL,
        "site_owner_name": SITE_OWNER_NAME,
        "site_owner_url": SITE_OWNER_URL,
        "async_analyze": ASYNC_ANALYZE,
    }


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------


def ensure_schema() -> None:
    """create_all + colonne nuove su SQLite già esistente."""
    db.create_all()
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
        }
        for name, col_type in alters.items():
            if name not in existing:
                _add_column("site_analyses", name, col_type)

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
            "reset_token_hash": "TEXT",
            "reset_token_expires": "DATETIME",
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
            # Schema precedente incompatibile: ricrea (coda volatile, ok perdere pending).
            with db.engine.begin() as conn:
                conn.execute(text("DROP TABLE IF EXISTS analysis_jobs"))
            try:
                inspect(db.engine).clear_cache()
            except Exception:
                pass
            db.create_all()
            # Verifica: se ancora legacy, forza CREATE senza checkfirst
            try:
                inspect(db.engine).clear_cache()
            except Exception:
                pass
            cols_after = {
                col["name"] for col in inspect(db.engine).get_columns("analysis_jobs")
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
    for _ in range(max(1, limit)):
        job = claim_next_job(db.session, AnalysisJob)
        if job is None:
            stats["empty"] += 1
            break
        user = User.query.get(job.user_id)
        if user is None:
            fail_job(db.session, job, "Utente non trovato")
            stats["error"] += 1
            continue
        try:
            analysis = run_analysis_pipeline(
                db_session=db.session,
                SiteAnalysis=SiteAnalysis,
                AnalysisRun=AnalysisRun,
                user=user,
                url=job.url,
                openai_api_key=api_key,
                openai_model=model,
                competitor_urls=job.competitors,
                run_measured=bool(
                    MEASURED_SOV_ON_ANALYZE and user.is_pro and api_key
                ),
                source="job",
            )
            complete_job(db.session, job, site_id=getattr(analysis, "id", None))
            stats["ok"] += 1
        except Exception as exc:
            app.logger.exception("Analyze job %s failed", job.id)
            fail_job(db.session, job, str(exc)[:500])
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
    return (request.headers.get("X-Real-IP") or request.remote_addr or "unknown").strip()


def analyses_today(user_id: int) -> int:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        AnalysisRun.query.filter(
            AnalysisRun.user_id == user_id,
            AnalysisRun.created_at >= start,
        ).count()
    )


def history_limit_for(user: User) -> int:
    return PRO_HISTORY_LIMIT if user.is_pro else FREE_HISTORY_LIMIT


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
    return (
        jsonify(
            {
                "ok": db_ok,
                "service": "geopulse",
                "openai": bool(OPENAI_API_KEY),
                "stripe": stripe_enabled(),
                "async_analyze": ASYNC_ANALYZE,
                "time": datetime.now(timezone.utc).isoformat(),
            }
        ),
        status,
    )


@app.route("/llms.txt")
def llms_txt():
    return send_from_directory(
        app.static_folder, "llms.txt", mimetype="text/plain; charset=utf-8"
    )


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


@app.route("/robots.txt")
def robots_txt():
    base = public_base_url()
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /dashboard\n"
        "Disallow: /dashboard/\n"
        "Disallow: /logout\n"
        "Disallow: /admin\n"
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
        ("/interesse-pro", "0.5", "monthly"),
    ]
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


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/termini")
def terms():
    return render_template("termini.html")


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


@app.route("/prodotto")
def product():
    return render_template("product.html")


@app.route("/prezzi")
def pricing():
    return render_template("pricing.html", stripe_ready=stripe_enabled())


@app.route("/billing/checkout", methods=["POST"])
@login_required
def billing_checkout():
    user = current_user()
    if not stripe_enabled():
        flash("Checkout non ancora attivo. Prenota l’interesse Plus.", "warning")
        return redirect(url_for("pro_interest"))
    if user.is_pro and not user.is_admin:
        flash("Hai già un piano Plus attivo.", "success")
        return redirect(url_for("dashboard"))
    try:
        session_data = create_checkout_session(
            user_id=user.id,
            email=user.email,
            name=user.name,
            customer_id=user.stripe_customer_id,
            success_url=url_for("billing_success", _external=True)
            + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=url_for("pricing", _external=True),
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
    if not stripe_enabled() or not user.stripe_customer_id:
        flash("Portale abbonamento non disponibile.", "warning")
        return redirect(url_for("pricing"))
    try:
        url = create_portal_session(
            customer_id=user.stripe_customer_id,
            return_url=url_for("dashboard", _external=True),
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
            "(o scrivici a info@geopulse.it).",
            "success",
        )
        return redirect(url_for("pricing"))

    return render_template("pro_interest.html", form=form)


@app.route("/faq")
def faq():
    return render_template("faq.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        if not limiter.allow(
            f"register:{client_ip()}", limit=5, window_seconds=3600
        ):
            flash("Troppe registrazioni da questo IP. Riprova più tardi.", "error")
            return render_template("register.html", form=form)
        email = form.email.data.strip().lower()
        if User.query.filter_by(email=email).first():
            form.email.errors.append(
                "Questa email è già registrata. Accedi o recupera la password."
            )
            flash(
                "Questa email è già registrata. Accedi oppure usa il recupero password.",
                "error",
            )
            return render_template("register.html", form=form)
        try:
            website = normalize_url(form.website_url.data)
            user = User(
                email=email,
                name=form.name.data.strip(),
                company=form.company.data.strip(),
                website_url=website,
                phone=(form.phone.data or "").strip() or None,
                role=form.role.data,
                country=form.country.data.strip(),
                plan="free",
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            form.email.errors.append(
                "Questa email è già registrata. Accedi o recupera la password."
            )
            flash(
                "Questa email è già registrata. Accedi oppure usa il recupero password.",
                "error",
            )
            return render_template("register.html", form=form)
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("register.html", form=form)

        session.clear()
        session["user_id"] = user.id
        session.permanent = True
        flash("Account creato. Benvenuto su GeoPulse.", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        if not limiter.allow(f"login:{client_ip()}", limit=20, window_seconds=900):
            flash("Troppi tentativi di accesso. Attendi qualche minuto.", "error")
            return render_template("login.html", form=form)
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(form.password.data):
            flash("Credenziali non valide.", "error")
        else:
            session.clear()
            session["user_id"] = user.id
            session.permanent = True
            flash("Accesso effettuato.", "success")
            next_url = request.args.get("next")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect(url_for("dashboard"))

    return render_template("login.html", form=form)


@app.route("/recupero-password", methods=["GET", "POST"])
def forgot_password():
    if session.get("user_id"):
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
        generic_ok = (
            "Se l’email è registrata e l’invio mail è attivo, "
            "riceverai un link per reimpostare la password."
        )

        if user is None:
            flash(generic_ok, "success")
            return redirect(url_for("login"))

        if not mail_configured():
            flash(
                "Invio email non ancora attivo su questo server. "
                "Contatta info@geopulse.it per il reset password.",
                "warning",
            )
            return render_template("forgot_password.html", form=form)

        try:
            raw_token = user.issue_reset_token(hours=PASSWORD_RESET_HOURS)
            db.session.commit()
            reset_url = url_for(
                "reset_password", token=raw_token, _external=True
            )
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
            flash(
                "Non siamo riusciti a inviare l’email di recupero. Riprova tra poco.",
                "error",
            )
            return render_template("forgot_password.html", form=form)

        flash(generic_ok, "success")
        return redirect(url_for("login"))

    return render_template("forgot_password.html", form=form)


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    if session.get("user_id"):
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
        try:
            url = normalize_url(form.url.data)
            existing = SiteAnalysis.query.filter_by(user_id=user.id, url=url).first()
            site_count = SiteAnalysis.query.filter_by(user_id=user.id).count()
            max_sites = user.max_sites
            daily_limit = user.daily_limit
            if existing is None and site_count >= max_sites:
                flash(
                    f"Piano {user.plan_label}: massimo {max_sites} siti. "
                    "Riusa un URL già analizzato o passa a Plus.",
                    "warning",
                )
            elif not limiter.allow(
                f"analyze:{user.id}",
                limit=daily_limit,
                window_seconds=86400,
            ):
                flash(
                    f"Limite raggiunto: max {daily_limit} analisi ogni 24 ore "
                    f"(piano {user.plan_label}).",
                    "warning",
                )
            else:
                competitor_urls: list[str] = []
                raw_comp = (form.competitors.data or "").strip()
                if raw_comp and user.is_pro:
                    for line in re.split(r"[\n,;]+", raw_comp):
                        line = line.strip()
                        if line:
                            competitor_urls.append(line)
                if ASYNC_ANALYZE:
                    job = enqueue_analysis(
                        db.session,
                        AnalysisJob,
                        user_id=user.id,
                        url=url,
                        max_pages=user.crawl_pages,
                        competitor_urls=competitor_urls[:3],
                    )
                    kick_analyze_worker()
                    flash(
                        "Analisi in coda. Aggiorniamo lo stato automaticamente…",
                        "success",
                    )
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
                        run_measured=bool(
                            MEASURED_SOV_ON_ANALYZE and user.is_pro and OPENAI_API_KEY
                        ),
                        source="manual",
                    )
                    pages_n = int(latest.pages_analyzed or 1)
                    flash(
                        f"Analisi dominio completata su {pages_n} pagine: "
                        "score, findings e pack pronti.",
                        "success",
                    )
                except requests.Timeout:
                    flash("Timeout nel raggiungimento del sito. Riprova.", "error")
                except requests.RequestException:
                    flash(
                        "Impossibile raggiungere il sito. Verifica l’URL e riprova.",
                        "error",
                    )
                except Exception:
                    app.logger.exception("Dashboard analyze failed")
                    flash("Errore durante l’analisi. Riprova tra poco.", "error")
        except ValueError as exc:
            flash(str(exc), "error")

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
    if latest is not None:
        engine_breakdown = compute_engine_breakdown(
            aio_score=latest.aio_score,
            geo_score=latest.geo_score,
            findings=findings_all,
            robots_text=latest.robots_probed_text or "",
            competitors=latest.competitors,
        )
        measured = (latest.signals or {}).get("sov_measured")
        if isinstance(measured, dict):
            engine_breakdown = apply_measured_sov(engine_breakdown, measured)

    return render_template(
        "dashboard.html",
        form=form,
        schedule_form=schedule_form,
        latest=latest,
        run_diff=run_diff,
        engine_breakdown=engine_breakdown,
        openai_ready=bool(OPENAI_API_KEY),
        used_today=used_today,
        daily_limit=user.daily_limit,
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
        stripe_ready=stripe_enabled(),
    )


@app.route("/dashboard/jobs/<int:job_id>")
@login_required
def dashboard_job_status(job_id: int):
    user = current_user()
    job = AnalysisJob.query.filter_by(id=job_id, user_id=user.id).first()
    if job is None:
        return jsonify({"ok": False, "error": "not_found"}), 404
    return jsonify(
        {
            "ok": True,
            "id": job.id,
            "status": job.status,
            "url": job.url,
            "error": job.error,
            "site_id": job.site_id,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        }
    )


@app.route("/dashboard/guida")
@login_required
def dashboard_guide():
    return render_template("guide.html")


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
    leads = (
        ProInterest.query.order_by(ProInterest.created_at.desc()).limit(100).all()
    )
    users = User.query.order_by(User.created_at.desc()).limit(50).all()
    return render_template(
        "admin.html",
        leads=leads,
        users=users,
        lead_count=ProInterest.query.count(),
        user_count=User.query.count(),
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
    db.session.commit()
    flash(f"Piano di {target.email} aggiornato a {plan}.", "success")
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
    filename = f"geopulse-{analysis.domain.replace(':', '_')}.zip"
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
    filename = f"geopulse-{analysis.domain.replace(':', '_')}.zip"
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
    next_url = request.form.get("next") or request.args.get("next") or ""
    if next_url.startswith("/dashboard"):
        return redirect(next_url)
    return redirect(url_for("dashboard"))


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
    return render_template(
        "site_history.html",
        analysis=analysis,
        runs=runs,
        schedule_form=schedule_form,
        history_limit=PRO_HISTORY_LIMIT,
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
    filename = f"geopulse-{run.domain.replace(':', '_')}-{stamp}.zip"
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
        download_name=f"geopulse-storico-{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv",
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
        download_name=f"geopulse-siti-{datetime.now(timezone.utc).strftime('%Y%m%d')}.zip",
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
