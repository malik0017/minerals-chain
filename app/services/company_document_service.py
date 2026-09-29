"""
app/services/company_document_service.py
"""
import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.company import Company, CompanyRole
from app.models.company_document import CompanyDocument
from app.models.user import User
from app.services import file_crypto, notification_service, private_files

DOC_TYPES = {
    "cr": "Commercial Registration (CR)",
    "license": "Operating licence / accreditation",
    "mining_license": "MIM mining licence",
    "vat_cert": "VAT registration certificate",
    "zakat_cert": "Zakat certificate (ZATCA)",
    "gosi_cert": "GOSI certificate",
    "saudization_cert": "Saudization (Nitaqat) certificate",
    "chamber_cert": "Chamber of Commerce membership",
    "national_address": "National address proof",
    "bank_letter": "Bank IBAN letter",
    "iso_cert": "ISO certificate",
    "insurance": "Insurance policy",
    "lab_accreditation": "ISO/IEC 17025 accreditation",
    "other": "Other",
}
REQUIRED = {
    CompanyRole.SELLER: ("cr", "license", "mining_license", "vat_cert", "zakat_cert", "national_address"),
    CompanyRole.BUYER: ("cr", "license", "vat_cert", "national_address"),
    CompanyRole.LAB: ("cr", "license", "lab_accreditation"),
}
EXPIRING_DAYS = 60
REMINDER_STEPS = (60, 30, 7, 0)
STATUS_LABELS = {"pending": "Pending review", "approved": "Approved", "rejected": "Rejected"}


class DocumentError(ValueError):
    pass


def _date(v):
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        raise DocumentError("Invalid date.")


def health(doc: CompanyDocument, today: date | None = None) -> str:
    if doc.status == "rejected":
        return "rejected"
    d = doc.days_left(today)
    if d is None:
        return "no_expiry"
    if d < 0:
        return "expired"
    return "expiring" if d <= EXPIRING_DAYS else "valid"


def current(db: Session, company: Company) -> list[CompanyDocument]:
    return (db.query(CompanyDocument)
            .filter(CompanyDocument.company_id == company.id, CompanyDocument.is_current.is_(True))
            .order_by(CompanyDocument.doc_type).all())


def history(db: Session, company: Company, doc_type: str) -> list[CompanyDocument]:
    return (db.query(CompanyDocument)
            .filter(CompanyDocument.company_id == company.id, CompanyDocument.doc_type == doc_type)
            .order_by(CompanyDocument.version.desc()).all())


def checklist(db: Session, company: Company) -> list[dict]:
    today = date.today()
    docs = {d.doc_type: d for d in current(db, company)}
    rows = []
    for key in REQUIRED.get(company.role, ()) + tuple(k for k in docs if k not in REQUIRED.get(company.role, ())):
        d = docs.get(key)
        rows.append({"type": key, "label": DOC_TYPES.get(key, key), "doc": d, "required": key in REQUIRED.get(company.role, ()),
                     "health": health(d, today) if d else "missing", "days_left": d.days_left(today) if d else None})
    return rows


def completeness(rows: list[dict]) -> int:
    req = [r for r in rows if r["required"]]
    ok = [r for r in req if r["health"] in ("valid", "no_expiry", "expiring") and r["doc"].status != "rejected"]
    return round(100 * len(ok) / len(req)) if req else 100


