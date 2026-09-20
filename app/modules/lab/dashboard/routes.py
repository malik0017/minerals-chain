"""app/modules/lab/dashboard/routes.py — see seller/dashboard/routes.py for the pattern and reasoning."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.donut_chart import build_donut
from app.core.permissions import require_active_portal
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.user import User, UserRole
from app.models.verification import VerificationStatus
from app.repositories import verification_repository

router = APIRouter(prefix="/lab", tags=["lab"])
from app.core.templates import templates

_ACTIVE = (VerificationStatus.REQUESTED, VerificationStatus.SAMPLE_SCHEDULED, VerificationStatus.TESTING_IN_PROGRESS)

_STATUS_COLORS = {
    VerificationStatus.REQUESTED: "#ffc107",
    VerificationStatus.SAMPLE_SCHEDULED: "#0dcaf0",
    VerificationStatus.TESTING_IN_PROGRESS: "#0d6efd",
    VerificationStatus.COMPLETED: "#198754",
    VerificationStatus.FAILED: "#dc3545",
}
_STATUS_LABELS = {
    VerificationStatus.REQUESTED: "Requested",
    VerificationStatus.SAMPLE_SCHEDULED: "Sample scheduled",
    VerificationStatus.TESTING_IN_PROGRESS: "Testing in progress",
    VerificationStatus.COMPLETED: "Completed",
    VerificationStatus.FAILED: "Failed",
}


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
        context["completed_count"] = sum(1 for r in requests if r.status == VerificationStatus.COMPLETED)
        context["failed_count"] = sum(1 for r in requests if r.status == VerificationStatus.FAILED)
        context["stats_are_platform_wide"] = False

        context["verification_donut"] = build_donut([
            (_STATUS_LABELS[status], sum(1 for r in requests if r.status == status), _STATUS_COLORS[status])
            for status in VerificationStatus
        ])
    else:
        context["request_count"] = verification_repository.count_all(db)
        context["pending_count"] = verification_repository.count_active(db)
        context["completed_count"] = None
        context["failed_count"] = None
        context["stats_are_platform_wide"] = True
        context["verification_donut"] = None

    return templates.TemplateResponse(request, "lab/dashboard.html", context)
