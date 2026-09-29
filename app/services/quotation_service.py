"""
app/services/quotation_service.py
"""
from datetime import date, timedelta
from decimal import Decimal
import uuid

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.audit_log import AuditLog
from app.models.certification import Certification, CertificationType
from app.models.product import Product, ProductStatus
from app.models.quotation import Quotation, QuotationStatus
from app.models.rfq import RFQ, RFQStatus
from app.repositories import certification_repository, quotation_repository
from app.services import notification_service, spec_service
from app.services.rfq_service import accepting_quotes, spec_rows as rfq_spec_rows
from app.schemas.quotation import QuotationRequest

from app.core.system_settings import get_setting
from app.models.user import User
from app.services.reference_service import next_reference


class QuotationActionError(ValueError):
    """Raised for any invalid quotation action. Routes catch this and
    show the message."""
    pass


def _apply_offer(db: Session, quotation: Quotation, rfq: RFQ, seller_company: Company, payload: QuotationRequest) -> None:
    """Batch M3: price, terms, validity, and the offered listing — which
    brings its current COA / passport and the spec match score."""
    quotation.price_value = payload.price_value
    quotation.price_currency = payload.price_currency
    quotation.price_unit = payload.price_unit
    quotation.lead_time_days = payload.lead_time_days
    quotation.terms_notes = payload.terms_notes
    quotation.incoterm_id = payload.incoterm_id or rfq.incoterm_id
    quotation.payment_terms_days = payload.payment_terms_days if payload.payment_terms_days is not None else rfq.payment_terms_days
    validity_days = payload.validity_days or get_setting(db, "quotation_validity_days")
    quotation.total_price = (payload.price_value * rfq.quantity_value).quantize(Decimal("0.01"))
    quotation.validity_days = validity_days
    quotation.valid_until = date.today() + timedelta(days=validity_days)
    quotation.product_id = quotation.coa_certification_id = quotation.passport_certification_id = None
    quotation.match_score = None
    if payload.product_id:
        product = db.get(Product, payload.product_id)
        if product is None or product.seller_company_id != seller_company.id:
            raise QuotationActionError("Choose one of your own listings.")
        if product.status != ProductStatus.VERIFIED:
            raise QuotationActionError("Only a verified listing can be offered against an RFQ.")
        quotation.product_id = product.id
        for c in certification_repository.list_for_product(db, product.id):
            if not c.is_currently_valid:
                continue
            if c.cert_type == CertificationType.LAB_CERTIFICATE and quotation.coa_certification_id is None:
                quotation.coa_certification_id = c.id
            elif c.cert_type == CertificationType.MINERAL_PASSPORT and quotation.passport_certification_id is None:
                quotation.passport_certification_id = c.id
        quotation.match_score = spec_service.match_score(rfq_spec_rows(rfq), spec_service.product_rows(db, product))


def submit_quotation(db: Session, rfq: RFQ, seller_company: Company, payload: QuotationRequest,
                     submitted_by: User | None = None) -> Quotation:
    if not accepting_quotes(rfq):
        raise QuotationActionError("This RFQ is closed and no longer accepting quotations.")
    if quotation_repository.get_by_rfq_and_seller(db, rfq.id, seller_company.id) is not None:
        raise QuotationActionError("You've already submitted a quotation for this RFQ — revise it instead.")

    quotation = Quotation(rfq_id=rfq.id, seller_company_id=seller_company.id, revision_no=1)
    _apply_offer(db, quotation, rfq, seller_company, payload)
    # Batch J (Schema V1): reference
    quotation.quotation_reference = next_reference(db, "quotation")
    quotation.submitted_by_user_id = submitted_by.id if submitted_by else None
    quotation_repository.create(db, quotation)
    notification_service.notify_company(
        db, rfq.buyer_company, "quotation_received", "New quotation received",
        f"You received a quotation on RFQ {rfq.rfq_reference} ({rfq.mineral_type}).",
        action_url=f"/buyer/rfqs/{rfq.id}", rfq=rfq.rfq_reference or "", mineral=rfq.mineral_type)
    db.commit()
    db.refresh(quotation)
    return quotation


