"""Digest email delivery. Uses SMTP when configured; otherwise logs the rendered email to
the console so the scheduled job is always runnable/demoable without real mail credentials.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from fastapi.templating import Jinja2Templates

from app.config import settings

logger = logging.getLogger(__name__)

_templates = Jinja2Templates(directory="app/templates")


def render_digest(user, rec, products, activity_recap: str, base_url: str = "") -> str:
    template = _templates.get_template("emails/digest_email.html")
    return template.render(
        user=user, rec=rec, products=products, activity_recap=activity_recap, base_url=base_url
    )


def send_digest_email(user, rec, products, activity_recap: str, base_url: str = "") -> bool:
    """Render + send the digest. Returns True if sent via SMTP, False if logged to console."""
    html = render_digest(user, rec, products, activity_recap, base_url)
    subject = "Your SmartReco picks for today"

    if not settings.smtp_host:
        logger.info(
            "[email:console-fallback] To: %s | Subject: %s\n%s",
            user.email,
            subject,
            html,
        )
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = user.email
    msg.set_content("Your personalized SmartReco picks are ready. View this email in HTML.")
    msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password or "")
            server.send_message(msg)
        logger.info("Digest email sent to %s", user.email)
        return True
    except Exception:
        logger.exception("SMTP send failed for %s; falling back to console log", user.email)
        logger.info("[email:console-fallback] To: %s | Subject: %s\n%s", user.email, subject, html)
        return False
