"""
app/modules/admin/backups/routes.py
"""
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import require_admin
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.database.base import get_db
from app.models.audit_log import AuditLog
from app.models.backup import BackupRun
from app.models.user import User, UserRole
from app.services import backup_service, file_crypto

router = APIRouter(prefix="/admin/backups", tags=["admin-backups"])


def _back(msg=None, error=None):
    q = f"?error={quote(error)}" if error else (f"?msg={quote(msg)}" if msg else "")
    return RedirectResponse(url="/admin/backups" + q, status_code=303)


@router.get("", name="admin_backups")
def backups(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin("system")),
            msg: str | None = None, error: str | None = None):
    runs = db.query(BackupRun).order_by(BackupRun.started_at.desc()).limit(60).all()
    on_disk = {d.name for d in backup_service.backup_root().iterdir() if d.is_dir()}
    ok = [r for r in runs if r.status == "success"]
    ctx = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/backups")
    ctx.update({"runs": runs, "on_disk": on_disk, "last": ok[0] if ok else None, "msg": msg, "error": error,
                "keep": settings.BACKUP_KEEP, "backup_dir": str(backup_service.backup_root().resolve()),
                "storage": file_crypto.storage_status(), "encryption_on": file_crypto.enabled(),
                "sizes": [{"name": r.started_at.strftime("%m-%d"), "value": round((r.size_bytes or 0) / 1048576, 2)}
                          for r in reversed(ok[:30])]})
    return templates.TemplateResponse(request, "admin/backups.html", ctx)


@router.post("/run", name="admin_backup_run")
def run(db: Session = Depends(get_db), admin: User = Depends(require_admin("system"))):
    r = backup_service.run_backup(db, trigger="manual", user_id=admin.id)
    db.add(AuditLog(actor_user_id=admin.id, action="backup_run", target_type="user", target_id=admin.id,
                    details=f"{r.name}: {r.status}"))
    db.commit()
    if r.status != "success":
        return _back(error=f"Backup failed: {r.message}")
    return _back(msg=f"Backup {r.name} created ({round((r.size_bytes or 0) / 1048576, 2)} MB).")


@router.post("/{name}/verify", name="admin_backup_verify")
def verify(name: str, admin: User = Depends(require_admin("system"))):
    try:
        res = backup_service.verify(name)
    except (FileNotFoundError, KeyError, ValueError):
        return _back(error="Backup files not found.")
    return _back(msg=f"{name}: checksums verified.") if res["ok"] else _back(error=f"{name}: checksum mismatch.")


@router.get("/{name}/{part}", name="admin_backup_download")
def download(name: str, part: str, db: Session = Depends(get_db), admin: User = Depends(require_admin("system"))):
    p = backup_service.path_of(name, part)
    if p is None:
        return Response(status_code=404)
    db.add(AuditLog(actor_user_id=admin.id, action="backup_downloaded", target_type="user", target_id=admin.id,
                    details=f"{name}/{part}"))
    db.commit()
    return FileResponse(p, filename=f"{name}-{part}")


@router.post("/encrypt-storage", name="admin_encrypt_storage")
def encrypt_storage(db: Session = Depends(get_db), admin: User = Depends(require_admin("system"))):
    if not file_crypto.enabled():
        return _back(error="Set FILE_ENCRYPTION_KEY in .env first (scripts/harden_env.py generates one).")
    n = file_crypto.encrypt_all()
    db.add(AuditLog(actor_user_id=admin.id, action="storage_encrypted", target_type="user", target_id=admin.id,
                    details=f"{n} file(s)"))
    db.commit()
    return _back(msg=f"Encrypted {n} file(s).")
