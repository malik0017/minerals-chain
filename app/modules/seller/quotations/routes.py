"""app/modules/seller/quotations/routes.py — read-only list of the seller's own submitted quotations."""
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.permissions import require_seller_company
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.user import User, UserRole
from app.repositories import quotation_repository

router = APIRouter(prefix="/seller/quotations", tags=["seller-quotations"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", name="seller_quotations_index")
def quotations_index(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_seller_company),
):
    quotations = quotation_repository.list_for_seller_company(db, user.company_id)
    context = build_portal_context(user, UserRole.SELLER, active_path=request.url.path)
    context["quotations"] = quotations
    return templates.TemplateResponse(request, "seller/quotations_index.html", context)
