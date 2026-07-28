"""Invio email: Resend API oppure SMTP."""

from __future__ import annotations

import base64
import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Any

import requests

logger = logging.getLogger(__name__)


def mail_configured() -> bool:
    if (os.getenv("RESEND_API_KEY") or "").strip():
        return True
    host = (os.getenv("SMTP_HOST") or "").strip()
    return bool(host)


def mail_from_address() -> str:
    return (
        (os.getenv("MAIL_FROM") or "").strip()
        or (os.getenv("SMTP_FROM") or "").strip()
        or (os.getenv("ADMIN_EMAIL") or "noreply@centropic.ai").strip()
    )


def send_email(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> dict[str, Any]:
    """Invia email senza allegato (Resend o SMTP)."""
    to_email = (to_email or "").strip()
    if not to_email or "@" not in to_email:
        raise ValueError("Indirizzo email destinatario non valido.")
    if not mail_configured():
        raise RuntimeError(
            "Invio email non configurato. Imposta RESEND_API_KEY oppure SMTP_HOST."
        )

    if (os.getenv("RESEND_API_KEY") or "").strip():
        return _send_plain_via_resend(
            to_email=to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )
    return _send_plain_via_smtp(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def _send_plain_via_resend(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None,
) -> dict[str, Any]:
    api_key = (os.getenv("RESEND_API_KEY") or "").strip()
    payload: dict[str, Any] = {
        "from": mail_from_address(),
        "to": [to_email],
        "subject": subject,
        "text": text_body,
    }
    if html_body:
        payload["html"] = html_body

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=45,
    )
    if response.status_code >= 400:
        detail = response.text[:300]
        logger.error("Resend send failed status=%s body=%s", response.status_code, detail)
        raise RuntimeError(f"Invio email fallito (Resend {response.status_code}).")
    data = response.json() if response.content else {}
    return {"provider": "resend", "id": data.get("id"), "to": to_email}


def _send_plain_via_smtp(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None,
) -> dict[str, Any]:
    host = (os.getenv("SMTP_HOST") or "").strip()
    port = int(os.getenv("SMTP_PORT") or "587")
    user = (os.getenv("SMTP_USER") or "").strip()
    password = os.getenv("SMTP_PASSWORD") or ""
    use_ssl = (os.getenv("SMTP_SSL") or "0").strip() == "1"
    use_starttls = (os.getenv("SMTP_STARTTLS") or "1").strip() != "0"
    from_addr = mail_from_address()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=45) as smtp:
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=45) as smtp:
            smtp.ehlo()
            if use_starttls:
                smtp.starttls()
                smtp.ehlo()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)

    return {"provider": "smtp", "to": to_email, "host": host}


def build_password_reset_email(
    *,
    user_name: str,
    reset_url: str,
    expires_hours: int = 2,
) -> tuple[str, str, str]:
    first = (user_name or "ciao").strip().split(" ")[0] or "ciao"
    subject = "Centropic — recupero password"
    text = (
        f"Ciao {first},\n\n"
        "hai richiesto il reset della password Centropic.\n"
        f"Apri questo link entro {expires_hours} ore:\n\n"
        f"{reset_url}\n\n"
        "Se non hai richiesto tu il reset, ignora questa email.\n\n"
        "— Centropic (centropic.ai)\n"
    )
    html = (
        f"<p>Ciao {first},</p>"
        "<p>hai richiesto il reset della password Centropic.</p>"
        f"<p><a href=\"{reset_url}\">Imposta una nuova password</a> "
        f"(valido {expires_hours} ore).</p>"
        "<p>Se non hai richiesto tu il reset, ignora questa email.</p>"
        "<p>— Centropic · <a href=\"https://centropic.ai\">centropic.ai</a></p>"
    )
    return subject, text, html


