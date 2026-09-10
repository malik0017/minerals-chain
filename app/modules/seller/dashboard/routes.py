"""
app/modules/seller/dashboard/routes.py
"""
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.permissions import require_active_portal
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.product import ProductStatus
from app.models.user import User, UserRole
from app.repositories import product_repository, rfq_repository

router = APIRouter(prefix="/seller", tags=["seller"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard", name="seller_dashboard")
def seller_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_active_portal(UserRole.SELLER)),
):
    context = build_portal_context(user, UserRole.SELLER, active_path=request.url.path)
    context["company"] = user.company
    # RFQ inbox is a broadcast/platform-wide feed (no per-seller scoping
    # exists — see rfq.py's docstring), so this count is the same for
    # every seller and for admin preview alike.
    context["open_rfq_count"] = rfq_repository.count_open(db)

    if user.company is not None:
        products = product_repository.list_for_company(db, user.company_id)
        context["listing_count"] = len(products)
        context["draft_count"] = sum(1 for p in products if p.status == ProductStatus.DRAFT)
        context["stats_are_platform_wide"] = False
    else:
        # Batch 8: admin previewing the Seller Portal has no company of
        # their own to show stats for — rather than hiding the summary
        # cards entirely (which read as "broken"/"nothing to see"),
        # show real platform-wide totals across every seller instead.
        context["listing_count"] = product_repository.count_all(db)
        context["draft_count"] = product_repository.count_by_status(db, ProductStatus.DRAFT)
        context["stats_are_platform_wide"] = True

    return templates.TemplateResponse(request, "seller/dashboard.html", context)
