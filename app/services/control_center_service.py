"""
app/services/control_center_service.py
"""
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import ADMIN_ROLES
from app.core.security import hash_password
from app.core.system_settings import get_setting
from app.models.audit_log import AuditLog
from app.models.batch import Batch
from app.models.company import ApprovalStatus, Company, CompanyRole, SubscriptionTier
from app.models.order import Order, OrderStatus, SettlementFee, SettlementFeeStatus
from app.models.product import Product
from app.models.rfq import RFQ
from app.models.user import User, UserRole
from app.repositories import audit_log_repository
from app.services import document_upload_service


class ControlCenterError(ValueError):
    pass


def _audit(db: Session, admin: User, action: str, target_type: str, target_id, details: str) -> None:
    audit_log_repository.create(db, AuditLog(
        actor_user_id=admin.id, action=action, target_type=target_type, target_id=target_id, details=details[:2000],
    ))


def _alembic_head() -> str | None:
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        return ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    except Exception:  
        return None


def system_health(db: Session) -> dict:
    try:
        current = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:  # pragma: no cover
        db.rollback()
        current = None
    head = _alembic_head()
    pg = db.execute(text("SHOW server_version")).scalar()
    return {
        "app_env": settings.APP_ENV,
        "debug": settings.DEBUG,
        "db_revision": current,
        "code_head": head,
        "migrations_ok": current is not None and current == head,
        "postgres": pg,
        "email_mode": settings.EMAIL_MODE,
        "counts": {
            "companies": db.scalar(select(func.count()).select_from(Company)),
            "pending_companies": db.scalar(select(func.count()).select_from(Company).where(Company.status == ApprovalStatus.PENDING)),
            "users": db.scalar(select(func.count()).select_from(User)),
            "listings": db.scalar(select(func.count()).select_from(Product)),
            "rfqs": db.scalar(select(func.count()).select_from(RFQ)),
            "orders": db.scalar(select(func.count()).select_from(Order)),
            "batches": db.scalar(select(func.count()).select_from(Batch)),
            "fees_pending": db.scalar(select(func.count()).select_from(SettlementFee).where(SettlementFee.status == SettlementFeeStatus.PENDING)),
        },
    }


def security_checklist(db: Session) -> list[dict]:
    """Each item: level ok|warn|fail|info, title, detail, fix. Order = severity."""
    from app.repositories import platform_settings_repository
    ps = platform_settings_repository.get_settings(db)
    admins_without_2fa = db.scalar(select(func.count()).select_from(User).where(
        User.role == UserRole.ADMIN, User.totp_enabled.is_(False), User.is_active.is_(True)))
    legacy_docs = document_upload_service.legacy_public_document_count()
    items = [
        {"level": "fail" if settings.SECRET_KEY.startswith("CHANGE_ME") else "ok",
         "title": "Session signing key (SECRET_KEY)",
         "detail": "Default development key in use — anyone who knows it can forge a login." if settings.SECRET_KEY.startswith("CHANGE_ME") else "Custom key configured.",
         "fix": "Set a long random SECRET_KEY in .env (python -c \"import secrets;print(secrets.token_urlsafe(64))\")."},
        {"level": "fail" if legacy_docs else "ok", "title": "Company documents not publicly downloadable",
         "detail": f"{legacy_docs} CR/licence file(s) still in the public /static folder." if legacy_docs else "All company documents are in private storage.",
         "fix": "Click “Secure legacy uploads” below.", "action": "secure_uploads" if legacy_docs else None},
        {"level": "ok" if settings.cookie_secure_effective else "warn", "title": "Cookies marked Secure (HTTPS only)",
         "detail": "On." if settings.cookie_secure_effective else "Off — fine on http://localhost, must be on in staging/production.",
         "fix": "Serve over HTTPS and set COOKIE_SECURE=true (APP_ENV=production forces it)."},
        {"level": "ok" if get_setting(db, "enforce_admin_2fa") else "warn", "title": "2FA enforced for administrators",
         "detail": f"{admins_without_2fa} active admin(s) without 2FA.",
         "fix": "System Settings → Security → Require 2FA for administrators (set up your own 2FA first)."},
        {"level": "ok" if ps.require_email_otp else "warn", "title": "Email OTP on registration",
         "detail": "On." if ps.require_email_otp else "Off — anyone can register with an unverified email.",
         "fix": "Settings → Email verification."},
        {"level": "warn" if get_setting(db, "allow_impersonation") else "ok", "title": "Admin impersonation",
         "detail": "Enabled (dev tool)." if get_setting(db, "allow_impersonation") else "Disabled.",
         "fix": "Turn off before go-live (always blocked when APP_ENV=production)."},
        {"level": "warn" if settings.DEBUG else "ok", "title": "DEBUG mode", "detail": "On." if settings.DEBUG else "Off.",
         "fix": "DEBUG=false in .env outside development (also stops SQL echo in logs)."},
        {"level": "info", "title": "Rate limiting store", "detail": "In-memory, per process (Batch G).",
         "fix": "Move to Redis before running multiple workers."},
        {"level": "info" if settings.EMAIL_MODE == "console" else "ok", "title": "Email delivery",
         "detail": f"EMAIL_MODE={settings.EMAIL_MODE}.", "fix": "Use smtp (or a KSA-hosted provider) in staging/production."},
        {"level": "ok", "title": "Password hashing", "detail": "Argon2 (passlib).", "fix": ""},
        {"level": "ok", "title": "CSRF protection", "detail": "Double-submit token on every POST (Batch G).", "fix": ""},
    ]
    order = {"fail": 0, "warn": 1, "info": 2, "ok": 3}
    return sorted(items, key=lambda i: order[i["level"]])


