"""
app/modules/shared/api_token_routes.py
"""
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.datastructures import FormData

from app.core.auth import get_current_user_required
from app.core.config import settings
from app.core.forms import form_data
from app.core.permissions import require_admin
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.database.base import get_db
from app.models.api_token import API_SCOPES, ApiToken
from app.models.user import User, UserRole
from app.services import api_token_service as svc

router = APIRouter(tags=["api-tokens"])


def _back(url, msg=None, error=None):
    q = f"?error={quote(error)}" if error else (f"?msg={quote(msg)}" if msg else "")
    return RedirectResponse(url=url + q, status_code=303)


@router.get("/account/api-tokens", name="my_api_tokens")
def page(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user_required),
         msg: str | None = None, error: str | None = None):
    ctx = build_portal_context(user, user.role, active_path="/account/api-tokens")
    ctx.update({"tokens": svc.for_user(db, user), "scopes": API_SCOPES, "expiries": svc.EXPIRY_CHOICES,
                "new_token": request.cookies.get("mc_new_token"), "base_url": settings.PUBLIC_BASE_URL.rstrip("/"),
                "msg": msg, "error": error})
    resp = templates.TemplateResponse(request, "shared/api_tokens.html", ctx)
    resp.delete_cookie("mc_new_token", path="/account/api-tokens")
    resp.headers["Cache-Control"] = "no-store"
    return resp


@router.post("/account/api-tokens", name="my_api_token_create")
def create(db: Session = Depends(get_db), user: User = Depends(get_current_user_required), form: FormData = Depends(form_data)):
    try:
        token, raw = svc.issue(db, user, form.get("name", ""), form.getlist("scopes"), form.get("expiry", "90"))
    except svc.ApiTokenError as exc:
        db.rollback()
        return _back("/account/api-tokens", error=str(exc))
    resp = _back("/account/api-tokens", msg=f"Token “{token.name}” created — copy it now, it won't be shown again.")
    resp.set_cookie("mc_new_token", raw, max_age=120, httponly=True, samesite="strict", path="/account/api-tokens",
                    secure=settings.cookie_secure_effective)
    return resp


@router.post("/account/api-tokens/{token_id}/revoke", name="my_api_token_revoke")
def revoke(token_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user_required)):
    t = svc.get_owned(db, token_id, user)
    if t is None:
        return _back("/account/api-tokens", error="Token not found.")
    svc.revoke(db, t, user)
    return _back("/account/api-tokens", msg=f"Token “{t.name}” revoked.")


@router.get("/admin/api-tokens", name="admin_api_tokens")
def admin_page(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin("system")),
               msg: str | None = None, error: str | None = None):
    tokens = db.query(ApiToken).order_by(ApiToken.created_at.desc()).limit(300).all()
    ctx = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/api-tokens")
    by_role: dict = {}
    for t in tokens:
        if t.is_active:
            by_role[t.user.role.value] = by_role.get(t.user.role.value, 0) + 1
    ctx.update({"tokens": tokens, "active": sum(1 for t in tokens if t.is_active),
                "used_week": sum(1 for t in tokens if t.last_used_at and (t.is_active)),
                "by_role": [{"name": k.title(), "value": v} for k, v in by_role.items()], "msg": msg, "error": error})
    return templates.TemplateResponse(request, "admin/api_tokens.html", ctx)


@router.post("/admin/api-tokens/{token_id}/revoke", name="admin_api_token_revoke")
def admin_revoke(token_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin("system"))):
    t = svc.get_owned(db, token_id, None)
    if t is None:
        return _back("/admin/api-tokens", error="Token not found.")
    svc.revoke(db, t, admin)
    return _back("/admin/api-tokens", msg=f"Token “{t.name}” revoked.")
