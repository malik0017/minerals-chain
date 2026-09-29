"""
app/modules/shared/erp_export_views.py
"""
from datetime import date
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session
from starlette.datastructures import FormData

from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.models.audit_log import AuditLog
from app.models.company import Company
from app.models.erp_export import ErpExportRun
from app.models.user import User, UserRole
from app.services import erp_export_service as erp
from app.services import private_files


def _date(v):
    try:
        return date.fromisoformat(v) if v else None
    except ValueError:
        return None


def back(base: str, msg=None, error=None):
    q = f"?error={quote(error)}" if error else (f"?msg={quote(msg)}" if msg else "")
    return RedirectResponse(url=base + q, status_code=303)


def _runs(db: Session, scope: Company | None):
    q = db.query(ErpExportRun)
    q = q.filter(ErpExportRun.scope_company_id == scope.id) if scope else q
    return q.order_by(ErpExportRun.created_at.desc()).limit(50).all()


def page(request: Request, db: Session, user: User, role: UserRole, base: str, scope: Company | None,
         msg: str | None, error: str | None):
    runs = _runs(db, scope)
    datasets = {k: v for k, v in erp.DATASETS.items() if not (scope and k in erp.PLATFORM_ONLY)}
    totals: dict[str, int] = {}
    for r in runs:
        for k, v in (r.row_counts or {}).items():
            totals[k] = totals.get(k, 0) + int(v)
    ctx = build_portal_context(user, role, active_path=base)
    ctx.update({"runs": runs, "targets": erp.TARGETS, "datasets": datasets, "base": base, "scope": scope,
                "by_target": [{"name": erp.TARGETS[t].split(" (")[0], "value": sum(1 for r in runs if r.target == t)}
                              for t in erp.TARGETS],
                "by_dataset": [{"name": datasets.get(k, k), "value": v} for k, v in totals.items()],
                "last": runs[0] if runs else None, "today": date.today().isoformat(),
                "month_start": date.today().replace(day=1).isoformat(), "msg": msg, "error": error})
    return templates.TemplateResponse(request, "shared/erp_export.html", ctx)


def build(db: Session, user: User, base: str, scope: Company | None, form: FormData):
    try:
        run = erp.build(db, target=form.get("target", ""), datasets=form.getlist("datasets"),
                        start=_date(form.get("start")), end=_date(form.get("end")), scope=scope, user=user)
    except erp.ErpExportError as exc:
        return back(base, error=str(exc))
    return back(base, msg=f"Export ready — {sum(run.row_counts.values())} rows.")


def download(db: Session, user: User, run_id, scope: Company | None):
    q = db.query(ErpExportRun).filter(ErpExportRun.id == run_id)
    if scope:
        q = q.filter(ErpExportRun.scope_company_id == scope.id)
    run = q.first()
    if run is None or not run.file_path:
        return Response(status_code=404)
    try:
        data, intact = private_files.read_verified(run.file_path, run.file_sha256)
    except private_files.FileError:
        return Response(status_code=404)
    db.add(AuditLog(actor_user_id=user.id, action="erp_export_downloaded", target_type="company",
                    target_id=scope.id if scope else user.id, details=f"{run.id}{'' if intact else ' (checksum mismatch)'}"))
    db.commit()
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{erp.filename(run)}"'})
