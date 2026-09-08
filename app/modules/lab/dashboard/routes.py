"""app/modules/lab/dashboard/routes.py — see seller/dashboard/routes.py for the pattern."""
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates

from app.core.permissions import require_active_portal
from app.core.portal_nav import build_portal_context
from app.models.user import User, UserRole

router = APIRouter(prefix="/lab", tags=["lab"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard", name="lab_dashboard")
def lab_dashboard(
    request: Request,
    user: User = Depends(require_active_portal(UserRole.LAB)),
):
    context = build_portal_context(user, UserRole.LAB, active_path=request.url.path)
    context["company"] = user.company
    return templates.TemplateResponse(request, "lab/dashboard.html", context)
