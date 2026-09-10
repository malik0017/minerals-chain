"""
app/services/rfq_service.py

BRD §6.5. create_rfq() has no approval gate beyond "the buyer's
company is approved" (already enforced by require_seller_company's
sibling, require_active_portal, at the route level) — an RFQ isn't
reviewed before going out, unlike a product listing needing lab
verification first. Any approved buyer can post one immediately.
"""
import uuid

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.rfq import RFQ
from app.repositories import rfq_repository
from app.schemas.rfq import RFQRequest


class RFQActionError(ValueError):
    """Raised for any invalid RFQ action. Routes catch this and show
    the message."""
    pass


def create_rfq(db: Session, buyer_company: Company, payload: RFQRequest) -> RFQ:
    rfq = RFQ(
        buyer_company_id=buyer_company.id,
        mineral_type=payload.mineral_type,
        specifications_notes=payload.specifications_notes,
        quantity_value=payload.quantity_value,
        quantity_unit=payload.quantity_unit,
        delivery_location=payload.delivery_location,
        delivery_timeframe=payload.delivery_timeframe,
        commercial_terms_notes=payload.commercial_terms_notes,
    )
    rfq_repository.create(db, rfq)
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
