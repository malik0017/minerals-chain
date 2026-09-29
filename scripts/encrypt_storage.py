"""
scripts/encrypt_storage.py

    python scripts/encrypt_storage.py            encrypt every plaintext file under storage/
    python scripts/encrypt_storage.py --status
    python scripts/encrypt_storage.py --rotate OLD_KEY   re-encrypt with the current FILE_ENCRYPTION_KEY
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.services import file_crypto  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--rotate", metavar="OLD_KEY")
    args = ap.parse_args()
    if args.status:
        print(file_crypto.storage_status())
        return 0
    if not settings.FILE_ENCRYPTION_KEY:
        print("FILE_ENCRYPTION_KEY is not set — run scripts/harden_env.py first.")
        return 1
    if args.rotate:
        print(f"Re-encrypted {file_crypto.rotate(args.rotate, settings.FILE_ENCRYPTION_KEY)} file(s).")
    else:
        print(f"Encrypted {file_crypto.encrypt_all()} file(s).")
    print(file_crypto.storage_status())
    return 0


if __name__ == "__main__":
    sys.exit(main())
