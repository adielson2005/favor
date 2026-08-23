"""Real email delivery via SMTP (Python stdlib smtplib — no new dependency). Activates
the moment SMTP_HOST/SMTP_USER/SMTP_PASSWORD are set in the environment; until then,
send_email returns False and callers fall back to the existing dev-mode behavior (the
code returned directly in the API response) — the same pattern this app has always
used for email before any provider was configured.
"""
import logging
import os
import smtplib
import ssl
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def email_delivery_configured() -> bool:
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER") and os.environ.get("SMTP_PASSWORD"))


def send_email(to: str, subject: str, body: str) -> bool:
    if not email_delivery_configured():
        return False
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    sender = os.environ.get("SMTP_FROM", user)

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls(context=context)
            server.login(user, password)
            server.sendmail(sender, [to], msg.as_string())
        return True
    except Exception:
        logger.exception("Falha ao enviar e-mail via SMTP para %s", to)
        return False
