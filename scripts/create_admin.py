"""
scripts/create_admin.py — create the first super administrator on a fresh server

    python scripts/create_admin.py
    python scripts/create_admin.py --email it@mineralschain.sa --name "Platform Owner"
"""
import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.models  # noqa: E402,F401
from app.core.security import hash_password  # noqa: E402
from app.database.base import SessionLocal  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402

WEAK = {"admin123", "password", "12345678", "123456789", "qwerty123"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email")
    ap.add_argument("--name")
    args = ap.parse_args()
    email = (args.email or input("Admin email: ")).strip().lower()
    name = (args.name or input("Full name: ")).strip()
    if "@" not in email or not name:
        print("A valid email and name are required.")
        return 1
    pw = getpass.getpass("Password (min 12 chars): ")
    if len(pw) < 12 or pw.lower() in WEAK:
        print("Password too short or too common.")
        return 1
    if pw != getpass.getpass("Repeat password: "):
        print("Passwords do not match.")
        return 1
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is not None:
            if user.role != UserRole.ADMIN:
                print("That email belongs to a portal user.")
                return 1
            user.hashed_password, user.is_active, user.admin_role = hash_password(pw), True, "super_admin"
            action = "updated"
        else:
            db.add(User(company_id=None, full_name=name, email=email, hashed_password=hash_password(pw),
                        role=UserRole.ADMIN, is_active=True, admin_role="super_admin", company_role="owner"))
            action = "created"
        db.commit()
    finally:
        db.close()
    print(f"Super administrator {email} {action}. Sign in, then set up 2FA under My Profile.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
