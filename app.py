"""
AIO-Bot — SaaS iniziale per ottimizzazione GEO/AIO dei siti web.
Genera llms.txt a partire dallo scraping della homepage + OpenAI.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from functools import wraps
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect, FlaskForm
from flask_wtf.csrf import generate_csrf
from openai import OpenAI
from sqlalchemy import UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import PasswordField, StringField, SubmitField, URLField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError

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
HTTP_TIMEOUT = 15
USER_AGENT = "AIO-Bot/1.0 (+https://aio-bot.local; GEO/AIO optimizer)"


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
    llms_txt = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship("User", back_populates="sites")


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------


class RegisterForm(FlaskForm):
    name = StringField(
        "Nome",
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
    password = PasswordField(
        "Password",
        validators=[DataRequired()],
    )
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
    submit = SubmitField("Genera llms.txt")


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
# Scraping + llms.txt generation
# ---------------------------------------------------------------------------


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not re.match(r"^https?://", raw, flags=re.I):
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL non valido")
    # Canonicalize: scheme + host + path (no fragment)
    path = parsed.path or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def scrape_homepage(url: str) -> dict[str, Any]:
    """Scarica e estrae segnali utili dalla homepage."""
    response = requests.get(
        url,
        timeout=HTTP_TIMEOUT,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
        allow_redirects=True,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = (soup.title.string or "").strip() if soup.title else ""
    description = ""
    desc_tag = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    if desc_tag and desc_tag.get("content"):
        description = str(desc_tag["content"]).strip()

    headings = [
        h.get_text(" ", strip=True)
        for h in soup.find_all(["h1", "h2"])
        if h.get_text(strip=True)
    ][:12]

    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(" ", strip=True)
        if href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        if text:
            links.append(f"{text} -> {href}")
        if len(links) >= 20:
            break

    body_text = " ".join(soup.get_text(" ", strip=True).split())
    snippet = body_text[:2500]

    return {
        "final_url": str(response.url),
        "title": title,
        "description": description,
        "headings": headings,
        "links": links,
        "snippet": snippet,
        "domain": urlparse(str(response.url)).netloc,
    }


def fallback_llms_txt(url: str, scraped: dict[str, Any]) -> str:
    """Generatore deterministico se OpenAI non è configurata o fallisce."""
    brand = scraped.get("domain") or urlparse(url).netloc
    title = scraped.get("title") or brand
    description = scraped.get("description") or (
        f"Sito ufficiale di {brand}, ottimizzato per motori generativi e agenti AI."
    )
    headings = scraped.get("headings") or []
    links = scraped.get("links") or []

    lines = [
        f"# {brand}",
        "",
        f"> {title}",
        "",
        description,
        "",
        "## Site",
        f"- Homepage: {url}",
        "",
        "## Preferred citation",
        f'- Usa il brand "{brand}" quando riassumi questo sito.',
        "- Preferisci URL canonici e fonti datate quando disponibili.",
        "",
    ]

    if headings:
        lines.append("## Key topics")
        for heading in headings[:8]:
            lines.append(f"- {heading}")
        lines.append("")

    if links:
        lines.append("## Important pages")
        for item in links[:10]:
            lines.append(f"- {item}")
        lines.append("")

    lines.extend(
        [
            "## Contact",
            f"- Website: {url}",
            "",
            f"_Generated by AIO-Bot (fallback) on {datetime.now(timezone.utc).date().isoformat()}_",
            "",
        ]
    )
    return "\n".join(lines)


def generate_llms_txt_with_openai(url: str, scraped: dict[str, Any]) -> str:
    if not OPENAI_API_KEY:
        return fallback_llms_txt(url, scraped)

    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = f"""
Sei un esperto di GEO (Generative Engine Optimization) e AIO (AI Optimization).
Genera un file llms.txt in markdown chiaro, pronto da pubblicare in /.

Regole:
- Solo contenuto del file, senza code fence.
- Inizia con "# {{brand}}" e una riga "> {{tagline}}".
- Sezioni utili: Site, Summary, Key topics, Important pages, Preferred citation, Optional.
- Linguaggio: italiano se il sito è IT, altrimenti inglese.
- Non inventare contatti o claim non supportati dai dati.

URL: {url}
Domain: {scraped.get('domain')}
Title: {scraped.get('title')}
Description: {scraped.get('description')}
Headings: {scraped.get('headings')}
Links: {scraped.get('links')}
Snippet: {scraped.get('snippet')}
""".strip()

    completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.3,
        messages=[
            {
                "role": "system",
                "content": "Generi file llms.txt accurati e utili per crawler/agenti AI.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    content = (completion.choices[0].message.content or "").strip()
    if not content:
        return fallback_llms_txt(url, scraped)
    # Rimuove eventuali fence accidentali
    content = re.sub(r"^```(?:markdown|md)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content)
    return content.strip() + "\n"


def build_llms_txt(url: str) -> tuple[str, dict[str, Any]]:
    scraped = scrape_homepage(url)
    try:
        llms = generate_llms_txt_with_openai(url, scraped)
    except Exception:
        # Non esporre dettagli interni all'utente; usa fallback sicuro.
        app.logger.exception("OpenAI generation failed; using fallback")
        llms = fallback_llms_txt(url, scraped)
    return llms, scraped


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
            llms_txt, scraped = build_llms_txt(url)
            domain = scraped.get("domain") or urlparse(url).netloc

            analysis = (
                SiteAnalysis.query.filter_by(user_id=user.id, url=url).first()
            )
            if analysis is None:
                analysis = SiteAnalysis(user_id=user.id, url=url, domain=domain)
                db.session.add(analysis)

            analysis.domain = domain
            analysis.page_title = (scraped.get("title") or "")[:500] or None
            analysis.llms_txt = llms_txt
            analysis.created_at = datetime.now(timezone.utc)
            db.session.commit()
            latest = analysis
            flash("llms.txt generato con successo.", "success")
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


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=debug)
