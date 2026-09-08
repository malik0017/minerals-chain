"""
app/services/admin_service.py
"""

import uuid
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
from app.models.company import ApprovalStatus, Company
from app.models.notification import Notification
from app.models.user import User
from app.repositories import audit_log_repository, company_repository, notification_repository

class AdminActionError(ValueError):
    pass


def _notify_company_users(db: Session, company: Company, *, type_: str, title: str, body: str) -> None:
    for user in company.users:
        notification_repository.create(
            db, Notification(user_id=user.id, type=type_, title=title, body=body)
        )


def approve_company(db: Session, company_id: uuid.UUID, admin: User) -> Company:
    company = company_repository.get_by_id(db, company_id)
    if company is None:
        raise AdminActionError("Company not found.")
    if company.status != ApprovalStatus.PENDING:
        raise AdminActionError(f"This company is already {company.status.value}, not pending.")

    company.status = ApprovalStatus.APPROVED
    company.reviewed_by_user_id = admin.id
    company.rejection_reason = None

    audit_log_repository.create(
        db,
        AuditLog(
            actor_user_id=admin.id,
            action="company_approved",
            target_type="company",
            target_id=company.id,
        ),
    )
    _notify_company_users(
        db,
        company,
        type_="registration_approved",
        title="Registration approved",
        body=f"{company.company_name} has been approved. You now have full access to your portal.",
    )

    db.commit()
    db.refresh(company)
    return company


def reject_company(db: Session, company_id: uuid.UUID, admin: User, reason: str) -> Company:
    if not reason or not reason.strip():
        # BRD §6.1: "mandatory reason captured on rejection"
        raise AdminActionError("A rejection reason is required.")

    company = company_repository.get_by_id(db, company_id)
    if company is None:
        raise AdminActionError("Company not found.")
    if company.status != ApprovalStatus.PENDING:
        raise AdminActionError(f"This company is already {company.status.value}, not pending.")

    company.status = ApprovalStatus.REJECTED
    company.reviewed_by_user_id = admin.id
    company.rejection_reason = reason.strip()

    audit_log_repository.create(
        db,
        AuditLog(
            actor_user_id=admin.id,
            action="company_rejected",
            target_type="company",
            target_id=company.id,
            details=reason.strip(),
        ),
    )
    _notify_company_users(
        db,
        company,
        type_="registration_rejected",
        title="Registration not approved",
        body=f"Your registration for {company.company_name} was not approved. Reason: {reason.strip()}",
    )

    db.commit()
    db.refresh(company)
    return company