def upload(db: Session, company: Company, user: User, form, filename: str, contents: bytes) -> CompanyDocument:
    doc_type = form.get("doc_type") or ""
    if doc_type not in DOC_TYPES:
        raise DocumentError("Choose a document type.")
    issued, expires = _date(form.get("issued_on")), _date(form.get("expires_on"))
    if issued and expires and expires <= issued:
        raise DocumentError("Expiry date must be after the issue date.")
    try:
        stored = private_files.save_upload("company_library", filename, contents)
    except private_files.FileError as exc:
        raise DocumentError(str(exc))
    prev = (db.query(CompanyDocument)
            .filter(CompanyDocument.company_id == company.id, CompanyDocument.doc_type == doc_type)
            .order_by(CompanyDocument.version.desc()).first())
    db.query(CompanyDocument).filter(CompanyDocument.company_id == company.id, CompanyDocument.doc_type == doc_type,
                                     CompanyDocument.is_current.is_(True)).update({"is_current": False})
    doc = CompanyDocument(company_id=company.id, doc_type=doc_type, title=(form.get("title") or "").strip()[:200] or None,
                          number=(form.get("number") or "").strip()[:80] or None, issued_on=issued, expires_on=expires,
                          version=(prev.version + 1) if prev else 1, is_current=True, status="pending",
                          file_path=stored.path, file_sha256=stored.sha256, file_size=stored.size, mime=stored.mime,
                          original_name=stored.original_name, uploaded_by_user_id=user.id)
    db.add(doc)
    db.flush()
    db.add(AuditLog(actor_user_id=user.id, action="company_document_uploaded", target_type="company", target_id=company.id,
                    details=f"{doc_type} v{doc.version}"))
    notification_service.notify_admins(db, "companies", "document_uploaded", "Company document awaiting review",
                                       f"{company.company_name} uploaded {DOC_TYPES[doc_type]} (v{doc.version}).",
                                       action_url="/admin/documents?status=pending", company=company.company_name,
                                       doc_type=DOC_TYPES[doc_type])
    db.commit()
    return doc


def review(db: Session, doc: CompanyDocument, admin: User, approve: bool, note: str = "") -> CompanyDocument:
    note = (note or "").strip()
    if not approve and len(note) < 5:
        raise DocumentError("Give a reason for rejecting (at least 5 characters).")
    doc.status = "approved" if approve else "rejected"
    doc.review_note = note or None
    doc.reviewed_by_user_id, doc.reviewed_at = admin.id, datetime.now(timezone.utc)
    if approve and doc.doc_type == "license" and doc.expires_on:
        doc.company.license_valid_until = doc.expires_on
    label = DOC_TYPES.get(doc.doc_type, doc.doc_type)
    notification_service.notify_company(
        db, doc.company, "document_reviewed", f"{label}: {STATUS_LABELS[doc.status]}",
        f"{label} v{doc.version} was {doc.status}." + (f" Note: {note}" if note else ""),
        action_url="/account/documents", doc_type=label, status=STATUS_LABELS[doc.status], note=note)
    db.add(AuditLog(actor_user_id=admin.id, action=f"company_document_{doc.status}", target_type="company",
                    target_id=doc.company_id, details=f"{doc.doc_type} v{doc.version} {note}".strip()))
    db.commit()
    return doc


def register_initial(db: Session, company: Company, user: User | None) -> None:
    for doc_type, number, fname in (("cr", company.cr_number, company.cr_document_filename),
                                    ("license", company.license_or_accreditation_number, company.license_document_filename)):
        if not fname:
            continue
        rel = f"company_documents/{fname}"
        sha = None
        p = private_files.resolve(rel)
        if p is not None:
            try:
                sha = hashlib.sha256(file_crypto.read(p)).hexdigest()
            except Exception:
                sha = None
        db.add(CompanyDocument(company_id=company.id, doc_type=doc_type, number=number, version=1, is_current=True,
                               status="pending", file_path=rel, file_sha256=sha, original_name=fname,
                               expires_on=company.license_valid_until if doc_type == "license" else None,
                               uploaded_by_user_id=user.id if user else None))


def approve_initial(db: Session, company: Company, admin: User) -> None:
    now = datetime.now(timezone.utc)
    (db.query(CompanyDocument)
     .filter(CompanyDocument.company_id == company.id, CompanyDocument.status == "pending",
             CompanyDocument.doc_type.in_(("cr", "license")), CompanyDocument.version == 1)
     .update({"status": "approved", "reviewed_by_user_id": admin.id, "reviewed_at": now}, synchronize_session=False))


def get(db: Session, doc_id, company: Company | None = None) -> CompanyDocument | None:
    try:
        doc = db.get(CompanyDocument, uuid.UUID(str(doc_id)))
    except ValueError:
        return None
    if doc is None or (company is not None and doc.company_id != company.id):
        return None
    return doc


