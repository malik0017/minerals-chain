"""
app/services/monitoring_service.py
"""
import os
import platform
import shutil
import threading
import time
import traceback as tb
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.monitoring import ErrorEvent, JobRun, RequestStat

SLOW_MS = 1000
FLUSH_SECONDS = 30
FLUSH_ROWS = 300
STARTED_AT = datetime.now(timezone.utc)
SKIP_PREFIXES = ("/static", "/assets", "/favicon", "/csp-report", "/healthz", "/sw.js", "/manifest.webmanifest")

_lock = threading.Lock()
_buf: dict = defaultdict(lambda: [0, 0, 0, 0, 0, 0])
_last_flush = time.monotonic()
enabled = os.environ.get("MC_METRICS", "1") != "0"


def _bucket(now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0)


def record(method: str, route: str, status: int, ms: float) -> None:
    global _last_flush
    if not enabled:
        return
    key = (_bucket(), method, route[:200])
    with _lock:
        row = _buf[key]
        row[0] += 1
        row[1] += 400 <= status < 500
        row[2] += status >= 500
        row[3] += int(ms)
        row[4] = max(row[4], int(ms))
        row[5] += ms >= SLOW_MS
        due = len(_buf) >= FLUSH_ROWS or time.monotonic() - _last_flush >= FLUSH_SECONDS
        if due:
            _last_flush = time.monotonic()
    if due:
        threading.Thread(target=flush, daemon=True).start()


def _drain() -> dict:
    global _buf
    with _lock:
        data, _buf = _buf, defaultdict(lambda: [0, 0, 0, 0, 0, 0])
    return data


def flush(db: Session | None = None) -> int:
    data = _drain()
    if not data:
        return 0
    own = db is None
    if own:
        from app.database.base import SessionLocal
        db = SessionLocal()
    try:
        for (bucket, method, route), (n, e4, e5, total, mx, slow) in data.items():
            stmt = insert(RequestStat).values(bucket=bucket, method=method, route=route, count=n, errors_4xx=e4,
                                              errors_5xx=e5, total_ms=total, max_ms=mx, slow=slow)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_request_stats_bucket_route",
                set_={"count": RequestStat.count + n, "errors_4xx": RequestStat.errors_4xx + e4,
                      "errors_5xx": RequestStat.errors_5xx + e5, "total_ms": RequestStat.total_ms + total,
                      "max_ms": func.greatest(RequestStat.max_ms, mx), "slow": RequestStat.slow + slow})
            db.execute(stmt)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        if own:
            db.close()
    return len(data)


def _user_from_scope(scope: dict):
    try:
        from http.cookies import SimpleCookie
        from app.core.auth import SESSION_COOKIE_NAME
        from app.core.security import decode_access_token
        raw = dict(scope.get("headers") or []).get(b"cookie", b"").decode("latin-1")
        morsel = SimpleCookie(raw).get(SESSION_COOKIE_NAME)
        return decode_access_token(morsel.value) if morsel else None
    except Exception:
        return None


def record_error(scope: dict, exc: BaseException, user_id=None) -> None:
    if not enabled:
        return
    route = getattr(scope.get("route"), "path", None)
    uid = user_id or _user_from_scope(scope)
    trace = "".join(tb.format_exception(type(exc), exc, exc.__traceback__))[-20000:]
    row = dict(occurred_at=datetime.now(timezone.utc), method=scope.get("method"), path=(scope.get("path") or "")[:500],
               route=route, status=500, error_type=f"{type(exc).__module__}.{type(exc).__name__}"[:200],
               message=str(exc)[:4000], traceback=trace)

    def _save():
        from app.database.base import SessionLocal
        db = SessionLocal()
        try:
            try:
                import uuid as _u
                row["user_id"] = _u.UUID(str(uid)) if uid else None
            except ValueError:
                row["user_id"] = None
            db.add(ErrorEvent(**row))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    t = threading.Thread(target=_save, daemon=True)
    t.start()
    t.join(timeout=2)


class MetricsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"].startswith(SKIP_PREFIXES):
            return await self.app(scope, receive, send)
        start = time.perf_counter()
        status = {"code": 500}

        async def _send(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, _send)
        except Exception as exc:
            status["code"] = 500
            record_error(scope, exc)
            raise
        finally:
            route = getattr(scope.get("route"), "path", None) or "(unmatched)"
            record(scope["method"], route, status["code"], (time.perf_counter() - start) * 1000)


def _dir_size(p: Path) -> int:
    total = 0
    if p.is_dir():
        for root, _, files in os.walk(p):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    return total


