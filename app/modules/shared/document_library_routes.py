"""
app/modules/shared/document_library_routes.py
"""
import uuid
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.core.permissions import require_active_portal
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.database.base import get_db
from app.models.user import User, UserRole
from app.services import company_document_service as docs

router = APIRouter(prefix="/account/documents", tags=["document-library"])
guard = require_active_portal(UserRole.SELLER, UserRole.BUYER, UserRole.LAB)


def _back(msg=None, error=None):
    q = f"?error={quote(error)}" if error else (f"?msg={quote(msg)}" if msg else "")
    return RedirectResponse(url="/account/documents" + q, status_code=303)


def serve(doc, data: bytes, intact: bool) -> Response:
    name = (doc.original_name or "document").replace('"', "")
    return Response(content=data, media_type=doc.mime or "application/octet-stream",
                    headers={"Content-Disposition": f'inline; filename="{name}"', "X-Integrity": "verified" if intact else "MISMATCH",
                             "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:"})


@router.get("", name="my_documents")
def page(request: Request, db: Session = Depends(get_db), user: User = Depends(guard),
         msg: str | None = None, error: str | None = None):
    if user.role == UserRole.ADMIN:
        return RedirectResponse(url="/admin/documents", status_code=303)
    rows = docs.checklist(db, user.company)
    counts = {h: sum(1 for r in rows if r["health"] == h) for h in ("valid", "no_expiry", "expiring", "expired", "missing", "rejected")}
    ctx = build_portal_context(user, user.role, active_path="/account/documents")
    ctx.update({"rows": rows, "counts": counts, "score": docs.completeness(rows), "types": docs.DOC_TYPES,
                "history": {r["type"]: docs.history(db, user.company, r["type"]) for r in rows if r["doc"]},
                "status_labels": docs.STATUS_LABELS,
                "today": date.today(), "msg": msg, "error": error})
    return templates.TemplateResponse(request, "shared/documents.html", ctx)


@router.post("", name="my_documents_upload")
async def upload(request: Request, file: UploadFile | None = File(None), db: Session = Depends(get_db),
                 user: User = Depends(guard)):
    if user.role == UserRole.ADMIN or user.company is None:
        return _back(error="Admins manage documents from the admin portal.")
    form = await request.form()
    contents = await file.read() if file else b""
    try:
        doc = docs.upload(db, user.company, user, form, file.filename if file else "", contents)
    except docs.DocumentError as exc:
        db.rollback()
        return _back(error=str(exc))
    return _back(msg=f"{docs.DOC_TYPES[doc.doc_type]} v{doc.version} uploaded — pending review.")


@router.get("/{doc_id}", name="my_document_file")
def download(doc_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(guard)):
    doc = docs.get(db, doc_id, None if user.role == UserRole.ADMIN else user.company)
    if doc is None:
        return Response(status_code=404)
    try:
        return serve(doc, *docs.read(doc))
    except docs.DocumentError:
        return Response(status_code=404)