def secure_legacy_uploads(db: Session, admin: User) -> int:
    moved = document_upload_service.migrate_legacy_documents()
    _audit(db, admin, "documents_secured", "platform", admin.id, f"Moved {moved} company document(s) to private storage")
    db.commit()
    return moved

COMPANY_EDITABLE = ("company_name", "company_name_ar", "cr_number", "vat_registration_number",
                    "license_or_accreditation_number", "contact_email", "contact_phone", "city",
                    "national_address", "region_id", "customer_segment_id", "license_valid_until",
                    "license_verified", "is_founding_member", "subscription_tier", "subscription_valid_until")


def update_company(db: Session, company: Company, form: dict, admin: User) -> Company:
    changes = []

    def setval(name, value):
        old = getattr(company, name)
        old_cmp = old.value if hasattr(old, "value") else old
        new_cmp = value.value if hasattr(value, "value") else value
        if old_cmp != new_cmp:
            changes.append(f"{name}: {old_cmp!r} → {new_cmp!r}")
            setattr(company, name, value)

    for name in ("company_name", "cr_number", "license_or_accreditation_number", "contact_email"):
        v = (form.get(name) or "").strip()
        if not v:
            raise ControlCenterError(f"{name.replace('_', ' ').capitalize()} is required.")
        setval(name, v)
    for name in ("company_name_ar", "vat_registration_number", "contact_phone", "city", "national_address"):
        setval(name, (form.get(name) or "").strip() or None)
    vat = company.vat_registration_number
    if vat and (not vat.isdigit() or len(vat) != 15):
        raise ControlCenterError("VAT registration number must be 15 digits.")
    for name in ("region_id", "customer_segment_id"):
        raw = (form.get(name) or "").strip()
        setval(name, uuid.UUID(raw) if raw else None)
    for name in ("license_valid_until", "subscription_valid_until"):
        raw = (form.get(name) or "").strip()
        try:
            setval(name, date.fromisoformat(raw) if raw else None)
        except ValueError:
            raise ControlCenterError(f"{name.replace('_', ' ')}: use YYYY-MM-DD.")
    for name in ("license_verified", "is_founding_member"):
        setval(name, bool(form.get(name)))
    tier_raw = (form.get("subscription_tier") or "").strip()
    if company.role != CompanyRole.LAB or tier_raw:
        setval("subscription_tier", SubscriptionTier(tier_raw) if tier_raw else None)
    if changes:
        _audit(db, admin, "company_updated", "company", company.id, f"{company.company_name}: " + "; ".join(changes))
    db.commit()
    db.refresh(company)
    return company