def health(db: Session) -> list[dict]:
    from app.core import rate_limit
    from app.core.config import settings
    from app.services import backup_service
    from app.services.control_center_service import system_health
    items = []
    t = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        ping = round((time.perf_counter() - t) * 1000, 1)
        size = db.execute(text("SELECT pg_database_size(current_database())")).scalar()
        items.append(("bi-database", "Database", f"{ping} ms · {size / 1048576:,.0f} MB", "ok" if ping < 50 else "warn"))
    except Exception as exc:
        db.rollback()
        items.append(("bi-database", "Database", str(exc)[:80], "fail"))
    sh = system_health(db)
    items.append(("bi-diagram-2", "Migrations", f"{sh['db_revision']}", "ok" if sh["migrations_ok"] else "fail"))
    rl = rate_limit.backend()
    items.append(("bi-lightning", "Rate-limit store", rl["name"], "ok" if rl["ok"] else "warn"))
    du = shutil.disk_usage(".")
    free = du.free / du.total
    items.append(("bi-hdd", "Disk free", f"{du.free / 1073741824:,.1f} GB ({free:.0%})", "ok" if free > 0.2 else "warn" if free > 0.1 else "fail"))
    items.append(("bi-folder", "Private storage", f"{_dir_size(Path('storage')) / 1048576:,.1f} MB", "ok"))
    last = backup_service.checklist_item(db)
    items.append(("bi-hdd-stack", "Backups", last["detail"][:60], last["level"] if last["level"] in ("ok", "warn", "fail") else "warn"))
    items.append(("bi-envelope", "Email", settings.EMAIL_MODE, "ok" if settings.EMAIL_MODE == "smtp" else "warn"))
    up = datetime.now(timezone.utc) - STARTED_AT
    items.append(("bi-clock-history", "Process uptime", f"{up.days}d {up.seconds // 3600}h {(up.seconds // 60) % 60}m", "ok"))
    items.append(("bi-cpu", "Runtime", f"Python {platform.python_version()} · pid {os.getpid()}", "ok"))
    return [{"icon": i, "label": label, "value": v, "level": lv} for i, label, v, lv in items]


def overview(db: Session, hours: int = 24) -> dict:
    flush(db)
    since = _bucket() - timedelta(hours=hours - 1)
    rows = db.query(RequestStat).filter(RequestStat.bucket >= since).all()
    keys = [since + timedelta(hours=i) for i in range(hours)]
    per_hour = {k: [0, 0, 0, 0] for k in keys}
    routes = defaultdict(lambda: [0, 0, 0, 0, 0])
    for r in rows:
        b = per_hour.setdefault(r.bucket, [0, 0, 0, 0])
        b[0] += r.count
        b[1] += r.errors_4xx
        b[2] += r.errors_5xx
        b[3] += r.total_ms
        x = routes[(r.method, r.route)]
        x[0] += r.count
        x[1] += r.total_ms
        x[2] = max(x[2], r.max_ms)
        x[3] += r.errors_5xx
        x[4] += r.slow
    total = sum(v[0] for v in per_hour.values())
    e5 = sum(v[2] for v in per_hour.values())
    e4 = sum(v[1] for v in per_hour.values())
    ms = sum(v[3] for v in per_hour.values())
    slowest = sorted(([m, r, n, round(t / n), mx, e, s] for (m, r), (n, t, mx, e, s) in routes.items() if n),
                     key=lambda x: -x[3])[:15]
    busiest = sorted(([m, r, n] for (m, r), (n, *_rest) in routes.items()), key=lambda x: -x[2])[:8]
    labels = [k.strftime("%H:00") for k in keys]
    return {
        "requests": total, "errors_5xx": e5, "errors_4xx": e4,
        "error_rate": round(100 * e5 / total, 2) if total else 0.0,
        "avg_ms": round(ms / total) if total else 0,
        "labels": labels,
        "series_requests": [{"name": "Requests", "data": [per_hour[k][0] for k in keys]}],
        "series_latency": [{"name": "Avg ms", "data": [round(per_hour[k][3] / per_hour[k][0]) if per_hour[k][0] else 0 for k in keys]}],
        "series_errors": [{"name": "4xx", "data": [per_hour[k][1] for k in keys]}, {"name": "5xx", "data": [per_hour[k][2] for k in keys]}],
        "slowest": slowest,
        "busiest": [{"name": f"{m} {r}", "value": n} for m, r, n in busiest],
    }


def recent_errors(db: Session, limit: int = 50, unresolved_only: bool = False):
    q = db.query(ErrorEvent)
    if unresolved_only:
        q = q.filter(ErrorEvent.resolved_at.is_(None))
    return q.order_by(ErrorEvent.occurred_at.desc()).limit(limit).all()


def prune(db: Session, keep_days: int = 90) -> int:
    cut = datetime.now(timezone.utc) - timedelta(days=keep_days)
    n = db.query(RequestStat).filter(RequestStat.bucket < cut).delete(synchronize_session=False)
    n += db.query(ErrorEvent).filter(ErrorEvent.occurred_at < cut, ErrorEvent.resolved_at.isnot(None)).delete(synchronize_session=False)
    n += db.query(JobRun).filter(JobRun.started_at < cut - timedelta(days=keep_days)).delete(synchronize_session=False)
    db.commit()
    return n
