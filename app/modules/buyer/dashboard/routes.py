"""app/modules/buyer/dashboard/routes.py — see seller/dashboard/routes.py for the pattern and reasoning."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.donut_chart import build_donut
from app.core.permissions import require_active_portal
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.rfq import RFQStatus
from app.models.user import User, UserRole
from app.repositories import order_repository, product_repository, rfq_repository

router = APIRouter(prefix="/buyer", tags=["buyer"])
from app.core.templates import templates

_RFQ_COLORS = {RFQStatus.OPEN: "#198754", RFQStatus.CLOSED: "#6c757d"}
_RFQ_LABELS = {RFQStatus.OPEN: "Open", RFQStatus.CLOSED: "Closed"}


@router.get("/dashboard", name="buyer_dashboard")
def buyer_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_active_portal(UserRole.BUYER)),
):
    context = build_portal_context(user, UserRole.BUYER, active_path=request.url.path)
    context["company"] = user.company
    # Batch 11: this is a platform-wide number for EVERY buyer (and
    # admin preview) alike — there's no "my listings" concept for a
    # buyer, unlike the seller/lab dashboards' company-scoped counts.
    context["verified_listing_count"] = len(product_repository.list_verified(db))

    if user.company is not None:
        rfqs = rfq_repository.list_for_company(db, user.company_id)
        context["my_rfq_count"] = len(rfqs)
        context["rfq_stats_are_platform_wide"] = False

        orders = order_repository.list_for_buyer_company(db, user.company_id)
        context["order_count"] = len(orders)
        context["orders_in_progress"] = sum(1 for o in orders if o.status.value != "completed")

        context["rfq_donut"] = build_donut([
            (_RFQ_LABELS[status], sum(1 for r in rfqs if r.status == status), _RFQ_COLORS[status])
            for status in RFQStatus
        ])
    else:
        context["my_rfq_count"] = rfq_repository.count_all(db)
        context["rfq_stats_are_platform_wide"] = True
        context["order_count"] = None
        context["orders_in_progress"] = None
        context["rfq_donut"] = None

    return templates.TemplateResponse(request, "buyer/dashboard.html", context)
