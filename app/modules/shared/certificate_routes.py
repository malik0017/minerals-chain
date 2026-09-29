"""
app/modules/shared/certificate_routes.py
"""
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_required
from app.core.listing import paginate, qs
from app.core.permissions import require_lab_company
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.database.base import get_db
from app.models.certification import Certification, CertificationStatus, CertificationType
from app.models.company import ApprovalStatus
from app.models.order import Order
from app.models.user import User, UserRole
from app.services.verification_service import coa_fingerprint

router = APIRouter(tags=["certificates"])


@router.get("/lab/certificates", name="lab_certificates")
def lab_certificates(request: Request, db: Session = Depends(get_db), user: User = Depends(require_lab_company),
                     result: str = "", q: str = "", page: int = 1):
    query = db.query(Certification).filter(Certification.issuing_company_id == user.company_id,
                                           Certification.cert_type == CertificationType.LAB_CERTIFICATE)
    if result == "pass":
        query = query.filter(Certification.status == CertificationStatus.APPROVED)
    elif result == "fail":
        query = query.filter(Certification.status == CertificationStatus.REJECTED)
    if q.strip():
        query = query.filter(Certification.certificate_number.ilike(f"%{q.strip()}%"))
    rows, total, page, pages = paginate(query.order_by(Certification.created_at.desc()), page)
    base = db.query(Certification).filter(Certification.issuing_company_id == user.company_id,
                                          Certification.cert_type == CertificationType.LAB_CERTIFICATE)
    stats = {"total": base.count(),
             "pass": base.filter(Certification.status == CertificationStatus.APPROVED).count(),
             "fail": base.filter(Certification.status == CertificationStatus.REJECTED).count()}
    ctx = build_portal_context(user, UserRole.LAB, active_path="/lab/certificates")
    ctx.update({"rows": rows, "total": total, "page": page, "pages": pages, "qs": qs(result=result, q=q),
                "result": result, "q": q, "stats": stats})
    return templates.TemplateResponse(request, "lab/certificates.html", ctx)


def _access(db: Session, cert: Certification, user: User) -> tuple[bool, bool]:
    """(allowed, seller_masked)"""
    if user.role == UserRole.ADMIN:
        return True, False
    if user.company_id in (cert.issuing_company_id, cert.subject_company_id):
        return True, False
    if user.role == UserRole.BUYER and user.company and user.company.status == ApprovalStatus.APPROVED \
            and cert.status == CertificationStatus.APPROVED:
        revealed = db.query(Order).filter(Order.buyer_company_id == user.company_id,
                                          Order.seller_company_id == cert.subject_company_id,
                                          Order.confirmed_at.isnot(None)).first() is not None
        return True, not revealed
    return False, True


@router.get("/certificates/{cert_id}", name="certificate_document")
def certificate_document(request: Request, cert_id: uuid.UUID, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user_required)):
    cert = db.get(Certification, cert_id)
    if cert is None:
        return Response(status_code=404)
    allowed, masked = _access(db, cert, user)
    if not allowed:
        return Response(status_code=404)
    product = cert.scopes[0].product if cert.scopes and cert.scopes[0].product else None
    intact = None
    if cert.cert_type == CertificationType.LAB_CERTIFICATE and cert.file_hash and cert.results:
        intact = coa_fingerprint(cert) == cert.file_hash
    source = db.get(Certification, cert.source_certification_id) if cert.source_certification_id else None
    return templates.TemplateResponse(request, "shared/certificate_document.html", {
        "cert": cert, "product": product, "masked": masked, "intact": intact, "source": source,
        "lang": user.preferred_language or "en", "vr": cert.verification_request})
