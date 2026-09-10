"""
app/modules/seller/dashboard/routes.py
"""
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates

from app.core.permissions import require_active_portal
from app.core.portal_nav import build_portal_context
from app.models.user import User, UserRole

router = APIRouter(prefix="/seller", tags=["seller"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard", name="seller_dashboard")
def seller_dashboard(
    request: Request,
    user: User = Depends(require_active_portal(UserRole.SELLER)),
):
    context = build_portal_context(user, UserRole.SELLER, active_path=request.url.path)
    context["company"] = user.company
    return templates.TemplateResponse(request, "seller/dashboard.html", context)
