"""
app/services/rfq_service.py
"""
from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.audit_log import AuditLog
from app.models.md_quality import QualityParameter
from app.models.quotation import Quotation, QuotationStatus
from app.models.rfq import RFQ, RFQSpec, RFQStatus
from app.services import notification_service
from app.repositories import rfq_repository
from app.schemas.rfq import RFQRequest

from app.core.system_settings import get_setting
from app.models.user import User
from app.services.reference_service import next_reference
from app.services.subscription_limits import SubscriptionLimitError, check_can_create_rfq


class RFQActionError(ValueError):
    """Raised for any invalid RFQ action. Routes catch this and show
    the message."""
    pass


def create_rfq(db: Session, buyer_company: Company, payload: RFQRequest, created_by: User | None = None,
               spec_rows: list[dict] | None = None) -> RFQ:
    try:
        check_can_create_rfq(db, buyer_company)  
    except SubscriptionLimitError as exc:
        raise RFQActionError(str(exc))
    rfq = RFQ(
        rfq_reference=next_reference(db, "rfq"),
        closes_at=datetime.now(timezone.utc) + timedelta(days=get_setting(db, "rfq_open_days")),
        created_by_user_id=created_by.id if created_by else None,
        buyer_company_id=buyer_company.id,
        mineral_type=payload.mineral_type,
        specifications_notes=payload.specifications_notes,
        quantity_value=payload.quantity_value,
        quantity_unit=payload.quantity_unit,
        delivery_location=payload.delivery_location,
        delivery_timeframe=payload.delivery_timeframe,
        commercial_terms_notes=payload.commercial_terms_notes,
        # Batch M3: structured RFQ
        product_master_id=payload.product_master_id,
        incoterm_id=payload.incoterm_id,
        required_by=payload.required_by,
        payment_terms_days=payload.payment_terms_days,
    )
    if payload.product_master_id:
        from app.models.md_product import ProductMaster
        pm = db.get(ProductMaster, payload.product_master_id)
        rfq.grade_id = pm.grade_id if pm else None
    rfq_repository.create(db, rfq)
    known = {p.id.hex: p.id for p in db.query(QualityParameter.id)}
    for r in spec_rows or []:
        pid = r.get("parameter_id")
        db.add(RFQSpec(rfq_id=rfq.id, parameter=r["parameter"], min_value=r["min"], max_value=r["max"], unit=r["unit"],
                       parameter_id=known.get(str(pid).replace("-", "")) if pid else None))
    _notify_sellers_new_rfq(db, rfq)
    db.commit()
    db.refresh(rfq)
    return rfq


def get_owned_rfq(db: Session, rfq_id: uuid.UUID, buyer_company_id: uuid.UUID) -> RFQ:
    """Mirrors product_service.get_owned_listing — confirms an RFQ
    actually belongs to this buyer's company."""
    rfq = rfq_repository.get_by_id(db, rfq_id)
    if rfq is None or rfq.buyer_company_id != buyer_company_id:
        raise RFQActionError("RFQ not found.")
    return rfq

def _notify_sellers_new_rfq(db: Session, rfq: RFQ) -> None:
    """Only sellers who list the same mineral are told (keeps noise down);
    the buyer stays anonymous."""
    from app.models.company import ApprovalStatus, CompanyRole
    from app.models.product import Product
    seller_ids = {sid for (sid,) in db.query(Product.seller_company_id)
                  .filter(Product.mineral_type.ilike(f"%{rfq.mineral_type.split('(')[0].strip()}%"))}
    for c in db.query(Company).filter(Company.id.in_(seller_ids), Company.role == CompanyRole.SELLER,
                                      Company.status == ApprovalStatus.APPROVED):
        notification_service.notify_company(
            db, c, "rfq_new", "New RFQ matching your listings",
            f"New RFQ for {rfq.mineral_type} ({rfq.quantity_value} {rfq.quantity_unit}).",
            action_url=f"/seller/rfq-inbox/{rfq.id}", mineral=rfq.mineral_type,
            quantity=f"{rfq.quantity_value} {rfq.quantity_unit}")


def spec_rows(rfq: RFQ) -> list[dict]:
    return [{"parameter_id": s.parameter_id, "parameter": s.parameter, "min": s.min_value, "max": s.max_value,
             "unit": s.unit, "test_method": None} for s in rfq.specs]


def cancel_rfq(db: Session, rfq: RFQ, actor: User, reason: str) -> None:
    if rfq.status != RFQStatus.OPEN:
        raise RFQActionError("Only an open RFQ can be cancelled.")
    if len((reason or "").strip()) < 5:
        raise RFQActionError("Give a short reason for cancelling.")
    rfq.status = RFQStatus.CANCELLED
    rfq.cancelled_at = datetime.now(timezone.utc)
    rfq.cancel_reason = reason.strip()
    for q in db.query(Quotation).filter(Quotation.rfq_id == rfq.id, Quotation.status == QuotationStatus.SUBMITTED):
        q.status = QuotationStatus.REJECTED
        notification_service.notify_company(
            db, q.seller_company, "rfq_cancelled", "RFQ cancelled",
            f"The buyer cancelled RFQ {rfq.rfq_reference} ({rfq.mineral_type}). Your quotation is closed.",
            action_url=f"/seller/rfq-inbox/{rfq.id}", rfq=rfq.rfq_reference or "", mineral=rfq.mineral_type)
    db.add(AuditLog(actor_user_id=actor.id, action="rfq_cancelled", target_type="rfq", target_id=rfq.id,
                    details=f"{rfq.rfq_reference}: {rfq.cancel_reason}"[:500]))
    db.commit()



def accepting_quotes(rfq: RFQ) -> bool:
    """Open and before its closing date. After closes_at the buyer can still
    accept one of the quotes already received (while it is valid)."""
    return rfq.status == RFQStatus.OPEN and (rfq.closes_at is None or rfq.closes_at >= datetime.now(timezone.utc))
