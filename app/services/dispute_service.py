"""
app/services/dispute_service.py
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.system_settings import get_setting
from app.models.audit_log import AuditLog
from app.models.dispute import Dispute, DisputeCorrection, DisputeMessage, DisputeRuling, DisputeStatus
from app.models.order import Order, OrderStatus
from app.models.user import User
from app.repositories import audit_log_repository
from app.services import notification_service, private_files
from app.services.reference_service import next_reference

CATEGORIES = {
    "quality": "Quality / specification mismatch",
    "quantity": "Quantity / weight difference",
    "delivery_delay": "Late or missed delivery",
    "damaged": "Damaged or contaminated goods",
    "documentation": "Missing or wrong documents",
    "pricing": "Price or invoice disagreement",
    "other": "Other",
}
DISPUTABLE = {OrderStatus.CONFIRMED, OrderStatus.IN_TRANSIT, OrderStatus.DELIVERED, OrderStatus.INVOICED}


class DisputeError(ValueError):
    pass


def _audit(db, actor: User, action: str, d: Dispute, details: str = "") -> None:
    audit_log_repository.create(db, AuditLog(actor_user_id=actor.id, action=action, target_type="dispute",
                                             target_id=d.id, details=f"{d.reference}: {details}"[:500]))


def _party_url(d: Dispute, party: str) -> str:
    return f"/{party}/disputes/{d.id}"


def _notify_parties(db, d: Dispute, type_: str, title: str, body: str, *, exclude: str | None = None, **params):
    order = d.order
    for party, company in (("buyer", order.buyer_company), ("seller", order.seller_company)):
        if party != exclude:
            notification_service.notify_company(db, company, type_, title, body,
                                                action_url=_party_url(d, party), dispute=d.reference, **params)


def party_of(order: Order, company_id) -> str | None:
    if order.buyer_company_id == company_id:
        return "buyer"
    if order.seller_company_id == company_id:
        return "seller"
    return None


def can_raise(db: Session, order: Order) -> tuple[bool, str]:
    if active_for_order(db, order):
        return False, "A dispute is already open on this order."
    if order.status in DISPUTABLE:
        return True, ""
    if order.status == OrderStatus.COMPLETED and order.completed_at:
        window = get_setting(db, "dispute_window_days")
        if datetime.now(timezone.utc) <= order.completed_at + timedelta(days=window):
            return True, ""
        return False, f"The {window}-day dispute window after completion has passed."
    return False, "Disputes can be raised once the seller has confirmed the order."


def active_for_order(db: Session, order: Order) -> Dispute | None:
    return (db.query(Dispute).filter(Dispute.order_id == order.id,
                                     Dispute.status.in_([DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW,
                                                         DisputeStatus.AWAITING_INFO]))
            .first())


def for_order(db: Session, order: Order) -> list[Dispute]:
    return db.query(Dispute).filter(Dispute.order_id == order.id).order_by(Dispute.created_at.desc()).all()


def _attach(msg: DisputeMessage, upload) -> None:
    if upload is None or not getattr(upload, "filename", ""):
        return
    try:
        stored = private_files.save_upload("dispute_evidence", upload.filename, upload.file.read())
    except private_files.FileError as exc:
        raise DisputeError(str(exc))
    msg.attachment_path, msg.attachment_name, msg.attachment_hash = stored.path, stored.original_name, stored.sha256


def raise_dispute(db: Session, order: Order, user: User, category: str, reason: str,
                  desired_outcome: str = "", upload=None) -> Dispute:
    party = party_of(order, user.company_id)
    if party is None:
        raise DisputeError("Order not found.")
    ok, why = can_raise(db, order)
    if not ok:
        raise DisputeError(why)
    if category not in CATEGORIES:
        raise DisputeError("Choose a dispute category.")
    if len((reason or "").strip()) < 10:
        raise DisputeError("Describe the problem (at least 10 characters).")
    d = Dispute(reference=next_reference(db, "dispute"), order_id=order.id, raised_by_party=party,
                raised_by_company_id=user.company_id, raised_by_user_id=user.id, category=category,
                reason=reason.strip(), desired_outcome=(desired_outcome or "").strip() or None,
                status=DisputeStatus.OPEN, order_status_before=order.status.value)
    db.add(d)
    db.flush()
    msg = DisputeMessage(dispute_id=d.id, author_user_id=user.id, author_party=party, body=reason.strip())
    _attach(msg, upload)
    db.add(msg)
    order.status = OrderStatus.DISPUTED
    d.order = order
    _notify_parties(db, d, "dispute_raised", "A dispute was raised",
                    f"Dispute {d.reference} was raised on order {order.order_reference}: {CATEGORIES[category]}.",
                    exclude=party, order=order.order_reference or "", category=CATEGORIES[category])
    notification_service.notify_admins(db, "disputes", "dispute_raised", "New dispute",
                                       f"{d.reference} on {order.order_reference} ({CATEGORIES[category]}).",
                                       action_url=f"/admin/disputes/{d.id}", dispute=d.reference,
                                       order=order.order_reference or "", category=CATEGORIES[category])
    _audit(db, user, "dispute_raised", d, f"by {party} · {category} · order was {d.order_status_before}")
    db.commit()
    return d


def post_message(db: Session, d: Dispute, user: User, party: str, body: str, *,
                 internal: bool = False, upload=None) -> DisputeMessage:
    if not d.is_active:
        raise DisputeError("This dispute is closed — messages can no longer be added.")
    if not (body or "").strip():
        raise DisputeError("Write a message.")
    msg = DisputeMessage(dispute_id=d.id, author_user_id=user.id, author_party=party, body=body.strip(),
                         is_internal=internal and party == "admin")
    _attach(msg, upload)
    db.add(msg)
    if not msg.is_internal:
        if party == "admin":
            _notify_parties(db, d, "dispute_message", "New message on your dispute",
                            f"The platform posted a message on dispute {d.reference}.")
        else:
            _notify_parties(db, d, "dispute_message", "New message on your dispute",
                            f"There is a new message on dispute {d.reference}.", exclude=party)
            if d.status == DisputeStatus.AWAITING_INFO:
                d.status = DisputeStatus.UNDER_REVIEW
            notification_service.notify_admins(db, "disputes", "dispute_message", "Dispute reply",
                                               f"New {party} message on {d.reference}.",
                                               action_url=f"/admin/disputes/{d.id}", dispute=d.reference)
    _audit(db, user, "dispute_note" if msg.is_internal else "dispute_message", d, party)
    db.commit()
    return msg


def withdraw(db: Session, d: Dispute, user: User) -> None:
    if not d.is_active:
        raise DisputeError("This dispute is already closed.")
    if d.raised_by_company_id != user.company_id:
        raise DisputeError("Only the party that raised the dispute can withdraw it.")
    d.status = DisputeStatus.WITHDRAWN
    d.withdrawn_at = datetime.now(timezone.utc)
    d.order.status = OrderStatus(d.order_status_before)
    _notify_parties(db, d, "dispute_withdrawn", "Dispute withdrawn", f"Dispute {d.reference} was withdrawn.",
                    exclude=d.raised_by_party)
    _audit(db, user, "dispute_withdrawn", d, f"order restored to {d.order_status_before}")
    db.commit()


def set_status(db: Session, d: Dispute, admin: User, status: str, assign_to=None) -> None:
    if not d.is_active:
        raise DisputeError("This dispute is closed.")
    if status not in (DisputeStatus.OPEN.value, DisputeStatus.UNDER_REVIEW.value, DisputeStatus.AWAITING_INFO.value):
        raise DisputeError("Use the decision form to resolve a dispute.")
    old = d.status.value
    d.status = DisputeStatus(status)
    if assign_to is not None:
        d.assigned_admin_id = assign_to
    elif d.assigned_admin_id is None:
        d.assigned_admin_id = admin.id
    if old != status:
        _notify_parties(db, d, "dispute_status", "Dispute status updated",
                        f"Dispute {d.reference} is now {status.replace('_', ' ')}.", status=status.replace("_", " "))
    _audit(db, admin, "dispute_status", d, f"{old} → {status}")
    db.commit()


def decide(db: Session, d: Dispute, admin: User, ruling: str, decision_text: str) -> None:
    if d.is_decided:
        raise DisputeError("This dispute is already decided. Use a formal correction to change it.")
    if not d.is_active:
        raise DisputeError("This dispute is closed.")
    if ruling not in ("buyer", "seller"):
        raise DisputeError("Choose in whose favour the dispute is decided.")
    if len((decision_text or "").strip()) < 20:
        raise DisputeError("Write the decision and its reasons (at least 20 characters).")
    now = datetime.now(timezone.utc)
    d.ruling = DisputeRuling(ruling)
    d.decision_text = decision_text.strip()
    d.decided_at = now
    d.decided_by_user_id = admin.id
    d.status = DisputeStatus.RESOLVED
    if d.assigned_admin_id is None:
        d.assigned_admin_id = admin.id
    order = d.order
    order.status = OrderStatus.RESOLVED
    order.completed_via_dispute = True
    order.completed_at = order.completed_at or now
    _notify_parties(db, d, "dispute_resolved", "Dispute decided",
                    f"Dispute {d.reference} was decided in favour of the {ruling}.", party=ruling)
    _audit(db, admin, "dispute_decided", d, f"ruling={ruling}")
    db.commit()


def correct_ruling(db: Session, d: Dispute, admin: User, ruling: str, decision_text: str, reason: str) -> None:
    if not d.is_decided:
        raise DisputeError("Only a decided dispute can be corrected.")
    if ruling not in ("buyer", "seller"):
        raise DisputeError("Choose the corrected ruling.")
    if len((reason or "").strip()) < 10:
        raise DisputeError("A formal reason for the correction is required (at least 10 characters).")
    new_text = (decision_text or "").strip() or d.decision_text
    if ruling == d.ruling.value and new_text == d.decision_text:
        raise DisputeError("Nothing changed.")
    db.add(DisputeCorrection(dispute_id=d.id, previous_ruling=d.ruling.value, new_ruling=ruling,
                             previous_text=d.decision_text, new_text=new_text, reason=reason.strip(),
                             corrected_by_user_id=admin.id, corrected_at=datetime.now(timezone.utc)))
    d.ruling = DisputeRuling(ruling)
    d.decision_text = new_text
    _notify_parties(db, d, "dispute_corrected", "Dispute decision corrected",
                    f"The decision on dispute {d.reference} was formally corrected.")
    _audit(db, admin, "dispute_corrected", d, reason.strip())
    db.commit()


def visible_messages(d: Dispute, party: str) -> list[DisputeMessage]:
    return [m for m in d.messages if party == "admin" or not m.is_internal]
