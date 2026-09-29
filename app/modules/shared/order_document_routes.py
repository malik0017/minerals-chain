"""
app/modules/shared/order_document_routes.py
"""
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.core.permissions import require_admin, require_buyer_company, require_seller_company
from app.database.base import get_db
from app.models.order import Order
from app.models.user import User
from app.services import order_document_service as ods


def _serve(doc, data: bytes, intact: bool) -> Response:
    name = (doc.original_filename or "document").replace('"', "")
    headers = {"Content-Disposition": f'inline; filename="{name}"', "X-Integrity": "verified" if intact else "MISMATCH",
               "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:"}
    return Response(content=data, media_type=doc.mime_type or "application/octet-stream", headers=headers)


def make_router(party: str) -> APIRouter:
    guard = require_buyer_company if party == "buyer" else require_seller_company
    router = APIRouter(prefix=f"/{party}/orders", tags=[f"{party}-order-documents"])

    def _order(db, order_id, user) -> Order | None:
        o = db.get(Order, order_id)
        if o is None:
            return None
        return o if ods.party_of(o, user) == party else None

    def _back(order_id, *, msg=None, error=None):
        url = f"/{party}/orders/{order_id}"
        if error:
            url += "?error=" + quote(error)
        elif msg:
            url += "?msg=" + quote(msg)
        return RedirectResponse(url=url + "#documents", status_code=303)

    @router.post("/{order_id}/documents", name=f"{party}_order_document_upload")
    def upload(order_id: uuid.UUID, document_type: str = Form(""), title: str = Form(""), notes: str = Form(""),
               share: str = Form("1"), file: UploadFile | None = File(None), db: Session = Depends(get_db),
               user: User = Depends(guard)):
        o = _order(db, order_id, user)
        if o is None:
            return RedirectResponse(url=f"/{party}/orders", status_code=303)
        try:
            ods.upload(db, o, user, document_type, file, title, notes, share=bool(share))
        except ods.OrderDocumentError as exc:
            db.rollback()
            return _back(order_id, error=str(exc))
        return _back(order_id, msg="Document uploaded.")

    @router.get("/{order_id}/documents/{doc_id}", name=f"{party}_order_document")
    def download(order_id: uuid.UUID, doc_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(guard)):
        o = _order(db, order_id, user)
        if o is None:
            return Response(status_code=404)
        try:
            return _serve(*ods.read(db, o, doc_id, user))
        except ods.OrderDocumentError:
            return Response(status_code=404)

    if party == "seller":
        @router.post("/{order_id}/invoice", name="seller_order_invoice")
        def invoice(order_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(guard)):
            o = _order(db, order_id, user)
            if o is None:
                return RedirectResponse(url="/seller/orders", status_code=303)
            try:
                ods.issue_invoice(db, o, user)
            except ods.OrderDocumentError as exc:
                db.rollback()
                return _back(order_id, error=str(exc))
            return _back(order_id, msg=f"Invoice {o.invoice_number} issued and shared with the buyer.")

    return router


buyer_router = make_router("buyer")
seller_router = make_router("seller")
admin_router = APIRouter(tags=["admin-order-documents"])


@admin_router.get("/admin/orders/{order_id}/documents/{doc_id}", name="admin_order_document")
def admin_download(order_id: uuid.UUID, doc_id: uuid.UUID, db: Session = Depends(get_db),
                   admin: User = Depends(require_admin("orders"))):
    o = db.get(Order, order_id)
    if o is None:
        return Response(status_code=404)
    try:
        return _serve(*ods.read(db, o, doc_id, admin))
    except ods.OrderDocumentError:
        return Response(status_code=404)
