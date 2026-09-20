"""
app/services/email_service.py

Batch A: a single send_email() function every future feature (OTP
verification in Batch B, and anything transactional later — password
reset emails, order notifications, etc.) calls, regardless of whether
real SMTP is configured yet.

Two modes, controlled by settings.EMAIL_MODE (see core/config.py):
  - "console" (default): nothing is actually sent. The email is
    logged to the server's console/log output in full, so anyone
    developing or testing against this system can see exactly what
    would have been sent — including the OTP code itself — without
    any mail server running. This is what ships until real SMTP
    credentials are added to .env.
  - "smtp": sends for real using smtplib against the configured host.

Switching from console to smtp is a one-line .env change
(EMAIL_MODE=smtp + the SMTP_* values) — no application code changes
anywhere else, since every caller only ever sees send_email().
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger("minerals_chain.email")


class EmailSendError(RuntimeError):
    """Raised when EMAIL_MODE=smtp and the send genuinely fails (bad
    credentials, host unreachable, etc). Never raised in console mode."""
    pass


def send_email(*, to: str, subject: str, body: str) -> None:
    if settings.EMAIL_MODE == "smtp":
        _send_via_smtp(to=to, subject=subject, body=body)
    else:
        _send_via_console(to=to, subject=subject, body=body)


def _send_via_console(*, to: str, subject: str, body: str) -> None:
    logger.info(
        "\n"
        "===== EMAIL (console mode — nothing actually sent) =====\n"
        f"To:      {to}\n"
        f"Subject: {subject}\n"
        f"Body:\n{body}\n"
        "=========================================================="
    )


def _send_via_smtp(*, to: str, subject: str, body: str) -> None:
    if not settings.SMTP_HOST or not settings.SMTP_USERNAME:
        raise EmailSendError(
            "EMAIL_MODE is set to 'smtp' but SMTP_HOST/SMTP_USERNAME are not configured in .env."
        )

    message = MIMEMultipart()
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    message["To"] = to
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, [to], message.as_string())
    except (smtplib.SMTPException, OSError) as exc:
        raise EmailSendError(f"Failed to send email to {to}: {exc}") from exc
