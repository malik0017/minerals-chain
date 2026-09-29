"""
app/services/backup_service.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.backup import BackupRun

STORAGE = Path("storage")


class BackupError(RuntimeError):
    pass


def backup_root() -> Path:
    root = Path(settings.BACKUP_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _pg_tool(name: str) -> str:
    if settings.PG_BIN_DIR:
        exe = Path(settings.PG_BIN_DIR) / (name + (".exe" if os.name == "nt" else ""))
        return str(exe)
    found = shutil.which(name)
    if not found:
        raise BackupError(f"{name} not found — install PostgreSQL client tools or set PG_BIN_DIR.")
    return found


def _pg_env_args(url: str) -> tuple[dict, list[str]]:
    u = urlparse(url.replace("postgresql+psycopg2://", "postgresql://"))
    env = dict(os.environ)
    if u.password:
        env["PGPASSWORD"] = unquote(u.password)
    args = ["-h", u.hostname or "localhost", "-p", str(u.port or 5432), "-U", unquote(u.username or "postgres")]
    return env, args + [u.path.lstrip("/")]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_backup(db: Session, *, trigger: str = "manual", user_id=None) -> BackupRun:
    now = datetime.now(timezone.utc)
    name = f"mc-{now:%Y%m%d-%H%M%S}"
    run = BackupRun(started_at=now, name=name, status="running", trigger=trigger, triggered_by_user_id=user_id)
    db.add(run)
    db.commit()
    target = backup_root() / name
    try:
        target.mkdir(parents=True)
        env, args = _pg_env_args(settings.DATABASE_URL)
        dump = target / "db.dump"
        proc = subprocess.run([_pg_tool("pg_dump"), "-Fc", "--no-owner", "-f", str(dump)] + args,
                              env=env, capture_output=True, text=True, timeout=1800)
        if proc.returncode != 0:
            raise BackupError(proc.stderr.strip()[:500] or "pg_dump failed")
        files = 0
        with tarfile.open(target / "storage.tar.gz", "w:gz") as tar:
            if STORAGE.exists():
                for p in STORAGE.rglob("*"):
                    if p.is_file():
                        tar.add(p, arcname=str(p))
                        files += 1
        revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
        manifest = {"name": name, "created_at": now.isoformat(), "alembic_revision": revision, "files": files,
                    "db_sha256": _sha256(dump), "storage_sha256": _sha256(target / "storage.tar.gz"),
                    "encrypted_files": bool(settings.FILE_ENCRYPTION_KEY)}
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2))
        run.status = "success"
        run.db_sha256 = manifest["db_sha256"]
        run.files_count = files
        run.alembic_revision = revision
        run.size_bytes = sum(p.stat().st_size for p in target.iterdir())
        run.message = "Database + private storage"
    except Exception as exc:
        run.status = "failed"
        run.message = str(exc)[:1000]
        shutil.rmtree(target, ignore_errors=True)
    run.finished_at = datetime.now(timezone.utc)
    db.commit()
    prune()
    return run


def prune(keep: int | None = None) -> int:
    keep = keep or settings.BACKUP_KEEP
    dirs = sorted([d for d in backup_root().iterdir() if d.is_dir() and d.name.startswith("mc-")], reverse=True)
    removed = 0
    for d in dirs[keep:]:
        shutil.rmtree(d, ignore_errors=True)
        removed += 1
    return removed


def verify(name: str) -> dict:
    target = backup_root() / name
    manifest = json.loads((target / "manifest.json").read_text())
    ok_db = _sha256(target / "db.dump") == manifest["db_sha256"]
    ok_st = _sha256(target / "storage.tar.gz") == manifest["storage_sha256"]
    return {"db": ok_db, "storage": ok_st, "ok": ok_db and ok_st, "manifest": manifest}


def path_of(name: str, part: str) -> Path | None:
    if "/" in name or "\\" in name or ".." in name or part not in ("db.dump", "storage.tar.gz", "manifest.json"):
        return None
    p = backup_root() / name / part
    return p if p.is_file() else None


def restore(name: str, *, target_url: str | None = None, with_storage: bool = True) -> None:
    check = verify(name)
    if not check["ok"]:
        raise BackupError("Checksum mismatch — backup is damaged.")
    env, args = _pg_env_args(target_url or settings.DATABASE_URL)
    proc = subprocess.run([_pg_tool("pg_restore"), "--clean", "--if-exists", "--no-owner", "-d", args[-1]] + args[:-1]
                          + [str(backup_root() / name / "db.dump")], env=env, capture_output=True, text=True, timeout=3600)
    if proc.returncode not in (0, 1):
        raise BackupError(proc.stderr.strip()[:500])
    if with_storage:
        with tarfile.open(backup_root() / name / "storage.tar.gz", "r:gz") as tar:
            try:
                tar.extractall(".", filter="data")
            except TypeError:
                tar.extractall(".")


def last_success(db: Session) -> BackupRun | None:
    return db.query(BackupRun).filter(BackupRun.status == "success").order_by(BackupRun.started_at.desc()).first()


def checklist_item(db: Session) -> dict:
    last = last_success(db)
    age = (datetime.now(timezone.utc) - last.started_at) if last else None
    if last is None:
        level, detail = "warn", "No successful backup yet."
    elif age > timedelta(hours=26):
        level, detail = "warn", f"Last backup {last.started_at:%Y-%m-%d %H:%M} — older than a day."
    else:
        level, detail = "ok", f"Last backup {last.started_at:%Y-%m-%d %H:%M} · {round((last.size_bytes or 0) / 1048576, 1)} MB."
    return {"key": "backups", "level": level, "title": "Daily backups", "detail": detail,
            "fix": "Run a backup now and schedule scripts/backup.py daily.", "kind": "action" if level != "ok" else "none",
            "env": {}, "toggle": None, "link": "admin_backup_run" if level != "ok" else None}
