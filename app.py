"""
AIO-Bot — SaaS iniziale per ottimizzazione GEO/AIO dei siti web.
Analisi score + findings + generazione pack artifact (llms.txt, JSON-LD, meta, robots).
"""

from __future__ import annotations

import io
import json
import os
import zipfile
from datetime import datetime, timezone
from functools import wraps
from typing import Any
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
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
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import PasswordField, StringField, SubmitField, URLField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError

from services.analyzer import analyze_site, normalize_url
from services.artifacts import build_optimization_pack

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


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
app.config["WTF_CSRF_TIME_LIMIT"] = 3600
app.config["INSTANCE_RELATIVE_CONFIG"] = False

db = SQLAlchemy(app)
csrf = CSRFProtect(app)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
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


class RegisterForm(FlaskForm):
    name = StringField("Nome", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField(
        "Email",
        validators=[
            DataRequired(),
            Email(message="Email non valida.", check_deliverability=False),
            Length(max=255),
        ],
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


def validate_http_url(_form: FlaskForm, field: URLField) -> None:
    value = (field.data or "").strip()
    parsed = urlparse(value if "://" in value else f"https://{value}")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError("Inserisci un URL http(s) valido.")


class AnalyzeForm(FlaskForm):
    url = URLField(
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
    }


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------


def ensure_schema() -> None:
    """create_all + colonne nuove su SQLite già esistente."""
    db.create_all()
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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if User.query.filter_by(email=email).first():
            flash("Questa email è già registrata.", "error")
        else:
            user = User(email=email, name=form.name.data.strip())
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
    latest: SiteAnalysis | None = (
        SiteAnalysis.query.filter_by(user_id=user.id)
        .order_by(SiteAnalysis.created_at.desc())
        .first()
    )

    if form.validate_on_submit():
        try:
            url = normalize_url(form.url.data)
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

            analysis = SiteAnalysis.query.filter_by(user_id=user.id, url=url).first()
            if analysis is None:
                analysis = SiteAnalysis(user_id=user.id, url=url, domain=domain)
                db.session.add(analysis)

            analysis.domain = domain
            analysis.page_title = (scraped.get("title") or "")[:500] or None
            analysis.aio_score = result["aio_score"]
            analysis.geo_score = result["geo_score"]
            analysis.findings_json = json.dumps(result["findings"], ensure_ascii=False)
            analysis.analysis_notes = result["notes"]
            analysis.llms_txt = pack["llms.txt"]
            analysis.json_ld_artifact = pack["organization.jsonld.html"]
            analysis.meta_pack_artifact = pack["meta-pack.html"]
            analysis.robots_artifact = pack["robots.txt"]
            analysis.created_at = datetime.now(timezone.utc)
            db.session.commit()
            latest = analysis
            flash("Analisi completata: score, findings e pack pronti.", "success")
        except requests.RequestException:
            flash(
                "Impossibile raggiungere il sito. Verifica l’URL e riprova.",
                "error",
            )
        except ValueError as exc:
            flash(str(exc), "error")
        except Exception:
            app.logger.exception("Dashboard analyze failed")
            flash("Errore durante l’analisi. Riprova tra poco.", "error")

    history = (
        SiteAnalysis.query.filter_by(user_id=user.id)
        .order_by(SiteAnalysis.created_at.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "dashboard.html",
        form=form,
        latest=latest,
        history=history,
        openai_ready=bool(OPENAI_API_KEY),
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
