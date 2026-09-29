"""
app/services/lab_partner_service.py
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.system_settings import get_setting
from app.models.audit_log import AuditLog
from app.models.company import ApprovalStatus, Company, CompanyRole
from app.models.lab_partner import LabPartnerTerms
from app.models.user import User
from app.models.verification import VerificationRequest, VerificationStatus
from app.repositories import audit_log_repository


class LabPartnerError(ValueError):
    pass


def terms_for(db: Session, lab_id) -> LabPartnerTerms | None:
    return db.query(LabPartnerTerms).filter_by(lab_company_id=lab_id).first()


def lab_options(db: Session) -> list[dict]:
    default_fee = get_setting(db, "lab_verification_fee_sar")
    labs = db.query(Company).filter(Company.role == CompanyRole.LAB, Company.status == ApprovalStatus.APPROVED) \
        .order_by(Company.company_name).all()
    terms = {t.lab_company_id: t for t in db.query(LabPartnerTerms)}
    out = []
    for lab in labs:
        t = terms.get(lab.id)
        if t is not None and (not t.is_accepting_requests or not t.accreditation_current):
            continue
        out.append({"lab": lab, "terms": t, "fee": t.fee_sar if t and t.fee_sar is not None else default_fee,
                    "turnaround": t.turnaround_days if t else None, "preferred": bool(t and t.is_preferred),
                    "accreditation": (t.accreditation_body if t else None)})
    return sorted(out, key=lambda o: (not o["preferred"], o["lab"].company_name))


def lab_stats(db: Session) -> dict:
    rows = db.query(VerificationRequest.lab_company_id, VerificationRequest.status, func.count()) \
        .group_by(VerificationRequest.lab_company_id, VerificationRequest.status).all()
    stats: dict = {}
    for lab_id, status, n in rows:
        s = stats.setdefault(lab_id, {"total": 0, "passed": 0, "failed": 0, "active": 0, "avg_days": None})
        s["total"] += n
        if status == VerificationStatus.COMPLETED:
            s["passed"] += n
        elif status == VerificationStatus.FAILED:
            s["failed"] += n
        else:
            s["active"] += n
    for lab_id, avg in db.query(VerificationRequest.lab_company_id,
                                func.avg(func.extract("epoch", VerificationRequest.completed_at - VerificationRequest.created_at)))\
            .filter(VerificationRequest.completed_at.isnot(None)).group_by(VerificationRequest.lab_company_id):
        if lab_id in stats and avg is not None:
            stats[lab_id]["avg_days"] = round(float(avg) / 86400, 1)
    for s in stats.values():
        done = s["passed"] + s["failed"]
        s["pass_rate"] = round(100 * s["passed"] / done) if done else None
    return stats


def save_terms(db: Session, admin: User, lab: Company, form) -> LabPartnerTerms:
    if lab.role != CompanyRole.LAB:
        raise LabPartnerError("That company is not a laboratory.")
    t = terms_for(db, lab.id)
    if t is None:
        t = LabPartnerTerms(lab_company_id=lab.id)
        db.add(t)

    def num(key, kind):
        raw = (form.get(key) or "").strip()
        if not raw:
            return None
        try:
            v = kind(raw)
        except (ValueError, InvalidOperation):
            raise LabPartnerError(f"{key.replace('_', ' ').capitalize()} must be a number.")
        if v < 0:
            raise LabPartnerError(f"{key.replace('_', ' ').capitalize()} can't be negative.")
        return v

    t.fee_sar = num("fee_sar", Decimal)
    t.turnaround_days = num("turnaround_days", int)
    raw_until = (form.get("accreditation_valid_until") or "").strip()
    try:
        t.accreditation_valid_until = date.fromisoformat(raw_until) if raw_until else None
    except ValueError:
        raise LabPartnerError("Accreditation expiry must be a date.")
    t.accreditation_body = (form.get("accreditation_body") or "").strip()[:120] or None
    t.accreditation_number = (form.get("accreditation_number") or "").strip()[:80] or None
    t.accreditation_scope = (form.get("accreditation_scope") or "").strip() or None
    t.notes = (form.get("notes") or "").strip() or None
    t.is_accepting_requests = bool(form.get("is_accepting_requests"))
    t.is_preferred = bool(form.get("is_preferred"))
    audit_log_repository.create(db, AuditLog(actor_user_id=admin.id, action="lab_terms_updated", target_type="company",
                                             target_id=lab.id, details=f"fee={t.fee_sar} tat={t.turnaround_days} "
                                             f"accepting={t.is_accepting_requests} preferred={t.is_preferred}"))
    db.commit()
    return t
