"""
app/modules/shared/personalize/routes.py
"""
from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_required
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.models.user import User

router = APIRouter(tags=["personalize"])


@router.get("/personalize", name="personalize_page")
def personalize_page(request: Request, user: User = Depends(get_current_user_required)):
    context = build_portal_context(user, user.role, active_path="/personalize")
    return templates.TemplateResponse(request, "shared/personalize.html", context)
