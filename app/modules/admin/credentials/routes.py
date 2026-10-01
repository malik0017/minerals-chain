"""
app/modules/admin/credentials/routes.py
"""
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.listing import paginate, qs
from app.core.permissions import require_admin
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.database.base import get_db
from app.models.company import Company
from app.models.credential_check import CHECK_KINDS, CHECK_RESULTS, CredentialCheck
from app.models.user import User, UserRole
from app.services import credential_check_service as ccs

router = APIRouter(prefix="/admin/credential-checks", tags=["admin-credentials"])


def _safe(back: str) -> str:
    return back if back.startswith("/admin/") else "/admin/credential-checks"


@router.get("", name="admin_credential_checks")
def index(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin("approvals")),
          result: str = "", kind: str = "", q: str = "", page: int = 1, msg: str | None = None, error: str | None = None):
    query = db.query(CredentialCheck).join(Company)
    if result:
        query = query.filter(CredentialCheck.result == result)
    if kind:
        query = query.filter(CredentialCheck.kind == kind)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(Company.company_name.ilike(like) | CredentialCheck.reference_number.ilike(like))
    rows, total, page, pages = paginate(query.order_by(CredentialCheck.created_at.desc()), page)
    ctx = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/credential-checks")
    ctx.update({"rows": rows, "total": total, "page": page, "pages": pages, "qs": qs(result=result, kind=kind, q=q),
                "f": {"result": result, "kind": kind, "q": q}, "s": ccs.stats(db), "kinds": CHECK_KINDS, "results": CHECK_RESULTS,
                "modes": {"cr": ccs.mode_for("cr"), "mining_license": ccs.mode_for("mining_license")}, "msg": msg, "error": error})
    return templates.TemplateResponse(request, "admin/credential_checks.html", ctx)


@router.post("/run-all", name="admin_credential_check_run_all")
def run_all(db: Session = Depends(get_db), admin: User = Depends(require_admin("approvals")), scope: str = Form("unchecked")):
    if all(ccs.mode_for(k) == "off" for k in CHECK_KINDS):
        return RedirectResponse(url=f"/admin/credential-checks?error={quote('Registry checks are switched off (WATHQ_MODE / MIM_MODE = off).')}", status_code=303)
    n = ccs.run_all(db, admin, only_unchecked=scope != "all")
    if not n["companies"]:
        text = "Every company already has a check. Use “Re-check all” to refresh them."
    else:
        text = f"Checked {n['companies']} compan{'y' if n['companies'] == 1 else 'ies'}: {n['checks']} check(s), {n['issues']} with issues."
    return RedirectResponse(url=f"/admin/credential-checks?msg={quote(text)}", status_code=303)


@router.post("/{company_id}/{kind}", name="admin_credential_check_run")
def run(company_id: uuid.UUID, kind: str, db: Session = Depends(get_db), admin: User = Depends(require_admin("approvals")),
        back: str = Form("/admin/credential-checks")):
    back = _safe(back)
    sep = "&" if "?" in back else "?"
    company = db.get(Company, company_id)
    if company is None:
        return RedirectResponse(url=f"{back}{sep}error={quote('Company not found.')}", status_code=303)
    try:
        c = ccs.run_check(db, company, kind, admin)
    except ccs.CredentialCheckError as exc:
        db.rollback()
        return RedirectResponse(url=f"{back}{sep}error={quote(str(exc))}", status_code=303)
    text = f"{CHECK_KINDS[kind]}: {CHECK_RESULTS[c.result]}" + (f" — {c.message}" if c.message else "")
    key = "msg" if c.result == "verified" else "error"
    return RedirectResponse(url=f"{back}{sep}{key}={quote(text)}", status_code=303)
