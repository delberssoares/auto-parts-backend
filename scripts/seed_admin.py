"""Cria (ou promove) um administrador.

Uso interativo (pede e-mail e senha no terminal):
    python -m scripts.seed_admin

Uso sem interação (automação), por variáveis de ambiente:
    ADMIN_EMAIL=... ADMIN_PASSWORD=... ADMIN_NAME=... python -m scripts.seed_admin
"""

import getpass
import os

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import User
from app.schemas.auth import Email, Name, NewPassword


def _read(env_var: str, prompt: str, secret: bool = False) -> str:
    value = os.getenv(env_var)
    if value:
        return value
    return getpass.getpass(prompt) if secret else input(prompt)


def main() -> None:
    try:
        email = TypeAdapter(Email).validate_python(_read("ADMIN_EMAIL", "E-mail do admin: "))
        name = TypeAdapter(Name).validate_python(os.getenv("ADMIN_NAME", "Admin"))
        password = TypeAdapter(NewPassword).validate_python(
            _read("ADMIN_PASSWORD", "Senha: ", secret=True)
        )
    except ValidationError as e:
        raise SystemExit(e.errors()[0]["msg"].removeprefix("Value error, "))

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user:
            user.role = "admin"
            db.commit()
            print(f"{email} agora é admin (senha mantida).")
            return

        db.add(User(name=name, email=email, password_hash=hash_password(password), role="admin"))
        db.commit()
        print(f"Admin criado: {email}")


if __name__ == "__main__":
    main()