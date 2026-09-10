"""
app/services/quotation_service.py

BRD §6.5. The one-quotation-per-seller-per-RFQ rule is enforced here,
not as a DB unique constraint — a DB constraint can't produce a clean
"you already quoted this" message, and the check needs to run before
the insert anyway to give a useful error. A future "revise your
quote" feature would edit the existing row rather than needing a
second one, so this constraint isn't expected to loosen later, just
possibly grow an edit path.
"""
import uuid

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.quotation import Quotation
from app.models.rfq import RFQ, RFQStatus
from app.repositories import quotation_repository
from app.schemas.quotation import QuotationRequest


class QuotationActionError(ValueError):
    """Raised for any invalid quotation action. Routes catch this and
    show the message."""
    pass


def submit_quotation(db: Session, rfq: RFQ, seller_company: Company, payload: QuotationRequest) -> Quotation:
    if rfq.status != RFQStatus.OPEN:
        raise QuotationActionError("This RFQ is closed and no longer accepting quotations.")
    if quotation_repository.get_by_rfq_and_seller(db, rfq.id, seller_company.id) is not None:
        raise QuotationActionError("You've already submitted a quotation for this RFQ.")

    quotation = Quotation(
        rfq_id=rfq.id,
        seller_company_id=seller_company.id,
        price_value=payload.price_value,
        price_currency=payload.price_currency,
        price_unit=payload.price_unit,
        lead_time_days=payload.lead_time_days,
        terms_notes=payload.terms_notes,
    )
    quotation_repository.create(db, quotation)
    db.commit()
    db.refresh(quotation)
    return quotation


def get_owned_quotation(db: Session, quotation_id: uuid.UUID, seller_company_id: uuid.UUID) -> Quotation:
    quotation = quotation_repository.get_by_id(db, quotation_id)
    if quotation is None or quotation.seller_company_id != seller_company_id:
        raise QuotationActionError("Quotation not found.")
    return quotation