def read(doc: CompanyDocument) -> tuple[bytes, bool]:
    try:
        return private_files.read_verified(doc.file_path, doc.file_sha256)
    except private_files.FileError as exc:
        raise DocumentError(str(exc))


def admin_listing(db: Session, *, status: str = "", health_filter: str = "", doc_type: str = "", q: str = ""):
    today = date.today()
    query = db.query(CompanyDocument).join(Company).filter(CompanyDocument.is_current.is_(True))
    if status:
        query = query.filter(CompanyDocument.status == status)
    if doc_type:
        query = query.filter(CompanyDocument.doc_type == doc_type)
    if health_filter == "expired":
        query = query.filter(CompanyDocument.expires_on < today)
    elif health_filter == "expiring":
        query = query.filter(CompanyDocument.expires_on >= today, CompanyDocument.expires_on <= today + timedelta(days=EXPIRING_DAYS))
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(Company.company_name.ilike(like) | CompanyDocument.number.ilike(like))
    return query.order_by(CompanyDocument.status != "pending", CompanyDocument.expires_on.is_(None), CompanyDocument.expires_on)


def admin_stats(db: Session) -> dict:
    today = date.today()
    cur = db.query(CompanyDocument).filter(CompanyDocument.is_current.is_(True))
    by_status = dict(cur.with_entities(CompanyDocument.status, func.count()).group_by(CompanyDocument.status).all())
    by_type = cur.with_entities(CompanyDocument.doc_type, func.count()).group_by(CompanyDocument.doc_type).order_by(func.count().desc()).all()
    months = []
    for i in range(6):
        start = (today.replace(day=1) + timedelta(days=32 * i)).replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
        months.append({"name": start.strftime("%b %Y"),
                       "value": cur.filter(CompanyDocument.expires_on >= start, CompanyDocument.expires_on < end).count()})
    companies = db.query(Company).filter(Company.status == "approved").all()
    complete = sum(1 for c in companies if completeness(checklist(db, c)) == 100)
    return {
        "pending": by_status.get("pending", 0),
        "approved": by_status.get("approved", 0),
        "rejected": by_status.get("rejected", 0),
        "expired": cur.filter(CompanyDocument.expires_on < today).count(),
        "expiring": cur.filter(CompanyDocument.expires_on >= today, CompanyDocument.expires_on <= today + timedelta(days=EXPIRING_DAYS)).count(),
        "complete_pct": round(100 * complete / len(companies)) if companies else 0,
        "by_status": [{"name": STATUS_LABELS[k], "value": v} for k, v in by_status.items() if k in STATUS_LABELS],
        "by_type": [{"name": DOC_TYPES.get(k, k), "value": v} for k, v in by_type],
        "expiry_months": months,
    }


def send_expiry_reminders(db: Session, today: date | None = None) -> int:
    today = today or date.today()
    sent = 0
    docs = (db.query(CompanyDocument)
            .filter(CompanyDocument.is_current.is_(True), CompanyDocument.status != "rejected",
                    CompanyDocument.expires_on.isnot(None), CompanyDocument.expires_on <= today + timedelta(days=REMINDER_STEPS[0]))
            .all())
    for d in docs:
        left = d.days_left(today)
        step = next((s for s in sorted(REMINDER_STEPS) if left <= s), None)
        if step is None or (d.last_reminder_days is not None and d.last_reminder_days <= step):
            continue
        label = DOC_TYPES.get(d.doc_type, d.doc_type)
        title = f"{label} expired" if left < 0 else f"{label} expires in {left} day(s)"
        notification_service.notify_company(db, d.company, "document_expiring", title,
                                            f"Upload the renewed {label} before {d.expires_on:%Y-%m-%d} to keep trading.",
                                            action_url="/account/documents", doc_type=label, until=f"{d.expires_on:%Y-%m-%d}")
        d.last_reminder_days = step
        sent += 1
    if sent:
        notification_service.notify_admins(db, "companies", "documents_expiring", "Company documents expiring",
                                           f"{sent} reminder(s) sent to companies.", action_url="/admin/documents?health=expiring",
                                           count=sent)
    db.commit()
    return sent
