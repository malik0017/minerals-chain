"""
app/modules/seller/dashboard/routes.py

Batch E: redesigned in the InvestmentUX visual pattern (hero card,
stat tiles, status-breakdown donut, quick actions) — every number on
this page is real data from this seller's own company, computed here
by iterating what's already fetched rather than adding new
repository functions for counts that are cheap to derive in Python at
this data scale.

The donut only renders for a real company — admin previewing this
portal has no single company's listings to break down (see the
existing stats_are_platform_wide pattern below), so it shows a plain
note instead of a misleading or empty chart.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.donut_chart import build_donut
from app.core.permissions import require_active_portal
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.product import ProductStatus
from app.models.user import User, UserRole
from app.repositories import order_repository, product_repository, quotation_repository, rfq_repository

router = APIRouter(prefix="/seller", tags=["seller"])
from app.core.templates import templates

_STATUS_COLORS = {
    ProductStatus.DRAFT: "#6c757d",
    ProductStatus.UNDER_VERIFICATION: "#ffc107",
    ProductStatus.VERIFIED: "#198754",
    ProductStatus.FAILED_VERIFICATION: "#dc3545",
    ProductStatus.SUSPENDED: "#343a40",
}
_STATUS_LABELS = {
    ProductStatus.DRAFT: "Draft",
    ProductStatus.UNDER_VERIFICATION: "Under verification",
    ProductStatus.VERIFIED: "Verified",
    ProductStatus.FAILED_VERIFICATION: "Failed verification",
    ProductStatus.SUSPENDED: "Suspended",
}


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
        context["verified_count"] = sum(1 for p in products if p.status == ProductStatus.VERIFIED)
        context["stats_are_platform_wide"] = False

        orders = order_repository.list_for_seller_company(db, user.company_id)
        context["order_count"] = len(orders)
        context["orders_in_progress"] = sum(1 for o in orders if o.status.value != "completed")

        context["quotation_count"] = len(quotation_repository.list_for_seller_company(db, user.company_id))

        context["listing_donut"] = build_donut([
            (_STATUS_LABELS[status], sum(1 for p in products if p.status == status), _STATUS_COLORS[status])
            for status in ProductStatus
        ])
    else:
        # Batch 8: admin previewing the Seller Portal has no company of
        # their own to show stats for — rather than hiding the summary
        # cards entirely (which read as "broken"/"nothing to see"),
        # show real platform-wide totals across every seller instead.
        context["listing_count"] = product_repository.count_all(db)
        context["draft_count"] = product_repository.count_by_status(db, ProductStatus.DRAFT)
        context["verified_count"] = product_repository.count_by_status(db, ProductStatus.VERIFIED)
        context["stats_are_platform_wide"] = True
        context["order_count"] = None
        context["orders_in_progress"] = None
        context["quotation_count"] = None
        context["listing_donut"] = None

    return templates.TemplateResponse(request, "seller/dashboard.html", context)
