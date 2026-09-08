"""app/repositories/audit_log_repository.py"""
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog

def create(db: Session, entry: AuditLog) -> AuditLog:
    db.add(entry)
    db.flush()
    return entry
