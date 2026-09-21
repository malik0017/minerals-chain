"""
app/modules/admin/audit_log/routes.py

Task #7: admin-facing audit log viewer. Shows every AuditLog row (which
Batch G already writes for company/passport approvals, user-account
admin actions, and — as of this batch — every completed login) with the
actor's name, the action, what it was performed on, and when.

Read-only: no POST endpoints, nothing here writes an AuditLog row itself.
"""
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.permissions import require_portal
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.user import User, UserRole
from app.repositories import audit_log_repository, user_repository

router = APIRouter(prefix="/admin/audit-log", tags=["admin-audit-log"])
from app.core.templates import templates

PAGE_SIZE = 50


@router.get("", name="admin_audit_log")
def audit_log_list(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_portal(UserRole.ADMIN)),
    page: int = 1,
    actor: str | None = None,
    action: str | None = None,
):
    page = max(1, page)

    actor_user_id = None
    if actor:
        try:
            actor_user_id = uuid.UUID(actor)
        except ValueError:
            actor_user_id = None

    rows, total = audit_log_repository.list_paginated(
        db, page=page, page_size=PAGE_SIZE, actor_user_id=actor_user_id, action=action or None,
    )
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    context = build_portal_context(admin, UserRole.ADMIN, active_path=request.url.path)
    context.update({
        "entries": rows,
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "actions": audit_log_repository.distinct_actions(db),
        "admins": [u for u in user_repository.list_all(db) if u.role == UserRole.ADMIN],
        "selected_actor": actor or "",
        "selected_action": action or "",
    })
    return templates.TemplateResponse(request, "admin/audit_log_list.html", context)
