"""
app/modules/admin/monitoring/routes.py
"""
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.permissions import require_admin
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.database.base import get_db
from app.models.monitoring import ErrorEvent, JobRun
from app.models.user import User, UserRole
from app.services import job_service, monitoring_service as mon

router = APIRouter(prefix="/admin/monitoring", tags=["admin-monitoring"])


def _back(msg=None, error=None, anchor=""):
    q = f"?error={quote(error)}" if error else (f"?msg={quote(msg)}" if msg else "")
    return RedirectResponse(url="/admin/monitoring" + q + (f"#{anchor}" if anchor else ""), status_code=303)


@router.get("", name="admin_monitoring")
def index(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin("system")),
          hours: int = 24, msg: str | None = None, error: str | None = None):
    hours = hours if hours in (6, 24, 72, 168) else 24
    ctx = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/monitoring")
    ctx.update({"o": mon.overview(db, hours), "hours": hours, "health": mon.health(db),
                "errors": mon.recent_errors(db, 40),
                "open_errors": db.query(ErrorEvent).filter(ErrorEvent.resolved_at.is_(None)).count(),
                "jobs": job_service.status_rows(db),
                "runs": db.query(JobRun).order_by(JobRun.started_at.desc()).limit(25).all(),
                "msg": msg, "error": error})
    return templates.TemplateResponse(request, "admin/monitoring.html", ctx)


@router.post("/jobs/{name}/run", name="admin_job_run")
def run_job(name: str, db: Session = Depends(get_db), admin: User = Depends(require_admin("system"))):
    try:
        run = job_service.run(db, name, trigger="manual", user=admin)
    except job_service.JobError as exc:
        return _back(error=str(exc), anchor="jobs")
    label = job_service.JOBS[name][0]
    if run.status != "success":
        return _back(error=f"{label} failed: {run.message}", anchor="jobs")
    return _back(msg=f"{label}: {run.message}", anchor="jobs")


@router.post("/errors/{error_id}/resolve", name="admin_error_resolve")
def resolve(error_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin("system"))):
    e = db.get(ErrorEvent, error_id)
    if e is not None and e.resolved_at is None:
        e.resolved_at = datetime.now(timezone.utc)
        db.commit()
    return _back(msg="Marked resolved.", anchor="errors")


@router.post("/errors/resolve-all", name="admin_errors_resolve_all")
def resolve_all(db: Session = Depends(get_db), admin: User = Depends(require_admin("system"))):
    n = (db.query(ErrorEvent).filter(ErrorEvent.resolved_at.is_(None))
         .update({"resolved_at": datetime.now(timezone.utc)}, synchronize_session=False))
    db.commit()
    return _back(msg=f"{n} error(s) marked resolved.", anchor="errors")