def send_email_with_attachment(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    attachment_filename: str,
    attachment_bytes: bytes,
    attachment_mime: str = "application/zip",
) -> dict[str, Any]:
    """
    Invia email con allegato.
    Preferisce Resend se RESEND_API_KEY è impostata, altrimenti SMTP_*.
    """
    to_email = (to_email or "").strip()
    if not to_email or "@" not in to_email:
        raise ValueError("Indirizzo email destinatario non valido.")
    if not mail_configured():
        raise RuntimeError(
            "Invio email non configurato. Imposta RESEND_API_KEY oppure SMTP_HOST."
        )

    if (os.getenv("RESEND_API_KEY") or "").strip():
        return _send_via_resend(
            to_email=to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            attachment_filename=attachment_filename,
            attachment_bytes=attachment_bytes,
            attachment_mime=attachment_mime,
        )
    return _send_via_smtp(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        attachment_filename=attachment_filename,
        attachment_bytes=attachment_bytes,
        attachment_mime=attachment_mime,
    )


def _send_via_resend(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None,
    attachment_filename: str,
    attachment_bytes: bytes,
    attachment_mime: str,
) -> dict[str, Any]:
    api_key = (os.getenv("RESEND_API_KEY") or "").strip()
    payload: dict[str, Any] = {
        "from": mail_from_address(),
        "to": [to_email],
        "subject": subject,
        "text": text_body,
        "attachments": [
            {
                "filename": attachment_filename,
                "content": base64.b64encode(attachment_bytes).decode("ascii"),
                "content_type": attachment_mime,
            }
        ],
    }
    if html_body:
        payload["html"] = html_body

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=45,
    )
    if response.status_code >= 400:
        detail = response.text[:300]
        logger.error("Resend send failed status=%s body=%s", response.status_code, detail)
        raise RuntimeError(f"Invio email fallito (Resend {response.status_code}).")
    data = response.json() if response.content else {}
    return {"provider": "resend", "id": data.get("id"), "to": to_email}


def _send_via_smtp(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None,
    attachment_filename: str,
    attachment_bytes: bytes,
    attachment_mime: str,
) -> dict[str, Any]:
    host = (os.getenv("SMTP_HOST") or "").strip()
    port = int(os.getenv("SMTP_PORT") or "587")
    user = (os.getenv("SMTP_USER") or "").strip()
    password = os.getenv("SMTP_PASSWORD") or ""
    use_ssl = (os.getenv("SMTP_SSL") or "0").strip() == "1"
    use_starttls = (os.getenv("SMTP_STARTTLS") or "1").strip() != "0"
    from_addr = mail_from_address()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    maintype, _, subtype = attachment_mime.partition("/")
    msg.add_attachment(
        attachment_bytes,
        maintype=maintype or "application",
        subtype=subtype or "zip",
        filename=attachment_filename,
    )

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=45) as smtp:
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=45) as smtp:
            smtp.ehlo()
            if use_starttls:
                smtp.starttls()
                smtp.ehlo()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)

    return {"provider": "smtp", "to": to_email, "host": host}


def build_pack_email(
    *,
    user_name: str,
    domain: str,
    aio_score: int | None,
    geo_score: int | None,
) -> tuple[str, str, str]:
    """Ritorna subject, text, html per il pack."""
    first = (user_name or "ciao").strip().split(" ")[0] or "ciao"
    aio = "—" if aio_score is None else str(aio_score)
    geo = "—" if geo_score is None else str(geo_score)
    subject = f"Centropic — pack ottimizzazione {domain}"
    text = (
        f"Ciao {first},\n\n"
        f"in allegato il pack di ottimizzazione GEO/AIO per {domain}.\n"
        f"Score: AIO {aio} · GEO {geo}.\n\n"
        "Contiene llms.txt, JSON-LD, meta pack, robots e checklist.\n"
        "Apri lo ZIP e applica gli artifact sul sito.\n\n"
        "— Centropic (centropic.ai)\n"
    )
    html = (
        f"<p>Ciao {first},</p>"
        f"<p>in allegato il pack di ottimizzazione GEO/AIO per "
        f"<strong>{domain}</strong>.</p>"
        f"<p>Score: AIO {aio} · GEO {geo}.</p>"
        "<p>Contiene <code>llms.txt</code>, JSON-LD, meta pack, robots e checklist. "
        "Apri lo ZIP e applica gli artifact sul sito.</p>"
        "<p>— Centropic · <a href=\"https://centropic.ai\">centropic.ai</a></p>"
    )
    return subject, text, html
