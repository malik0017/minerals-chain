"""
app/services/security_posture.py
"""
import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import rate_limit
from app.core.config import settings
from app.core.system_settings import get_setting, set_setting
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
from app.services import document_upload_service

LEVEL_ORDER = {"fail": 0, "warn": 1, "info": 2, "ok": 3}
TOGGLES = {
    "enforce_admin_2fa": ("setting", "enforce_admin_2fa", True),
    "email_otp": ("platform", "require_email_otp", True),
    "impersonation": ("setting", "allow_impersonation", False),
    "dev_banner": ("setting", "dev_mode_banner", False),
}


def _item(key, level, title, detail, fix="", kind="none", env=None, toggle=None, link=None):
    return {"key": key, "level": level, "title": title, "detail": detail, "fix": fix, "kind": kind,
            "env": env or {}, "toggle": toggle, "link": link}


def _extra_items(db: Session) -> list[dict]:
    items = []
    try:
        from app.services import file_crypto
        items.append(file_crypto.checklist_item(db))
    except ImportError:
        pass
    try:
        from app.services import backup_service
        items.append(backup_service.checklist_item(db))
    except ImportError:
        pass
    try:
        from app.core import security_headers
        if hasattr(security_headers, "checklist_item"):
            items.append(security_headers.checklist_item())
    except ImportError:
        pass
    return items


def checklist(db: Session) -> list[dict]:
    from app.repositories import platform_settings_repository
    ps = platform_settings_repository.get_settings(db)
    admins_no_2fa = db.scalar(select(func.count()).select_from(User).where(
        User.role == UserRole.ADMIN, User.totp_enabled.is_(False), User.is_active.is_(True)))
    legacy_docs = document_upload_service.legacy_public_document_count()
    enforce_2fa = bool(get_setting(db, "enforce_admin_2fa"))
    rl = rate_limit.backend()
    default_key = settings.SECRET_KEY.startswith("CHANGE_ME") or len(settings.SECRET_KEY) < 32
    smtp_ready = settings.EMAIL_MODE == "smtp" and bool(settings.SMTP_HOST and settings.SMTP_USERNAME)

    items = [
        _item("secret_key", "fail" if default_key else "ok", "Session signing key (SECRET_KEY)",
              "Default or short key — sessions can be forged." if default_key else "Strong custom key configured.",
              "Generate a random 64-byte key.", "env", {"SECRET_KEY": secrets.token_urlsafe(64)} if default_key else {}),
        _item("legacy_docs", "fail" if legacy_docs else "ok", "Company documents not publicly downloadable",
              f"{legacy_docs} file(s) still in /static." if legacy_docs else "All company documents are in private storage.",
              "Move them to private storage.", "action" if legacy_docs else "none", link="admin_secure_uploads"),
        _item("cookie_secure", "ok" if settings.cookie_secure_effective else "warn", "Cookies marked Secure (HTTPS only)",
              "On." if settings.cookie_secure_effective else "Off — required once the site is served over HTTPS.",
              "Serve over HTTPS and set COOKIE_SECURE=true.", "env",
              {} if settings.cookie_secure_effective else {"COOKIE_SECURE": "true"}),
        _item("enforce_admin_2fa", "ok" if enforce_2fa and not admins_no_2fa else "warn", "2FA enforced for administrators",
              ("Enforced" if enforce_2fa else "Not enforced") + f" · {admins_no_2fa} active admin(s) without 2FA.",
              "Enforce it; each admin is sent to 2FA setup at next sign-in.",
              "toggle" if not enforce_2fa else ("link" if admins_no_2fa else "none"),
              toggle=None if enforce_2fa else "enforce_admin_2fa", link="my_profile_2fa_setup" if admins_no_2fa else None),
        _item("email_otp", "ok" if ps.require_email_otp else "warn", "Email OTP on registration",
              "On." if ps.require_email_otp else "Off — anyone can register with an unverified email.",
              "Require an emailed code before registration is submitted.",
              "none" if ps.require_email_otp else "toggle", toggle=None if ps.require_email_otp else "email_otp"),
        _item("impersonation", "warn" if get_setting(db, "allow_impersonation") else "ok", "Admin impersonation",
              "Enabled (dev tool)." if get_setting(db, "allow_impersonation") else "Disabled.",
              "Turn off before go-live.", "toggle" if get_setting(db, "allow_impersonation") else "none",
              toggle="impersonation" if get_setting(db, "allow_impersonation") else None),
        _item("dev_banner", "info" if get_setting(db, "dev_mode_banner") else "ok", "Test-environment banner",
              "Shown on every page." if get_setting(db, "dev_mode_banner") else "Hidden.",
              "Hide it for client demos and production.", "toggle" if get_setting(db, "dev_mode_banner") else "none",
              toggle="dev_banner" if get_setting(db, "dev_mode_banner") else None),
        _item("debug", "warn" if settings.DEBUG else "ok", "DEBUG mode", "On." if settings.DEBUG else "Off.",
              "Disable debug output and SQL echo.", "env", {"DEBUG": "false"} if settings.DEBUG else {}),
        _item("rate_limit", "ok" if rl["ok"] else "info", "Rate limiting store", rl["detail"],
              "Point REDIS_URL at a Redis server so limits hold across workers.", "env",
              {} if rl["ok"] else {"REDIS_URL": settings.REDIS_URL or "redis://localhost:6379/0"}),
        _item("email", "ok" if smtp_ready else "info", "Email delivery",
              f"SMTP via {settings.SMTP_HOST}." if smtp_ready else f"EMAIL_MODE={settings.EMAIL_MODE} — emails are printed, not sent.",
              "Configure SMTP (a KSA-hosted provider is recommended).", "env",
              {} if smtp_ready else {"EMAIL_MODE": "smtp", "SMTP_HOST": settings.SMTP_HOST or "smtp.example.sa",
                                     "SMTP_PORT": str(settings.SMTP_PORT), "SMTP_USERNAME": settings.SMTP_USERNAME or "no-reply@example.sa",
                                     "SMTP_PASSWORD": "********", "SMTP_FROM_EMAIL": settings.SMTP_FROM_EMAIL}),
        _item("password_hashing", "ok", "Password hashing", "Argon2 (passlib)."),
        _item("csrf", "ok", "CSRF protection", "Double-submit token on every POST."),
    ] + _extra_items(db)
    return sorted(items, key=lambda i: LEVEL_ORDER[i["level"]])


def env_fixes(items: list[dict]) -> dict:
    out = {}
    for i in items:
        if i["level"] != "ok":
            out.update(i["env"])
    return out


def apply_toggle(db: Session, admin: User, key: str) -> str:
    if key not in TOGGLES:
        raise ValueError("Unknown fix.")
    store, name, value = TOGGLES[key]
    if key == "enforce_admin_2fa" and not admin.totp_enabled:
        raise ValueError("Set up your own 2FA first (My Profile → Two-factor authentication), then enforce it.")
    if store == "setting":
        set_setting(db, name, value, admin.id)
        from app.core import system_settings
        getattr(system_settings, "_CACHE", {}).clear()
    else:
        from app.repositories import platform_settings_repository
        platform_settings_repository.update_settings(db, **{name: value})
    db.add(AuditLog(actor_user_id=admin.id, action="security_fix_applied", target_type="user", target_id=admin.id,
                    details=f"{key} → {value}"))
    db.commit()
    return name


def score(items: list[dict]) -> int:
    weights = {"ok": 1.0, "info": 0.75, "warn": 0.4, "fail": 0.0}
    return round(100 * sum(weights[i["level"]] for i in items) / len(items)) if items else 0
