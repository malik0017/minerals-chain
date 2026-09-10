"""
app/services/passport_service.py
"""
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.notification import Notification
from app.models.passport import MineralPassport, PassportScope, PassportStatus
from app.models.product import Product, ProductStatus
from app.models.user import User
from app.repositories import notification_repository, passport_repository


VALIDITY_PERIOD_DAYS = 365


class PassportActionError(ValueError):
    """Raised for any invalid passport action. Routes catch this and
    show the message."""
    pass


def _notify_company_users(db: Session, company: Company, *, type_: str, title: str, body: str) -> None:
    for user in company.users:
        notification_repository.create(
            db, Notification(user_id=user.id, type=type_, title=title, body=body)
        )


def request_passport(db: Session, product: Product, scope: PassportScope) -> MineralPassport:
    if product.status != ProductStatus.VERIFIED:
        raise PassportActionError("Only a verified listing can request a Mineral Passport.")
    if passport_repository.has_pending_or_active(db, product.id):
        raise PassportActionError("This listing already has a pending or currently valid passport.")

    passport = MineralPassport(
        product_id=product.id,
        seller_company_id=product.seller_company_id,
        scope=scope,
        status=PassportStatus.PENDING,
    )
    passport_repository.create(db, passport)
    db.commit()
    db.refresh(passport)
    return passport


def get_pending_passport(db: Session, passport_id: uuid.UUID) -> MineralPassport:
    passport = passport_repository.get_by_id(db, passport_id)
    if passport is None:
        raise PassportActionError("Passport request not found.")
    return passport


def approve_passport(db: Session, passport: MineralPassport, admin: User) -> MineralPassport:
    if passport.status != PassportStatus.PENDING:
        raise PassportActionError(f"This passport request is already {passport.status.value}.")

    passport.status = PassportStatus.APPROVED
    passport.passport_number = f"MP-{secrets.token_hex(4).upper()}"
    passport.valid_from = date.today()
    passport.valid_until = date.today() + timedelta(days=VALIDITY_PERIOD_DAYS)
    passport.reviewed_by_user_id = admin.id
    passport.reviewed_at = datetime.now(timezone.utc)

    _notify_company_users(
        db, passport.seller_company,
        type_="passport_approved",
        title="Mineral Passport issued",
        body=f"Your {passport.scope.value.replace('_', ' ')} passport for {passport.product.mineral_type} "
             f"has been issued: {passport.passport_number} (valid until {passport.valid_until}).",
    )

    db.commit()
    db.refresh(passport)
    return passport


def reject_passport(db: Session, passport: MineralPassport, admin: User, rejection_reason: str) -> MineralPassport:
    if passport.status != PassportStatus.PENDING:
        raise PassportActionError(f"This passport request is already {passport.status.value}.")

    passport.status = PassportStatus.REJECTED
    passport.rejection_reason = rejection_reason
    passport.reviewed_by_user_id = admin.id
    passport.reviewed_at = datetime.now(timezone.utc)

    _notify_company_users(
        db, passport.seller_company,
        type_="passport_rejected",
        title="Mineral Passport request not approved",
        body=f"Your passport request for {passport.product.mineral_type} was not approved. Reason: {rejection_reason}",
    )

    db.commit()
    db.refresh(passport)
    return passport
