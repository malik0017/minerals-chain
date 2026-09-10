"""
app/modules/buyer/browse/routes.py
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import uuid

from app.core.permissions import require_active_portal
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.user import User, UserRole
from app.repositories import product_repository

router = APIRouter(prefix="/buyer/browse", tags=["buyer-browse"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", name="buyer_browse_index")
def browse_index(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_active_portal(UserRole.BUYER)),
    q: str | None = None,
):
    products = product_repository.list_verified(db, search=q)
    context = build_portal_context(user, UserRole.BUYER, active_path=request.url.path)
    context.update({"products": products, "q": q or ""})
    return templates.TemplateResponse(request, "buyer/browse_index.html", context)


@router.get("/{product_id}", name="buyer_browse_detail")
def browse_detail(
    request: Request,
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_active_portal(UserRole.BUYER)),
):
    product = product_repository.get_verified_by_id(db, product_id)
    if product is None:
        return RedirectResponse(url=request.url_for("buyer_browse_index"), status_code=303)

    context = build_portal_context(user, UserRole.BUYER, active_path="/buyer/browse")
    context["product"] = product
    return templates.TemplateResponse(request, "buyer/browse_detail.html", context)
