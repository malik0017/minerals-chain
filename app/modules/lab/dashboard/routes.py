"""app/modules/lab/dashboard/routes.py — see seller/dashboard/routes.py for the pattern."""
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.permissions import require_active_portal
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.user import User, UserRole
from app.models.verification import VerificationStatus
from app.repositories import verification_repository

router = APIRouter(prefix="/lab", tags=["lab"])
templates = Jinja2Templates(directory="app/templates")

_ACTIVE = (VerificationStatus.REQUESTED, VerificationStatus.SAMPLE_SCHEDULED, VerificationStatus.TESTING_IN_PROGRESS)


@router.get("/dashboard", name="lab_dashboard")
def lab_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_active_portal(UserRole.LAB)),
):
    context = build_portal_context(user, UserRole.LAB, active_path=request.url.path)
    context["company"] = user.company

    if user.company is not None:
        requests = verification_repository.list_for_lab_company(db, user.company_id)
        context["request_count"] = len(requests)
        context["pending_count"] = sum(1 for r in requests if r.status in _ACTIVE)
        context["stats_are_platform_wide"] = False
    else:
        # Batch 8: admin previewing the Lab Portal — platform-wide
        # totals across every lab, same reasoning as the seller
        # dashboard (see its routes.py comment).
        context["request_count"] = verification_repository.count_all(db)
        context["pending_count"] = verification_repository.count_active(db)
        context["stats_are_platform_wide"] = True

    return templates.TemplateResponse(request, "lab/dashboard.html", context)
