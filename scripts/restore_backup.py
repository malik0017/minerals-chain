"""
scripts/restore_backup.py

    python scripts/restore_backup.py --list
    python scripts/restore_backup.py mc-20260929-020000 [--target-url postgresql://…] [--no-storage] --yes
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import backup_service  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--target-url")
    ap.add_argument("--no-storage", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()
    if args.list or not args.name:
        for d in sorted(backup_service.backup_root().iterdir(), reverse=True):
            if d.is_dir():
                print(d.name)
        return 0
    check = backup_service.verify(args.name)
    print(f"Checksums: {'OK' if check['ok'] else 'MISMATCH'} · schema {check['manifest']['alembic_revision']}")
    if not args.yes:
        print("Add --yes to overwrite the target database.")
        return 1
    backup_service.restore(args.name, target_url=args.target_url, with_storage=not args.no_storage)
    print("Restore complete. Run: alembic upgrade head")
    return 0


if __name__ == "__main__":
    sys.exit(main())
