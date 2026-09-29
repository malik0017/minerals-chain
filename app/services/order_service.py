"""
app/services/order_service.py
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.notification import Notification
from app.models.order import Order, OrderStatus, RevealLog
from app.models.quotation import Quotation, QuotationStatus
from app.models.rfq import RFQ, RFQStatus
from app.services import notification_service
from app.repositories import notification_repository, order_repository
from app.services import settlement_service
from app.services.reference_service import next_reference


class OrderActionError(ValueError):
    pass


def _notify_company_users(db: Session, target_company: Company, *, type_: str, title: str, body: str,
                           action_url: str | None = None, **params) -> None:
    # Batch M6: bilingual, deep-linked — see services/notification_service.py
    notification_service.notify_company(db, target_company, type_, title, body, action_url=action_url, **params)


def accept_quotation(db: Session, rfq: RFQ, quotation: Quotation, buyer_company: Company) -> Order:
    if rfq.buyer_company_id != buyer_company.id:
        raise OrderActionError("RFQ not found.")
    if quotation.rfq_id != rfq.id:
        raise OrderActionError("Quotation not found.")
    if rfq.status != RFQStatus.OPEN:
        raise OrderActionError("This RFQ is already closed.")
    if quotation.status != QuotationStatus.SUBMITTED:
        raise OrderActionError("This quotation has already been acted on or has expired.")
    from datetime import date as _date
    if quotation.valid_until is not None and quotation.valid_until < _date.today():
        raise OrderActionError("This quotation's validity has ended — ask the seller to revise it.")

    order = Order(
        rfq_id=rfq.id,
        quotation_id=quotation.id,
        buyer_company_id=buyer_company.id,
        seller_company_id=quotation.seller_company_id,
        status=OrderStatus.PENDING_CONFIRMATION,
        order_reference=next_reference(db, "order"),  
    )
    order_repository.create(db, order)
    order.rfq, order.quotation = rfq, quotation
    settlement_service.snapshot_order_financials(db, order)  

    quotation.status = QuotationStatus.ACCEPTED
    rfq.status = RFQStatus.CLOSED
    for other in db.query(Quotation).filter(Quotation.rfq_id == rfq.id, Quotation.id != quotation.id,
                                            Quotation.status == QuotationStatus.SUBMITTED):
        other.status = QuotationStatus.REJECTED
        _notify_company_users(db, other.seller_company, type_="quotation_not_selected", title="Quotation not selected",
                              body=f"RFQ {rfq.rfq_reference} was closed with another quotation.",
                              action_url=f"/seller/rfq-inbox/{rfq.id}", rfq=rfq.rfq_reference or "")

    _notify_company_users(
        db, quotation.seller_company,
        type_="quotation_accepted",
        title="Your quotation was accepted",
        body=f"A buyer accepted your quotation on the {rfq.mineral_type} RFQ. "
             f"Confirm the order to proceed — this is also when you'll see who the buyer is.",
        action_url=f"/seller/orders/{order.id}", mineral=rfq.mineral_type,
    )

    db.commit()
    db.refresh(order)
    return order


def get_owned_order(db: Session, order_id: uuid.UUID, company_id: uuid.UUID, role: str) -> Order:
    order = order_repository.get_by_id(db, order_id)
    if order is None:
        raise OrderActionError("Order not found.")
    owner_id = order.buyer_company_id if role == "buyer" else order.seller_company_id
    if owner_id != company_id:
        raise OrderActionError("Order not found.")
    return order


def confirm_order(db: Session, order: Order, confirmed_by=None) -> Order:
    if order.status != OrderStatus.PENDING_CONFIRMATION:
        raise OrderActionError(f"This order is already {order.status.value.replace('_', ' ')}.")

    now = datetime.now(timezone.utc)
    order.status = OrderStatus.CONFIRMED
    order.confirmed_at = now  
    order.identity_revealed_at = now
    db.add(RevealLog(
        order_id=order.id, buyer_company_id=order.buyer_company_id, seller_company_id=order.seller_company_id,
        triggered_by="seller_confirmation", triggered_by_user_id=confirmed_by.id if confirmed_by else None,
        revealed_at=now,
    ))
    settlement_service.create_settlement_fees(db, order)

    _notify_company_users(
        db, order.buyer_company,
        type_="order_confirmed",
        title="Order confirmed — seller identity revealed",
        body=f"The seller confirmed your {order.rfq.mineral_type} order. You can now see who you're trading with.",
        action_url=f"/buyer/orders/{order.id}", mineral=order.rfq.mineral_type,
    )

    db.commit()
    db.refresh(order)
    return order


def mark_shipped(db: Session, order: Order) -> Order:
    if order.status != OrderStatus.CONFIRMED:
        raise OrderActionError(f"This order is {order.status.value.replace('_', ' ')} — it must be confirmed first.")
    order.status = OrderStatus.IN_TRANSIT
    order.shipped_at = datetime.now(timezone.utc)
    _notify_company_users(
        db, order.buyer_company,
        type_="order_shipped",
        title="Order in transit",
        body=f"Your {order.rfq.mineral_type} order is now in transit.",
        action_url=f"/buyer/orders/{order.id}", mineral=order.rfq.mineral_type,
    )
    db.commit()
    db.refresh(order)
    return order


def mark_delivered(db: Session, order: Order) -> Order:
    if order.status != OrderStatus.IN_TRANSIT:
        raise OrderActionError(f"This order is {order.status.value.replace('_', ' ')} — it must be in transit first.")
    order.status = OrderStatus.DELIVERED
    order.delivered_at = datetime.now(timezone.utc)
    _notify_company_users(
        db, order.buyer_company,
        type_="order_delivered",
        title="Order delivered",
        body=f"Your {order.rfq.mineral_type} order has been marked delivered. Confirm receipt to complete it.",
        action_url=f"/buyer/orders/{order.id}", mineral=order.rfq.mineral_type,
    )
    db.commit()
    db.refresh(order)
    return order


def confirm_receipt(db: Session, order: Order) -> Order:
    from app.core.system_settings import get_setting
    if order.status not in (OrderStatus.DELIVERED, OrderStatus.INVOICED):
        raise OrderActionError(f"This order is {order.status.value.replace('_', ' ')} — it must be delivered first.")
    if order.status == OrderStatus.DELIVERED and get_setting(db, "require_invoice_before_completion"):
        raise OrderActionError("The seller must issue the invoice before receipt can be confirmed.")
    order.status = OrderStatus.COMPLETED
    order.completed_at = datetime.now(timezone.utc)
    _notify_company_users(
        db, order.seller_company,
        type_="order_completed",
        title="Order completed",
        body=f"The buyer confirmed receipt of the {order.rfq.mineral_type} order. It's now complete.",
        action_url=f"/seller/orders/{order.id}", mineral=order.rfq.mineral_type,
    )
    db.commit()
    db.refresh(order)
    return order