def change_company_status(db: Session, company: Company, new_status: ApprovalStatus, admin: User, reason: str | None) -> Company:
    """Suspend / reactivate / (re)approve. Keeps users.is_active in sync with
    the company (User.is_active 'mirrors company approval', models/user.py)."""
    if new_status == company.status:
        return company
    if new_status in (ApprovalStatus.SUSPENDED, ApprovalStatus.REJECTED) and not (reason or "").strip():
        raise ControlCenterError("A reason is required to suspend or reject a company.")
    old = company.status
    if new_status == ApprovalStatus.APPROVED and old == ApprovalStatus.PENDING:
        from app.services.admin_service import approve_company
        return approve_company(db, company.id, admin)
    company.status = new_status
    company.reviewed_by_user_id = admin.id
    company.rejection_reason = reason.strip() if reason else None
    active = new_status == ApprovalStatus.APPROVED
    for u in company.users:
        u.is_active = active
    _audit(db, admin, f"company_{new_status.value}", "company", company.id,
           f"{company.company_name}: {old.value} → {new_status.value}" + (f" — {reason.strip()}" if reason else ""))
    db.commit()
    db.refresh(company)
    return company

def create_user(db: Session, admin: User, *, full_name: str, email: str, password: str,
                company_id: str | None, role: str, company_role: str, job_title: str | None,
                admin_role: str | None = None) -> User:
    from app.repositories import user_repository
    full_name, email = (full_name or "").strip(), (email or "").strip().lower()
    if not full_name or "@" not in email:
        raise ControlCenterError("Full name and a valid email are required.")
    if len(password or "") < 8:
        raise ControlCenterError("Password must be at least 8 characters.")
    if user_repository.get_by_email(db, email) is not None:
        raise ControlCenterError("A user with this email already exists.")
    if role == "admin":
        company = None
        user_role = UserRole.ADMIN
    else:
        company = db.get(Company, uuid.UUID(company_id)) if company_id else None
        if company is None:
            raise ControlCenterError("Pick the company this user belongs to.")
        user_role = UserRole(company.role.value)  
    if company_role not in ("owner", "manager", "operator", "viewer"):
        raise ControlCenterError("Invalid company role.")
    user = User(
        full_name=full_name, email=email, hashed_password=hash_password(password), role=user_role,
        company_id=company.id if company else None,
        is_active=True if company is None else company.status == ApprovalStatus.APPROVED,
        company_role=company_role, job_title=(job_title or "").strip() or None,
        admin_role=(admin_role if admin_role in ADMIN_ROLES else "support") if user_role == UserRole.ADMIN else None,
    )
    if user_role == UserRole.ADMIN and user.admin_role == "super_admin" and (admin.admin_role or "super_admin") != "super_admin":
        raise ControlCenterError("Only a super administrator can create another super administrator.")
    db.add(user)
    db.flush()
    _audit(db, admin, "user_created", "user", user.id,
           f"{email} ({user_role.value}{', ' + company.company_name if company else ''}, {company_role})")
    db.commit()
    return user


def impersonation_allowed(db: Session) -> bool:
    return settings.APP_ENV != "production" and bool(get_setting(db, "allow_impersonation"))

_STATUS_TIMESTAMP = {
    OrderStatus.CONFIRMED: "confirmed_at", OrderStatus.IN_TRANSIT: "shipped_at",
    OrderStatus.DELIVERED: "delivered_at", OrderStatus.COMPLETED: "completed_at",
    OrderStatus.CANCELLED: "cancelled_at",
}


