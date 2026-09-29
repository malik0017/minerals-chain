"""
app/services/admin_service.py
"""

import uuid
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
from app.models.company import ApprovalStatus, Company
from app.models.notification import Notification
from app.models.user import User
from app.services import notification_service
from app.repositories import audit_log_repository, company_repository, notification_repository
from app.services.subscription_service import create_initial_subscription

class AdminActionError(ValueError):
    pass


def _notify_company_users(db: Session, target_company: Company, *, type_: str, title: str, body: str,
                           action_url: str | None = None, **params) -> None:
    # Batch M6: bilingual, deep-linked — see services/notification_service.py
    notification_service.notify_company(db, target_company, type_, title, body, action_url=action_url, **params)


def approve_company(db: Session, company_id: uuid.UUID, admin: User) -> Company:
    company = company_repository.get_by_id(db, company_id)
    if company is None:
        raise AdminActionError("Company not found.")
    if company.status != ApprovalStatus.PENDING:
        raise AdminActionError(f"This company is already {company.status.value}, not pending.")

    company.status = ApprovalStatus.APPROVED
    company.reviewed_by_user_id = admin.id
    company.rejection_reason = None

    create_initial_subscription(db, company)
    from app.services import company_document_service
    company_document_service.approve_initial(db, company, admin)

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
        action_url="/home", company=company.company_name,
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
        company=company.company_name, reason=reason.strip(),
    )

    db.commit()
    db.refresh(company)
    return company
