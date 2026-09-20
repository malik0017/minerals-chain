"""
app/modules/shared/personalize/routes.py

Batch D. Same shape as /my-profile — one page, works for any logged-in
user regardless of role, using their own role as portal_role so the
sidebar still shows their normal nav (build_portal_context already
does this for /my-profile; same call here).

The page itself has no server-side state to manage — every control on
it is a client-side preference (see static/js/personalize.js) except
the LTR/RTL toggle, which is real account state and posts through the
existing /language/set endpoint (Batch C), not anything new here.
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