def admin_set_order_status(db: Session, order: Order, new_status: OrderStatus, admin: User, reason: str) -> Order:
    """Admin override for testing and support. Never bypasses the identity
    rule silently: moving an order to CONFIRMED or beyond from PENDING
    reveals identities, so it writes a RevealLog with triggered_by='admin'."""
    from app.models.order import RevealLog
    from app.services import settlement_service
    if not (reason or "").strip():
        raise ControlCenterError("A reason is required for an admin status change.")
    old = order.status
    if new_status == old:
        return order
    now = datetime.now(timezone.utc)
    order.status = new_status
    ts = _STATUS_TIMESTAMP.get(new_status)
    if ts and getattr(order, ts) is None:
        setattr(order, ts, now)
    if new_status == OrderStatus.CANCELLED:
        order.cancellation_reason = reason.strip()
    revealing = {OrderStatus.CONFIRMED, OrderStatus.IN_TRANSIT, OrderStatus.DELIVERED, OrderStatus.COMPLETED, OrderStatus.INVOICED}
    if new_status in revealing and order.identity_revealed_at is None:
        order.confirmed_at = order.confirmed_at or now
        order.identity_revealed_at = now
        db.add(RevealLog(order_id=order.id, buyer_company_id=order.buyer_company_id,
                         seller_company_id=order.seller_company_id, triggered_by="admin",
                         triggered_by_user_id=admin.id, revealed_at=now))
        settlement_service.create_settlement_fees(db, order)
    _audit(db, admin, "order_status_override", "order", order.id,
           f"{order.order_reference or order.id}: {old.value} → {new_status.value} — {reason.strip()}")
    db.commit()
    db.refresh(order)
    return order


def set_fee_status(db: Session, fee: SettlementFee, status: str, admin: User, reference: str | None) -> SettlementFee:
    from app.services import settlement_service
    try:
        new_status = SettlementFeeStatus(status)
    except ValueError:
        raise ControlCenterError("Unknown fee status.")
    old = fee.status.value
    try:
        settlement_service.mark_fee(db, fee, new_status, admin, reference)
    except ValueError as exc:
        raise ControlCenterError(str(exc))
    _audit(db, admin, "settlement_fee_updated", "settlement_fee", fee.id,
           f"{fee.order.order_reference} {fee.party}: {old} → {new_status.value}" + (f" ref {reference}" if reference else ""))
    db.commit()
    return fee


def admin_create_company(db: Session, admin: User, form: dict) -> Company:
    from app.repositories import company_repository, user_repository
    from app.services.subscription_service import create_initial_subscription
    name = (form.get("company_name") or "").strip()
    cr = (form.get("cr_number") or "").strip()
    email = (form.get("owner_email") or "").strip().lower()
    role = form.get("role") or ""
    if not name or not cr or "@" not in email:
        raise ControlCenterError("Company name, CR number and the owner's email are required.")
    if role not in [r.value for r in CompanyRole]:
        raise ControlCenterError("Choose seller, buyer or lab.")
    if company_repository.get_by_cr_number(db, cr):
        raise ControlCenterError("A company with this CR number already exists.")
    if user_repository.get_by_email(db, email):
        raise ControlCenterError("A user with this email already exists.")
    password = form.get("owner_password") or ""
    if len(password) < 8:
        raise ControlCenterError("Owner password must be at least 8 characters.")
    approve = bool(form.get("approve"))
    crole = CompanyRole(role)
    company = Company(
        company_name=name, company_name_ar=(form.get("company_name_ar") or "").strip() or None, role=crole,
        cr_number=cr, license_or_accreditation_number=(form.get("license_number") or "").strip() or "—",
        cr_document_filename="", license_document_filename="",
        vat_registration_number=(form.get("vat_registration_number") or "").strip() or None,
        status=ApprovalStatus.APPROVED if approve else ApprovalStatus.PENDING,
        subscription_tier=None if crole == CompanyRole.LAB else SubscriptionTier.ENTRY,
        contact_email=email, contact_phone=(form.get("contact_phone") or "").strip() or None,
        city=(form.get("city") or "").strip() or None, reviewed_by_user_id=admin.id if approve else None,
    )
    raw_region = (form.get("region_id") or "").strip()
    company.region_id = uuid.UUID(raw_region) if raw_region else None
    company_repository.create(db, company)
    owner = User(
        company_id=company.id, full_name=(form.get("owner_name") or "").strip() or name, email=email,
        hashed_password=hash_password(password), role=UserRole(crole.value), is_active=True, company_role="owner",
    )
    db.add(owner)
    if approve and crole != CompanyRole.LAB:
        create_initial_subscription(db, company)
    db.flush()
    _audit(db, admin, "company_created_by_admin", "company", company.id,
           f"{name} ({crole.value}, {'approved' if approve else 'pending'}), owner {email}")
    db.commit()
    return company
