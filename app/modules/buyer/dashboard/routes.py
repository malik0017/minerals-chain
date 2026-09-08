"""app/modules/buyer/dashboard/routes.py — see seller/dashboard/routes.py for the pattern."""
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates

from app.core.permissions import require_active_portal
from app.core.portal_nav import build_portal_context
from app.models.user import User, UserRole

router = APIRouter(prefix="/buyer", tags=["buyer"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard", name="buyer_dashboard")
def buyer_dashboard(
    request: Request,
    user: User = Depends(require_active_portal(UserRole.BUYER)),
):
    context = build_portal_context(user, UserRole.BUYER, active_path=request.url.path)
    context["company"] = user.company
    return templates.TemplateResponse(request, "buyer/dashboard.html", context)
