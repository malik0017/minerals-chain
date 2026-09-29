"""
app/modules/admin/reports/routes.py
"""
import csv
import io

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.permissions import require_admin
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.database.base import get_db
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
from app.services import analytics_service as an
from app.services import insights_service as ins

router = APIRouter(prefix="/admin/reports", tags=["admin-reports"])


@router.get("", name="admin_reports")
def reports(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin("reports")),
            start: str = "", end: str = ""):
    d0, d1 = an.parse_range(start, end)
    ctx = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/reports")
    ctx.update({"r": an.report(db, d0, d1), "start": d0.isoformat(), "end": d1.isoformat()})
    return templates.TemplateResponse(request, "admin/reports.html", ctx)


@router.get("/export.csv", name="admin_reports_csv")
def reports_csv(db: Session = Depends(get_db), admin: User = Depends(require_admin("reports")),
                start: str = "", end: str = ""):
    d0, d1 = an.parse_range(start, end)
    buf = io.StringIO()
    csv.writer(buf).writerows(an.report_csv_rows(an.report(db, d0, d1)))
    db.add(AuditLog(actor_user_id=admin.id, action="report_exported", target_type="user", target_id=admin.id, details=f"{d0}..{d1}"))
    db.commit()
    return Response(content="﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="minerals-chain-report-{d0}-{d1}.csv"'})


@router.get("/insights", name="admin_insights")
def insights(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin("reports")),
             tab: str = "prices", start: str = "", end: str = ""):
    d0, d1 = an.parse_range(start, end)
    tab = tab if tab in ins.TABS else "prices"
    ctx = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/reports/insights")
    ctx.update({"tab": tab, "tabs": ins.TABS, "d": ins.build(db, tab, d0, d1), "start": d0.isoformat(), "end": d1.isoformat()})
    return templates.TemplateResponse(request, "admin/insights.html", ctx)


@router.get("/insights.xlsx", name="admin_insights_xlsx")
def insights_xlsx(db: Session = Depends(get_db), admin: User = Depends(require_admin("reports")),
                  tab: str = "", start: str = "", end: str = ""):
    d0, d1 = an.parse_range(start, end)
    data = ins.workbook(db, d0, d1, [tab] if tab in ins.TABS else None)
    db.add(AuditLog(actor_user_id=admin.id, action="report_exported", target_type="user", target_id=admin.id,
                    details=f"xlsx {tab or 'all'} {d0}..{d1}"))
    db.commit()
    return Response(content=data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="minerals-chain-insights-{tab or "all"}-{d0}-{d1}.xlsx"'})
