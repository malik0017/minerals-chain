"""
scripts/run_scheduled_jobs.py

    python scripts/run_scheduled_jobs.py --due          # cron: */15 * * * *
    python scripts/run_scheduled_jobs.py --job backup
    python scripts/run_scheduled_jobs.py --all
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.base import SessionLocal  # noqa: E402
from app.services import job_service  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--due", action="store_true")
    g.add_argument("--all", action="store_true")
    g.add_argument("--job", choices=sorted(job_service.JOBS))
    g.add_argument("--list", action="store_true")
    args = ap.parse_args()
    db = SessionLocal()
    try:
        if args.list:
            for r in job_service.status_rows(db):
                last = r["last"]
                print(f"{r['key']:<24} every {r['every_h']:>2}h  {r['health']:<4}  "
                      f"{last.started_at:%Y-%m-%d %H:%M} {last.status}" if last else f"{r['key']:<24} never run")
            return 0
        names = [args.job] if args.job else list(job_service.JOBS) if args.all else job_service.due(db)
        failed = 0
        for name in names:
            run = job_service.run(db, name, trigger="cli" if not args.due else "schedule")
            failed += run.status != "success"
            print(f"{run.status.upper():<8} {name:<24} {run.duration_s or 0:6.2f}s  {run.message or ''}")
        if not names:
            print("Nothing due.")
        return 1 if failed else 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
