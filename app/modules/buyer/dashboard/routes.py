"""app/modules/buyer/dashboard/routes.py — see seller/dashboard/routes.py for the pattern."""
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.permissions import require_active_portal
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.user import User, UserRole
from app.repositories import product_repository

router = APIRouter(prefix="/buyer", tags=["buyer"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard", name="buyer_dashboard")
def buyer_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_active_portal(UserRole.BUYER)),
):
    context = build_portal_context(user, UserRole.BUYER, active_path=request.url.path)
    context["company"] = user.company
    context["verified_listing_count"] = len(product_repository.list_verified(db))
    return templates.TemplateResponse(request, "buyer/dashboard.html", context)
