"""
AIO-Bot — SaaS iniziale per ottimizzazione GEO/AIO dei siti web.
Analisi score + findings + generazione pack artifact (llms.txt, JSON-LD, meta, robots).
"""

from __future__ import annotations

import io
import json
import logging
import os
import zipfile
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
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
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TelField,
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

from services.analyzer import analyze_site, normalize_url
from services.artifacts import build_optimization_pack
from services.rate_limit import limiter

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FREE_DAILY_ANALYSES = max(1, int(os.getenv("FREE_DAILY_ANALYSES", "10")))
MAX_SITES_FREE = max(1, int(os.getenv("MAX_SITES_FREE", "5")))


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
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
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
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    sites = db.relationship("SiteAnalysis", back_populates="user", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


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
    meta_pack_artifact = db.Column(db.Text, nullable=False, default="")
    robots_artifact = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship("User", back_populates="sites")

    @property
    def findings(self) -> list[dict[str, str]]:
        try:
            data = json.loads(self.findings_json or "[]")
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []


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
    submit = SubmitField("Analizza e ottimizza")


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


def current_user() -> User | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


@app.context_processor
def inject_globals() -> dict[str, Any]:
    return {
        "current_user": current_user(),
        "csrf_token": generate_csrf,
        "max_sites_free": MAX_SITES_FREE,
        "free_daily_analyses": FREE_DAILY_ANALYSES,
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
    if "site_analyses" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("site_analyses")}
    alters = {
        "aio_score": "INTEGER",
        "geo_score": "INTEGER",
        "findings_json": "TEXT DEFAULT '[]'",
        "analysis_notes": "TEXT",
        "json_ld_artifact": "TEXT DEFAULT ''",
        "meta_pack_artifact": "TEXT DEFAULT ''",
        "robots_artifact": "TEXT DEFAULT ''",
    }
    with db.engine.begin() as conn:
        for name, col_type in alters.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE site_analyses ADD COLUMN {name} {col_type}"))

    if "users" in inspector.get_table_names():
        user_cols = {col["name"] for col in inspector.get_columns("users")}
        user_alters = {
            "company": "TEXT",
            "website_url": "TEXT",
            "phone": "TEXT",
            "role": "TEXT",
            "country": "TEXT",
        }
        with db.engine.begin() as conn:
            for name, col_type in user_alters.items():
                if name not in user_cols:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {col_type}"))


def client_ip() -> str:
    return (request.headers.get("X-Real-IP") or request.remote_addr or "unknown").strip()


def analyses_today(user_id: int) -> int:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        SiteAnalysis.query.filter(
            SiteAnalysis.user_id == user_id,
            SiteAnalysis.created_at >= start,
        ).count()
    )


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
                "service": "aio-bot",
                "openai": bool(OPENAI_API_KEY),
                "time": datetime.now(timezone.utc).isoformat(),
            }
        ),
        status,
    )


@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("landing.html")


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
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            session.clear()
            session["user_id"] = user.id
            session.permanent = True
            flash("Account creato. Benvenuto su AIO-Bot.", "success")
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
            if existing is None and site_count >= MAX_SITES_FREE:
                flash(
                    f"Piano Free: massimo {MAX_SITES_FREE} siti. "
                    "Riusa un URL già analizzato.",
                    "warning",
                )
            elif not limiter.allow(
                f"analyze:{user.id}",
                limit=FREE_DAILY_ANALYSES,
                window_seconds=86400,
            ):
                flash(
                    f"Limite raggiunto: max {FREE_DAILY_ANALYSES} analisi ogni 24 ore.",
                    "warning",
                )
            else:
                try:
                    result = analyze_site(url)
                    scraped = result["scraped"]
                    pack = build_optimization_pack(
                        url,
                        scraped,
                        api_key=OPENAI_API_KEY,
                        model=OPENAI_MODEL,
                        logger=app.logger,
                    )
                    domain = scraped.get("domain") or urlparse(url).netloc

                    analysis = existing
                    if analysis is None:
                        analysis = SiteAnalysis(
                            user_id=user.id, url=url, domain=domain
                        )
                        db.session.add(analysis)

                    analysis.domain = domain
                    analysis.page_title = (scraped.get("title") or "")[:500] or None
                    analysis.aio_score = result["aio_score"]
                    analysis.geo_score = result["geo_score"]
                    analysis.findings_json = json.dumps(
                        result["findings"], ensure_ascii=False
                    )
                    analysis.analysis_notes = result["notes"]
                    analysis.llms_txt = pack["llms.txt"]
                    analysis.json_ld_artifact = pack["organization.jsonld.html"]
                    analysis.meta_pack_artifact = pack["meta-pack.html"]
                    analysis.robots_artifact = pack["robots.txt"]
                    analysis.created_at = datetime.now(timezone.utc)
                    db.session.commit()
                    latest = analysis
                    flash(
                        "Analisi completata: score, findings e pack pronti.",
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

    history = (
        SiteAnalysis.query.filter_by(user_id=user.id)
        .order_by(SiteAnalysis.created_at.desc())
        .limit(10)
        .all()
    )
    used_today = analyses_today(user.id)
    return render_template(
        "dashboard.html",
        form=form,
        latest=latest,
        history=history,
        openai_ready=bool(OPENAI_API_KEY),
        used_today=used_today,
        daily_limit=FREE_DAILY_ANALYSES,
        max_sites=MAX_SITES_FREE,
        site_count=SiteAnalysis.query.filter_by(user_id=user.id).count(),
    )


@app.route("/dashboard/download/<int:analysis_id>.zip")
@login_required
def download_pack(analysis_id: int):
    user = current_user()
    analysis = SiteAnalysis.query.filter_by(id=analysis_id, user_id=user.id).first()
    if analysis is None:
        flash("Analisi non trovata.", "error")
        return redirect(url_for("dashboard"))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("llms.txt", analysis.llms_txt or "")
        zf.writestr("organization.jsonld.html", analysis.json_ld_artifact or "")
        zf.writestr("meta-pack.html", analysis.meta_pack_artifact or "")
        zf.writestr("robots.txt", analysis.robots_artifact or "")
        report = {
            "url": analysis.url,
            "domain": analysis.domain,
            "aio_score": analysis.aio_score,
            "geo_score": analysis.geo_score,
            "findings": analysis.findings,
            "notes": analysis.analysis_notes,
            "generated_at": (
                analysis.created_at.isoformat() if analysis.created_at else None
            ),
        }
        zf.writestr(
            "report.json",
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        )
    buffer.seek(0)
    filename = f"aio-bot-{analysis.domain.replace(':', '_')}.zip"
    return send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
    )


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


with app.app_context():
    ensure_schema()


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=debug)
