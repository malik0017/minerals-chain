import getpass
import sys

from app.core.security import hash_password
from app.database.base import SessionLocal
from app.models.user import User, UserRole
from app.repositories import user_repository


def main() -> None:
    print("=== Minerals Chain — create an admin account ===")
    
    # Get input from user (remove default values from prompt)
    full_name = input("Full name: ").strip()
    email = input("Email: ").strip().lower()
    password = getpass.getpass("Password (min 8 chars): ")
    confirm = getpass.getpass("Confirm password: ")

    if not full_name or not email:
        print("Name and email are required.")
        sys.exit(1)
    if len(password) < 8:
        print("Password must be at least 8 characters.")
        sys.exit(1)
    if password != confirm:
        print("Passwords do not match.")
        sys.exit(1)

    db = SessionLocal()
    try:
        if user_repository.get_by_email(db, email):
            print(f"A user with email {email} already exists.")
            sys.exit(1)

        admin = User(
            company_id=None,
            full_name=full_name,
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        user_repository.create(db, admin)
        db.commit()
        print(f"\n✅ Admin account created: {email}")
        print("Log in at /login — you'll land on the approvals queue.")
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()