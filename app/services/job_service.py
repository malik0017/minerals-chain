"""
app/services/job_service.py
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.monitoring import JobRun
from app.models.user import User


def _subscriptions(db):
    from app.services import subscription_service
    stats = subscription_service.run_lifecycle(db)
    return sum(stats.values()), ", ".join(f"{k} {v}" for k, v in stats.items())


def _quotations(db):
    from app.services import quotation_service
    n = quotation_service.expire_stale(db)
    db.commit()
    return n, f"{n} quotation(s) expired"


def _documents(db):
    from app.services import company_document_service
    n = company_document_service.send_expiry_reminders(db)
    return n, f"{n} reminder(s) sent"


def _backup(db):
    from app.services import backup_service
    r = backup_service.run_backup(db, trigger="schedule")
    if r.status != "success":
        raise RuntimeError(r.message or "backup failed")
    return 1, f"{r.name} ({(r.size_bytes or 0) / 1048576:.2f} MB)"


def _metrics(db):
    from app.services import monitoring_service
    flushed = monitoring_service.flush(db)
    pruned = monitoring_service.prune(db)
    return flushed + pruned, f"{flushed} bucket(s) flushed, {pruned} old row(s) pruned"


def _late_shipments(db):
    from app.models.shipment import OPEN_STATUSES, Shipment
    from app.services import notification_service
    now = datetime.now(timezone.utc)
    late = db.query(Shipment).filter(Shipment.status.in_(OPEN_STATUSES), Shipment.eta < now,
                                     Shipment.eta >= now - timedelta(hours=24)).all()
    for s in late:
        notification_service.notify_company(db, s.seller_company, "shipment_late", f"Shipment {s.reference} is past its ETA",
                                            "Post a tracking update or a new ETA for the buyer.",
                                            action_url=f"/seller/orders/{s.order_id}", shipment=s.reference)
    db.commit()
    return len(late), f"{len(late)} late shipment alert(s)"


JOBS = {
    "subscription_lifecycle": ("Subscription lifecycle", "bi-stars", 24, _subscriptions),
    "quotation_expiry": ("Quotation expiry", "bi-tags", 1, _quotations),
    "document_reminders": ("Document expiry reminders", "bi-folder2-open", 24, _documents),
    "late_shipments": ("Late shipment alerts", "bi-truck", 24, _late_shipments),
    "backup": ("Database & storage backup", "bi-hdd-stack", 24, _backup),
    "metrics_maintenance": ("Metrics flush & retention", "bi-activity", 6, _metrics),
}


class JobError(ValueError):
    pass


def run(db: Session, name: str, *, trigger: str = "schedule", user: User | None = None) -> JobRun:
    if name not in JOBS:
        raise JobError(f"Unknown job: {name}")
    run = JobRun(job=name, trigger=trigger, started_at=datetime.now(timezone.utc), status="running",
                 triggered_by_user_id=user.id if user else None)
    db.add(run)
    db.commit()
    try:
        items, message = JOBS[name][3](db)
        run.status, run.items, run.message = "success", items, message
    except Exception as exc:
        db.rollback()
        run = db.merge(run)
        run.status, run.message = "failed", f"{type(exc).__name__}: {exc}"[:2000]
    run.finished_at = datetime.now(timezone.utc)
    if user:
        db.add(AuditLog(actor_user_id=user.id, action="job_run", target_type="user", target_id=user.id,
                        details=f"{name}: {run.status}"))
    db.commit()
    return run


def last_runs(db: Session) -> dict:
    sub = (db.query(JobRun.job, func.max(JobRun.started_at).label("m")).group_by(JobRun.job).subquery())
    rows = db.query(JobRun).join(sub, (JobRun.job == sub.c.job) & (JobRun.started_at == sub.c.m)).all()
    return {r.job: r for r in rows}


def due(db: Session, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    last = {}
    for job, at in db.query(JobRun.job, func.max(JobRun.started_at)).filter(JobRun.status == "success").group_by(JobRun.job).all():
        last[job] = at
    return [k for k, (_, _, hours, _) in JOBS.items() if k not in last or now - last[k] >= timedelta(hours=hours) - timedelta(minutes=5)]


def status_rows(db: Session) -> list[dict]:
    last = last_runs(db)
    now = datetime.now(timezone.utc)
    rows = []
    for key, (label, icon, hours, _) in JOBS.items():
        r = last.get(key)
        overdue = r is None or now - r.started_at > timedelta(hours=hours * 2)
        rows.append({"key": key, "label": label, "icon": icon, "every_h": hours, "last": r,
                     "health": "fail" if r and r.status == "failed" else "warn" if overdue else "ok"})
    return rows
