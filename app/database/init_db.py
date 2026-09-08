"""
app/database/init_db.py
"""

from sqlalchemy import text
from app.database.base import engine

def check_connection() -> None:
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version();")).scalar_one()
        print(f"Connected to PostgreSQL: {version}")


if __name__ == "__main__":
    check_connection()
