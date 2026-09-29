"""
scripts/load_master_data.py — Batch I

USAGE
    python scripts/load_master_data.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.base import SessionLocal  
import app.models  
from app.services.master_data.starter_data import load_starter_data  


def main() -> int:
    db = SessionLocal()
    try:
        results = load_starter_data(db)
    finally:
        db.close()
    failed = 0
    for key, r in results.items():
        print(f"  {key:<22} created {r.created:>3}  updated {r.updated:>3}  errors {len(r.errors)}")
        for e in r.errors:
            print(f"      ! {e}")
        failed += len(r.errors)
    print("\nDone." if not failed else f"\n{failed} row error(s).")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
