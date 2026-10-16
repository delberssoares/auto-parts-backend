import os

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import User

EMAIL = os.getenv("ADMIN_EMAIL", "admin@autoparts.com")
PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin1234")


def main() -> None:
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == EMAIL)):
            print(f"Admin {EMAIL} já existe.")
            return
        db.add(User(name="Admin", email=EMAIL, password_hash=hash_password(PASSWORD), role="admin"))
        db.commit()
        print(f"Admin criado: {EMAIL}")


if __name__ == "__main__":
    main()