def revise_quotation(db: Session, quotation: Quotation, payload: QuotationRequest, revised_by: User) -> Quotation:
    """BRD §6.5 — a seller may revise its quote while the RFQ is open and the
    quote hasn't been acted on. revision_no increments; validity restarts."""
    rfq = quotation.rfq
    if quotation.status not in (QuotationStatus.SUBMITTED, QuotationStatus.EXPIRED):
        raise QuotationActionError("This quotation has already been acted on and can't be revised.")
    if not accepting_quotes(rfq):
        raise QuotationActionError("This RFQ is closed and no longer accepting quotations.")
    old = f"{quotation.price_value} × {quotation.lead_time_days}d"
    _apply_offer(db, quotation, rfq, quotation.seller_company, payload)
    quotation.status = QuotationStatus.SUBMITTED
    quotation.revision_no = (quotation.revision_no or 1) + 1
    quotation.submitted_by_user_id = revised_by.id
    db.add(AuditLog(actor_user_id=revised_by.id, action="quotation_revised", target_type="quotation",
                    target_id=quotation.id, details=f"{quotation.quotation_reference} r{quotation.revision_no}: {old} → "
                                                    f"{quotation.price_value} × {quotation.lead_time_days}d"))
    notification_service.notify_company(
        db, rfq.buyer_company, "quotation_revised", "A quotation was revised",
        f"A seller revised its quotation on RFQ {rfq.rfq_reference}.", action_url=f"/buyer/rfqs/{rfq.id}",
        rfq=rfq.rfq_reference or "")
    db.commit()
    db.refresh(quotation)
    return quotation


def expire_stale(db: Session) -> int:
    """Submitted quotations past valid_until become EXPIRED (setting
    quotation_auto_expire). Idempotent; run on RFQ pages and by the
    Control Center lifecycle job."""
    if not get_setting(db, "quotation_auto_expire"):
        return 0
    n = (db.query(Quotation).filter(Quotation.status == QuotationStatus.SUBMITTED, Quotation.valid_until.isnot(None),
                                    Quotation.valid_until < date.today())
         .update({Quotation.status: QuotationStatus.EXPIRED}, synchronize_session=False))
    if n:
        db.commit()
    return n


def comparison(db: Session, rfq: RFQ, sort: str = "price") -> list[dict]:
    """Buyer comparison table rows (BRD §6.5 'compare quotations side by
    side'). Flags the best price, fastest delivery and best match."""
    rows = []
    for q in quotation_repository.list_for_rfq(db, rfq.id):
        rows.append({"q": q, "total": q.total_price or (q.price_value * rfq.quantity_value),
                     "expired": q.status == QuotationStatus.EXPIRED or (q.valid_until is not None and q.valid_until < date.today()),
                     "coa": db.get(Certification, q.coa_certification_id) if q.coa_certification_id else None,
                     "passport": db.get(Certification, q.passport_certification_id) if q.passport_certification_id else None})
    live = [r for r in rows if not r["expired"] and r["q"].status == QuotationStatus.SUBMITTED]
    if live:
        best_price = min(r["total"] for r in live)
        fastest = min(r["q"].lead_time_days for r in live)
        scores = [r["q"].match_score for r in live if r["q"].match_score is not None]
        best_match = max(scores) if scores else None
        for r in live:
            r["best_price"] = r["total"] == best_price
            r["fastest"] = r["q"].lead_time_days == fastest
            r["best_match"] = best_match is not None and r["q"].match_score == best_match
    keys = {"price": lambda r: (r["expired"], r["total"]),
            "lead": lambda r: (r["expired"], r["q"].lead_time_days, r["total"]),
            "match": lambda r: (r["expired"], -(r["q"].match_score or -1), r["total"])}
    return sorted(rows, key=keys.get(sort, keys["price"]))


def get_owned_quotation(db: Session, quotation_id: uuid.UUID, seller_company_id: uuid.UUID) -> Quotation:
    quotation = quotation_repository.get_by_id(db, quotation_id)
    if quotation is None or quotation.seller_company_id != seller_company_id:
        raise QuotationActionError("Quotation not found.")
    return quotation
