"""
scripts/backup.py — run from cron / Task Scheduler:  python scripts/backup.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.models  
from app.database.base import SessionLocal  
from app.services import backup_service 


def main() -> int:
    db = SessionLocal()
    try:
        run = backup_service.run_backup(db, trigger="scheduled")
    finally:
        db.close()
    print(f"{run.name}: {run.status} {run.message or ''}")
    return 0 if run.status == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
