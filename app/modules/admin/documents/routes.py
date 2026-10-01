"""
app/modules/admin/documents/routes.py
"""
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.core.listing import paginate, qs
from app.core.permissions import require_admin
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.database.base import get_db
from app.models.user import User, UserRole
from app.modules.shared.document_library_routes import serve
from app.services import company_document_service as docs

router = APIRouter(prefix="/admin/documents", tags=["admin-documents"])


@router.get("", name="admin_documents")
def index(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin("companies")),
          status: str = "", health: str = "", type: str = "", q: str = "", page: int = 1,
          msg: str | None = None, error: str | None = None):
    rows, total, page, pages = paginate(docs.admin_listing(db, status=status, health_filter=health, doc_type=type, q=q), page)
    ctx = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/documents")
    ctx.update({"rows": rows, "total": total, "page": page, "pages": pages, "qs": qs(status=status, health=health, type=type, q=q),
                "f": {"status": status, "health": health, "type": type, "q": q}, "s": docs.admin_stats(db),
                "types": docs.DOC_TYPES, "status_labels": docs.STATUS_LABELS, "health_of": docs.health,
                "back": str(request.url.path) + ("?" + request.url.query if request.url.query else ""), "msg": msg, "error": error})
    return templates.TemplateResponse(request, "admin/documents.html", ctx)


@router.post("/{doc_id}/review", name="admin_document_review")
def review(doc_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin("companies")),
           decision: str = Form(...), note: str = Form(""), back: str = Form("/admin/documents")):
    back = back if back.startswith("/admin/documents") else "/admin/documents"
    sep = "&" if "?" in back else "?"
    doc = docs.get(db, doc_id)
    if doc is None:
        return RedirectResponse(url=f"{back}{sep}error={quote('Document not found.')}", status_code=303)
    try:
        docs.review(db, doc, admin, decision == "approve", note)
    except docs.DocumentError as exc:
        db.rollback()
        return RedirectResponse(url=f"{back}{sep}error={quote(str(exc))}", status_code=303)
    return RedirectResponse(url=f"{back}{sep}msg={quote(f'{doc.company.company_name}: {docs.DOC_TYPES.get(doc.doc_type)} {doc.status}.')}",
                            status_code=303)


@router.get("/{doc_id}", name="admin_document_view")
def view(doc_id: uuid.UUID, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin("companies")),
         msg: str | None = None, error: str | None = None):
    doc = docs.get(db, doc_id)
    if doc is None:
        return RedirectResponse(url=f"/admin/documents?error={quote('Document not found.')}", status_code=303)
    ctx = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/documents")
    ctx.update({"doc": doc, "company": doc.company, "file": docs.file_state(doc), "health": docs.health(doc),
                "history": docs.history(db, doc.company, doc.doc_type), "types": docs.DOC_TYPES,
                "status_labels": docs.STATUS_LABELS, "mime": docs.mime_of(doc),
                "back": f"/admin/documents/{doc.id}", "msg": msg, "error": error})
    return templates.TemplateResponse(request, "admin/document_view.html", ctx)


@router.get("/{doc_id}/file", name="admin_document_file")
def download(doc_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin("companies")),
             download: int = 0):
    doc = docs.get(db, doc_id)
    if doc is None:
        return RedirectResponse(url=f"/admin/documents?error={quote('Document not found.')}", status_code=303)
    try:
        return serve(doc, *docs.read(doc), download=bool(download))
    except docs.DocumentError as exc:
        return RedirectResponse(url=f"/admin/documents/{doc.id}?error={quote(str(exc))}", status_code=303)
