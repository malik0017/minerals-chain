"""app/repositories/audit_log_repository.py"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from app.models.audit_log import AuditLog

def create(db: Session, entry: AuditLog) -> AuditLog:
    db.add(entry)
    db.flush()
    return entry


# Task #7: admin-facing audit log viewer — paginated, newest first, with
# the actor's user row eager-loaded (every row needs to show who did it).
# actor_user_id / action are optional filters for the page's own filter form.
def list_paginated(
    db: Session,
    page: int = 1,
    page_size: int = 50,
    actor_user_id=None,
    action: str | None = None,
) -> tuple[list[AuditLog], int]:
    query = select(AuditLog).options(joinedload(AuditLog.actor))
    count_query = select(func.count()).select_from(AuditLog)

    if actor_user_id is not None:
        query = query.where(AuditLog.actor_user_id == actor_user_id)
        count_query = count_query.where(AuditLog.actor_user_id == actor_user_id)
    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)

    total = db.execute(count_query).scalar_one()

    query = (
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list(db.execute(query).scalars().all())
    return rows, total


def distinct_actions(db: Session) -> list[str]:
    rows = db.execute(select(AuditLog.action).distinct().order_by(AuditLog.action)).scalars().all()
    return list(rows)
