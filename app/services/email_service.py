"""
app/services/email_service.py
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger("minerals_chain.email")


class EmailSendError(RuntimeError):
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
