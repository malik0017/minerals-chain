"""
app/services/data_request_service.py
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.system_settings import get_setting
from app.models.audit_log import AuditLog
from app.models.data_request import DataRequest, DataRequestStatus, DataRequestType
from app.models.notification import Notification
from app.models.user import User
from app.repositories import audit_log_repository
from app.services import notification_service
from app.services.reference_service import next_reference


class DataRequestError(ValueError):
    pass


def export_user_data(db: Session, user: User) -> dict:
    c = user.company
    notifications = db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.created_at).all()
    logins = db.query(AuditLog).filter(AuditLog.actor_user_id == user.id).order_by(AuditLog.created_at).all()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "account": {
            "full_name": user.full_name, "email": user.email, "phone": user.phone, "job_title": user.job_title,
            "role": user.role.value, "company_role": user.company_role, "preferred_language": user.preferred_language,
            "two_factor_enabled": user.totp_enabled, "created_at": user.created_at.isoformat(),
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "privacy_consent_at": user.privacy_consent_at.isoformat() if user.privacy_consent_at else None,
            "privacy_consent_version": user.privacy_consent_version,
        },
        "company": None if c is None else {
            "name": c.company_name, "name_ar": c.company_name_ar, "role": c.role.value, "cr_number": c.cr_number,
            "vat_registration_number": c.vat_registration_number, "license_number": c.license_or_accreditation_number,
            "contact_email": c.contact_email, "contact_phone": c.contact_phone, "city": c.city,
            "national_address": c.national_address, "status": c.status.value,
        },
        "notifications": [{"at": n.created_at.isoformat(), "type": n.type, "title": n.title, "body": n.body}
                          for n in notifications],
        "activity_log": [{"at": a.created_at.isoformat(), "action": a.action, "target": a.target_type} for a in logins],
        "data_requests": [{"reference": r.reference, "type": r.request_type.value, "status": r.status.value,
                           "created_at": r.created_at.isoformat()}
                          for r in db.query(DataRequest).filter(DataRequest.user_id == user.id)],
    }


def create_request(db: Session, user: User, request_type: str, details: str | None) -> DataRequest:
    try:
        rtype = DataRequestType(request_type)
    except ValueError:
        raise DataRequestError("Choose a request type.")
    if rtype in (DataRequestType.CORRECTION, DataRequestType.DELETION, DataRequestType.OBJECTION) and not (details or "").strip():
        raise DataRequestError("Please describe what you want corrected, deleted or objected to.")
    open_same = db.query(DataRequest).filter(
        DataRequest.user_id == user.id, DataRequest.request_type == rtype,
        DataRequest.status.in_([DataRequestStatus.OPEN, DataRequestStatus.IN_PROGRESS])).first()
    if open_same:
        raise DataRequestError(f"You already have an open {rtype.value} request ({open_same.reference}).")
    now = datetime.now(timezone.utc)
    req = DataRequest(
        reference=next_reference(db, "data_request"), user_id=user.id, company_id=user.company_id,
        request_type=rtype, details=(details or "").strip() or None, status=DataRequestStatus.OPEN,
        due_at=now + timedelta(days=get_setting(db, "data_request_sla_days")),
    )
    db.add(req)
    db.flush()
    notification_service.notify_admins(
        db, "data_requests", "data_request_submitted", "New personal-data request",
        f"{user.full_name} submitted a {rtype.value} request ({req.reference}).",
        action_url=f"/admin/data-requests/{req.id}", user=user.full_name, type=rtype.value, reference=req.reference)
    audit_log_repository.create(db, AuditLog(actor_user_id=user.id, action="data_request_created",
                                             target_type="data_request", target_id=req.id, details=rtype.value))
    db.commit()
    return req


def update_request(db: Session, req: DataRequest, admin: User, status: str, response: str | None) -> DataRequest:
    try:
        new_status = DataRequestStatus(status)
    except ValueError:
        raise DataRequestError("Unknown status.")
    if new_status in (DataRequestStatus.COMPLETED, DataRequestStatus.REJECTED) and not (response or "").strip():
        raise DataRequestError("A response to the user is required to complete or reject a request.")
    old = req.status.value
    req.status = new_status
    req.response = (response or "").strip() or req.response
    req.handled_by_user_id = admin.id
    req.handled_at = datetime.now(timezone.utc)
    notification_service.notify_user(
        db, req.user, "data_request_updated", "Your data request was updated",
        f"Your request {req.reference} is now {new_status.value.replace('_', ' ')}.",
        action_url="/my-profile/privacy", reference=req.reference, status=new_status.value)
    audit_log_repository.create(db, AuditLog(actor_user_id=admin.id, action="data_request_updated",
                                             target_type="data_request", target_id=req.id,
                                             details=f"{req.reference}: {old} → {new_status.value}"))
    db.commit()
    return req


def anonymise_user(db: Session, user: User, admin: User, reason: str) -> None:
    if user.id == admin.id:
        raise DataRequestError("You can't anonymise your own account.")
    if not (reason or "").strip():
        raise DataRequestError("A reason (e.g. the request reference) is required.")
    tag = uuid.uuid4().hex[:10]
    old_email = user.email
    user.full_name = "Deleted user"
    user.email = f"deleted-{tag}@removed.invalid"
    user.phone = None
    user.job_title = None
    user.avatar_filename = None
    user.totp_secret = None
    user.totp_enabled = False
    user.is_active = False
    audit_log_repository.create(db, AuditLog(actor_user_id=admin.id, action="user_anonymised", target_type="user",
                                             target_id=user.id, details=f"PDPL deletion — {reason.strip()} (was {old_email[:3]}***)"))
    db.commit()
