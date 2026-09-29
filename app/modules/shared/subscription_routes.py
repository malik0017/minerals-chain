"""
app/modules/shared/subscription_routes.py
"""
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.permissions import require_active_portal
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.database.base import get_db
from app.models.md_commercial import SubscriptionPlan
from app.models.user import User, UserRole
from app.services import subscription_service as subs

router = APIRouter(prefix="/account/subscription", tags=["subscription"])


@router.get("", name="my_subscription")
def page(request: Request, db: Session = Depends(get_db),
         user: User = Depends(require_active_portal(UserRole.SELLER, UserRole.BUYER)),
         msg: str | None = None, error: str | None = None):
    if user.role == UserRole.ADMIN:
        return RedirectResponse(url=request.url_for("admin_subscriptions"), status_code=303)
    subs.run_lifecycle(db)
    info = subs.status_info(db, user.company)
    plans = db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active.is_(True)).order_by(SubscriptionPlan.sort_order).all()
    context = build_portal_context(user, user.role, active_path="/account/subscription")
    context.update({"info": info, "plans": plans, "company": user.company, "msg": msg, "error": error,
                    "is_seller": user.role == UserRole.SELLER, "tier_order": subs.TIER_ORDER,
                    "can_change": user.company_role in ("owner", "manager")})
    return templates.TemplateResponse(request, "shared/subscription.html", context)


@router.post("/change", name="my_subscription_change")
def change(request: Request, db: Session = Depends(get_db),
           user: User = Depends(require_active_portal(UserRole.SELLER, UserRole.BUYER)), tier: str = Form(...)):
    back = str(request.url_for("my_subscription"))
    if user.role == UserRole.ADMIN or user.company_role not in ("owner", "manager"):
        return RedirectResponse(url=f"{back}?error={quote('Only the company owner or a manager can change the plan.')}", status_code=303)
    try:
        subs.change_plan(db, user.company, tier, user)
    except subs.SubscriptionError as exc:
        db.rollback()
        return RedirectResponse(url=f"{back}?error={quote(str(exc))}", status_code=303)
    return RedirectResponse(url=f"{back}?msg={quote('Plan changed — effective immediately.')}", status_code=303)


@router.post("/renew", name="my_subscription_renew")
def renew(request: Request, db: Session = Depends(get_db),
          user: User = Depends(require_active_portal(UserRole.SELLER, UserRole.BUYER))):
    back = str(request.url_for("my_subscription"))
    if user.role == UserRole.ADMIN or user.company_role not in ("owner", "manager"):
        return RedirectResponse(url=f"{back}?error={quote('Only the company owner or a manager can renew.')}", status_code=303)
    try:
        subs.renew(db, user.company, user)
    except subs.SubscriptionError as exc:
        db.rollback()
        return RedirectResponse(url=f"{back}?error={quote(str(exc))}", status_code=303)
    return RedirectResponse(url=f"{back}?msg={quote('Renewed for 12 months.')}", status_code=303)
