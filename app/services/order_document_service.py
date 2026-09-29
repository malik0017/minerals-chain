"""
app/services/order_document_service.py
"""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.certification import Certification
from app.models.order import Order, OrderDocument, OrderStatus
from app.models.user import User, UserRole
from app.services import notification_service, private_files
from app.services.reference_service import next_reference

DOC_TYPES = {
    "weighbridge_cert": "Weighbridge certificate",
    "proof_of_delivery": "Proof of delivery",
    "packing_list": "Packing list",
    "quality_report": "Quality / inspection report",
    "bill_of_lading": "Bill of lading / waybill",
    "other": "Other",
}
GENERATED_TYPES = {"invoice": "Commercial invoice", "coa": "Certificate of Analysis", "mineral_passport": "Mineral Passport"}


class OrderDocumentError(ValueError):
    pass


def party_of(order: Order, user: User) -> str | None:
    if user.role == UserRole.ADMIN:
        return "admin"
    if user.company_id == order.buyer_company_id:
        return "buyer"
    if user.company_id == order.seller_company_id:
        return "seller"
    return None


def visible_documents(order: Order, party: str) -> list[OrderDocument]:
    docs = sorted(order.documents, key=lambda d: d.created_at, reverse=True)
    if party == "admin":
        return docs
    return [d for d in docs if (d.visible_to_buyer if party == "buyer" else d.visible_to_seller)]


def linked_credentials(db: Session, order: Order) -> list[Certification]:
    q = order.quotation
    ids = [i for i in (q.coa_certification_id, q.passport_certification_id) if i] if q else []
    return [c for c in (db.get(Certification, i) for i in ids) if c is not None]


def upload(db: Session, order: Order, user: User, doc_type: str, upload_file, title: str = "",
           notes: str = "", share: bool = True) -> OrderDocument:
    party = party_of(order, user)
    if party not in ("buyer", "seller"):
        raise OrderDocumentError("Order not found.")
    if order.confirmed_at is None:
        raise OrderDocumentError("Documents can be exchanged once the seller has confirmed the order.")
    if order.status == OrderStatus.CANCELLED:
        raise OrderDocumentError("This order is cancelled.")
    if doc_type not in DOC_TYPES:
        raise OrderDocumentError("Choose a document type.")
    if upload_file is None or not getattr(upload_file, "filename", ""):
        raise OrderDocumentError("Choose a file to upload.")
    try:
        stored = private_files.save_upload("order_documents", upload_file.filename, upload_file.file.read())
    except private_files.FileError as exc:
        raise OrderDocumentError(str(exc))
    doc = OrderDocument(
        order_id=order.id, document_type=doc_type, title=(title or "").strip()[:200] or DOC_TYPES[doc_type],
        original_filename=stored.original_name, mime_type=stored.mime, file_size=stored.size,
        file_path=stored.path, file_hash=stored.sha256, uploaded_by_user_id=user.id, is_generated=False,
        notes=(notes or "").strip() or None,
        visible_to_buyer=True if party == "buyer" else share,
        visible_to_seller=True if party == "seller" else share,
    )
    db.add(doc)
    db.flush()
    if share:
        other = order.seller_company if party == "buyer" else order.buyer_company
        notification_service.notify_company(
            db, other, "order_document", "New document on an order",
            f"A {DOC_TYPES[doc_type].lower()} was added to order {order.order_reference}.",
            action_url=f"/{'seller' if party == 'buyer' else 'buyer'}/orders/{order.id}",
            doc_type=DOC_TYPES[doc_type], order=order.order_reference or "")
    db.add(AuditLog(actor_user_id=user.id, action="order_document_uploaded", target_type="order", target_id=order.id,
                    details=f"{order.order_reference}: {doc_type} {stored.sha256[:12]}"))
    db.commit()
    return doc


def read(db: Session, order: Order, doc_id, user: User) -> tuple[OrderDocument, bytes, bool]:
    party = party_of(order, user)
    doc = db.get(OrderDocument, doc_id)
    if party is None or doc is None or doc.order_id != order.id or doc not in visible_documents(order, party):
        raise OrderDocumentError("Document not found.")
    try:
        data, intact = private_files.read_verified(doc.file_path, doc.file_hash)
    except private_files.FileError:
        raise OrderDocumentError("The file is missing from storage.")
    if not intact:
        db.add(AuditLog(actor_user_id=user.id, action="document_integrity_mismatch", target_type="order",
                        target_id=order.id, details=f"{doc.id} {doc.file_path}"))
        db.commit()
    return doc, data, intact


def issue_invoice(db: Session, order: Order, seller_user: User) -> OrderDocument:
    if order.status != OrderStatus.DELIVERED:
        raise OrderDocumentError("An invoice can be issued once the order is delivered.")
    if order.invoice_number:
        raise OrderDocumentError(f"Invoice {order.invoice_number} was already issued.")
    from app.core.templates import templates
    now = datetime.now(timezone.utc)
    order.invoice_number = next_reference(db, "invoice")
    order.invoiced_at = now
    due = date.today() + timedelta(days=order.payment_terms_days or 0)
    html = templates.env.get_template("documents/commercial_invoice.html").render(
        order=order, seller=order.seller_company, buyer=order.buyer_company, issued=now, due=due,
        platform="Minerals Chain")
    stored = private_files.save_generated("order_documents", f"{order.invoice_number}.html", html.encode("utf-8"))
    doc = OrderDocument(order_id=order.id, document_type="invoice", title=f"Commercial invoice {order.invoice_number}",
                        original_filename=f"{order.invoice_number}.html", mime_type=stored.mime, file_size=stored.size,
                        file_path=stored.path, file_hash=stored.sha256, uploaded_by_user_id=seller_user.id,
                        is_generated=True, visible_to_buyer=True, visible_to_seller=True,
                        notes="Commercial invoice generated by the platform. Not a ZATCA e-invoice.")
    db.add(doc)
    order.status = OrderStatus.INVOICED
    notification_service.notify_company(
        db, order.buyer_company, "order_invoiced", "Invoice issued",
        f"The seller issued invoice {order.invoice_number} for order {order.order_reference}.",
        action_url=f"/buyer/orders/{order.id}", invoice=order.invoice_number, mineral=order.rfq.mineral_type)
    db.add(AuditLog(actor_user_id=seller_user.id, action="invoice_issued", target_type="order", target_id=order.id,
                    details=f"{order.order_reference} → {order.invoice_number} total {order.total_value_sar}"))
    db.commit()
    return doc

