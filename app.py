"""
GeoPulse (geopulse.it) — SaaS per ottimizzazione GEO/AIO dei siti web.
Analisi score + findings + generazione pack artifact (llms.txt, JSON-LD, meta, robots).
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
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
    persist_analysis,
)
from services.analyzer import analyze_site, normalize_url
from services.artifacts import build_optimization_pack
from services.export import multi_site_zip, pack_zip_bytes, runs_to_csv
from services.rate_limit import limiter
from services.rating import RATING_ORDER, compute_rating
from services.deep_checks import analyze_monitoring_alerts
from services.signals import compare_with_previous

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FREE_DAILY_ANALYSES = max(1, int(os.getenv("FREE_DAILY_ANALYSES", "10")))
MAX_SITES_FREE = max(1, int(os.getenv("MAX_SITES_FREE", "5")))
PRO_DAILY_ANALYSES = max(FREE_DAILY_ANALYSES, int(os.getenv("PRO_DAILY_ANALYSES", "200")))
MAX_SITES_PRO = max(MAX_SITES_FREE, int(os.getenv("MAX_SITES_PRO", "50")))
FREE_CRAWL_PAGES = max(1, min(20, int(os.getenv("FREE_CRAWL_PAGES", "8"))))
PRO_CRAWL_PAGES = max(FREE_CRAWL_PAGES, min(50, int(os.getenv("PRO_CRAWL_PAGES", "30"))))
FREE_HISTORY_LIMIT = max(5, int(os.getenv("FREE_HISTORY_LIMIT", "10")))
PRO_HISTORY_LIMIT = max(FREE_HISTORY_LIMIT, int(os.getenv("PRO_HISTORY_LIMIT", "100")))
ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL") or "admin@geopulse.it").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") or "GeoPulse!Admin26"
ADMIN_NAME = os.getenv("ADMIN_NAME") or "Admin GeoPulse"


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
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["X-XSS-Protection"] = "0"
    # CSP permissiva per Tailwind CDN; stringente su object/base
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
    plan = db.Column(db.String(40), nullable=False, default="free")  # free|pro|admin
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    sites = db.relationship("SiteAnalysis", back_populates="user", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return (self.plan or "").lower() == "admin" or (self.role or "") == "admin"

    @property
    def is_pro(self) -> bool:
        return self.is_admin or (self.plan or "").lower() == "pro"

    @property
    def plan_label(self) -> str:
        if self.is_admin:
            return "Admin"
        if self.is_pro:
            return "Pro"
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
    def rating(self) -> dict[str, Any]:
        return compute_rating(self.aio_score, self.geo_score, self.findings)

    @property
    def rescan_active(self) -> bool:
        return (self.rescan_interval or "off").lower() in {"daily", "weekly"}


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
        "Cosa ti serve da Pro",
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
                "Funzione Pro: attiva il piano Pro per re-scan, export e storico avanzato.",
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


def ensure_admin_user() -> User:
    """Crea o aggiorna l’utente admin di prova (piano Pro)."""
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
    else:
        user.name = ADMIN_NAME
        user.company = user.company or "GeoPulse"
        user.website_url = user.website_url or "https://geopulse.it/"
        user.role = "admin"
        user.plan = "admin"
        user.set_password(ADMIN_PASSWORD)
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
        "now_year": datetime.now(timezone.utc).year,
        "rating_scale": RATING_ORDER,
        "canonical_base": base,
        "canonical_url": canonical,
        "admin_email": ADMIN_EMAIL,
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
        with db.engine.begin() as conn:
            for name, col_type in alters.items():
                if name not in existing:
                    conn.execute(
                        text(f"ALTER TABLE site_analyses ADD COLUMN {name} {col_type}")
                    )

    if "users" in tables:
        user_cols = {col["name"] for col in inspector.get_columns("users")}
        user_alters = {
            "company": "TEXT",
            "website_url": "TEXT",
            "phone": "TEXT",
            "role": "TEXT",
            "country": "TEXT",
            "plan": "TEXT DEFAULT 'free'",
        }
        with db.engine.begin() as conn:
            for name, col_type in user_alters.items():
                if name not in user_cols:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {col_type}"))

    if "analysis_runs" in tables:
        run_cols = {col["name"] for col in inspector.get_columns("analysis_runs")}
        run_alters = {
            "pages_analyzed": "INTEGER DEFAULT 1",
            "crawl_pages_json": "TEXT DEFAULT '[]'",
            "faq_artifact": "TEXT DEFAULT ''",
            "checklist_artifact": "TEXT DEFAULT ''",
            "before_after_artifact": "TEXT DEFAULT ''",
        }
        with db.engine.begin() as conn:
            for name, col_type in run_alters.items():
                if name not in run_cols:
                    conn.execute(
                        text(f"ALTER TABLE analysis_runs ADD COLUMN {name} {col_type}")
                    )

    backfill_analysis_runs()


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


@app.route("/robots.txt")
def robots_txt():
    base = public_base_url()
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /dashboard\n"
        "Disallow: /dashboard/\n"
        "Disallow: /logout\n"
        "\n"
        "User-agent: GPTBot\n"
        "Allow: /\n"
        "\n"
        "User-agent: ClaudeBot\n"
        "Allow: /\n"
        "\n"
        "User-agent: PerplexityBot\n"
        "Allow: /\n"
        "\n"
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
        ("/faq", "0.7", "monthly"),
        ("/interesse-pro", "0.6", "monthly"),
        ("/register", "0.6", "monthly"),
        ("/login", "0.4", "monthly"),
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


@app.route("/")
def index():
    return render_template("landing.html")


@app.route("/prodotto")
def product():
    return render_template("product.html")


@app.route("/prezzi")
def pricing():
    return render_template("pricing.html")


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
            "Interesse Pro registrato. Ti contatteremo a "
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
            flash("Questa email è già registrata.", "error")
        else:
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
                    "Riusa un URL già analizzato o passa a Pro.",
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
                try:
                    previous_run = None
                    if existing is not None:
                        previous_run = (
                            AnalysisRun.query.filter_by(
                                site_id=existing.id, user_id=user.id
                            )
                            .order_by(AnalysisRun.created_at.desc())
                            .first()
                        )
                    competitor_urls = []
                    raw_comp = (form.competitors.data or "").strip()
                    if raw_comp:
                        for line in re.split(r"[\n,;]+", raw_comp):
                            line = line.strip()
                            if line:
                                competitor_urls.append(line)
                    result = analyze_site(
                        url,
                        max_pages=user.crawl_pages,
                        competitor_urls=competitor_urls[:3] if user.is_pro else [],
                    )
                    run_diff = compare_with_previous(
                        aio_score=result.get("aio_score"),
                        geo_score=result.get("geo_score"),
                        findings=result.get("findings"),
                        previous=previous_run,
                    )
                    if run_diff.get("findings"):
                        result["findings"] = list(result.get("findings") or []) + list(
                            run_diff["findings"]
                        )
                    result["diff"] = run_diff
                    rating_now = compute_rating(
                        result.get("aio_score"),
                        result.get("geo_score"),
                        result.get("findings"),
                    )
                    alerts = analyze_monitoring_alerts(
                        probes=result.get("probes") or {},
                        rating=rating_now,
                        previous=previous_run,
                        diff=run_diff,
                    )
                    if alerts.get("findings"):
                        result["findings"] = list(result.get("findings") or []) + list(
                            alerts["findings"]
                        )
                    pack = build_optimization_pack(
                        url,
                        result["scraped"],
                        api_key=OPENAI_API_KEY,
                        model=OPENAI_MODEL,
                        logger=app.logger,
                        findings=result.get("findings"),
                        previous=previous_run,
                        diff=run_diff,
                        result=result,
                    )
                    latest = persist_analysis(
                        db.session,
                        SiteAnalysis=SiteAnalysis,
                        AnalysisRun=AnalysisRun,
                        user_id=user.id,
                        url=url,
                        result=result,
                        pack=pack,
                        existing=existing,
                        source="manual",
                    )
                    pages_n = result.get("pages_analyzed") or 1
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
            # Diff già incorporato nei findings dell’ultima run se presente
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

    return render_template(
        "dashboard.html",
        form=form,
        schedule_form=schedule_form,
        latest=latest,
        history=history,
        run_diff=run_diff,
        openai_ready=bool(OPENAI_API_KEY),
        used_today=used_today,
        daily_limit=user.daily_limit,
        max_sites=user.max_sites,
        crawl_pages_limit=user.crawl_pages,
        site_count=SiteAnalysis.query.filter_by(user_id=user.id).count(),
        user_plan=user.plan_label,
        is_pro=user.is_pro,
        history_limit=hist_limit,
        history_is_runs=user.is_pro,
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
    if plan not in {"free", "pro", "admin"}:
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
