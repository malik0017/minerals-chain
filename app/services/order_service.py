"""
app/services/order_service.py

BRD §6.5's "acceptance creates an order and closes the RFQ" and
§6.6's full order lifecycle, including the identity reveal on seller
confirmation (see core/identity_guard.py for the concealment logic
itself — this module only triggers the transition, by setting
confirmed_at).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.notification import Notification
from app.models.order import Order, OrderStatus
from app.models.quotation import Quotation, QuotationStatus
from app.models.rfq import RFQ, RFQStatus
from app.repositories import notification_repository, order_repository


class OrderActionError(ValueError):
    """Raised for any invalid order action. Routes catch this and show
    the message."""
    pass


def _notify_company_users(db: Session, company: Company, *, type_: str, title: str, body: str) -> None:
    for user in company.users:
        notification_repository.create(
            db, Notification(user_id=user.id, type=type_, title=title, body=body)
        )


def accept_quotation(db: Session, rfq: RFQ, quotation: Quotation, buyer_company: Company) -> Order:
    if rfq.buyer_company_id != buyer_company.id:
        raise OrderActionError("RFQ not found.")
    if quotation.rfq_id != rfq.id:
        raise OrderActionError("Quotation not found.")
    if rfq.status != RFQStatus.OPEN:
        raise OrderActionError("This RFQ is already closed.")
    if quotation.status != QuotationStatus.SUBMITTED:
        raise OrderActionError("This quotation has already been acted on.")

    order = Order(
        rfq_id=rfq.id,
        quotation_id=quotation.id,
        buyer_company_id=buyer_company.id,
        seller_company_id=quotation.seller_company_id,
        status=OrderStatus.PENDING_CONFIRMATION,
    )
    order_repository.create(db, order)

    quotation.status = QuotationStatus.ACCEPTED
    rfq.status = RFQStatus.CLOSED

    # Identity is NOT revealed here — the seller only learns their
    # quote was accepted and an order is waiting on their confirmation.
    _notify_company_users(
        db, quotation.seller_company,
        type_="quotation_accepted",
        title="Your quotation was accepted",
        body=f"A buyer accepted your quotation on the {rfq.mineral_type} RFQ. "
             f"Confirm the order to proceed — this is also when you'll see who the buyer is.",
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


def confirm_order(db: Session, order: Order) -> Order:
    if order.status != OrderStatus.PENDING_CONFIRMATION:
        raise OrderActionError(f"This order is already {order.status.value.replace('_', ' ')}.")

    order.status = OrderStatus.CONFIRMED
    order.confirmed_at = datetime.now(timezone.utc)  # THE identity-reveal trigger

    _notify_company_users(
        db, order.buyer_company,
        type_="order_confirmed",
        title="Order confirmed — seller identity revealed",
        body=f"The seller confirmed your {order.rfq.mineral_type} order. You can now see who you're trading with.",
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
    )
    db.commit()
    db.refresh(order)
    return order


def confirm_receipt(db: Session, order: Order) -> Order:
    if order.status != OrderStatus.DELIVERED:
        raise OrderActionError(f"This order is {order.status.value.replace('_', ' ')} — it must be delivered first.")
    order.status = OrderStatus.COMPLETED
    order.completed_at = datetime.now(timezone.utc)
    _notify_company_users(
        db, order.seller_company,
        type_="order_completed",
        title="Order completed",
        body=f"The buyer confirmed receipt of the {order.rfq.mineral_type} order. It's now complete.",
    )
    db.commit()
    db.refresh(order)
    return order
