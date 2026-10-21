import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import (
    DUMMY_HASH,
    generate_reset_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models import PasswordResetRequest, PasswordResetToken, User

# Mesma mensagem para inválido, expirado e já usado
INVALID_LINK = "Este link é inválido ou expirou. Solicite um novo."


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def register_user(db: Session, name: str, email: str, password: str) -> User:
    if get_user_by_email(db, email):
        raise AppError(409, "Já existe uma conta com este e-mail.")

    user = User(
    name=name,
    email=email,
    password_hash=hash_password(password),
    role="customer",
    is_demo=settings.demo_reset_enabled,
)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # duas requisições simultâneas com o mesmo e-mail
        db.rollback()
        raise AppError(409, "Já existe uma conta com este e-mail.")
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    # Sempre confere um hash, existindo a conta ou não
    valid = verify_password(password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise AppError(401, "E-mail ou senha inválidos")
    return user


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.password_hash):
        raise AppError(400, "Senha atual incorreta.")
    if verify_password(new_password, user.password_hash):
        raise AppError(400, "A nova senha deve ser diferente da atual.")

    user.password_hash = hash_password(new_password)
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    db.commit()


# ---------- Recuperação de senha ----------
def request_password_reset(db: Session, email: str) -> tuple[str, str, bool] | None:
    """Devolve (nome, token, is_demo) se a conta existe, senão None."""
    now = _now()

    # Cooldown por e-mail, valendo também para contas inexistentes
    req = db.get(PasswordResetRequest, email)
    if req:
        elapsed = (now - req.requested_at).total_seconds()
        if elapsed < settings.reset_cooldown_seconds:
            retry = math.ceil(settings.reset_cooldown_seconds - elapsed)
            raise AppError(
                429,
                f"Aguarde {retry}s para solicitar um novo link.",
                headers={"Retry-After": str(retry)},
                extra={"retry_after": retry},
            )
        req.requested_at = now
    else:
        db.add(PasswordResetRequest(email=email, requested_at=now))

    user = get_user_by_email(db, email)
    result = None
    if user:
        # Um único link ativo por conta: o novo invalida os anteriores
        db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
        token = generate_reset_token()
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(token),  # só o hash vai para o banco
                expires_at=now + timedelta(minutes=settings.reset_token_ttl_minutes),
            )
        )
        result = (user.name, token, user.is_demo)

    db.commit()
    return result


def _find_valid_token(db: Session, token: str) -> PasswordResetToken:
    record = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_token(token),
            PasswordResetToken.expires_at > _now(),
        )
    )
    if not record:
        raise AppError(400, INVALID_LINK)
    return record


def _mask_email(email: str) -> str:
    local, domain = email.split("@")
    return f"{local[0]}{'*' * max(len(local) - 1, 2)}@{domain}"


def validate_reset_token(db: Session, token: str) -> str:
    record = _find_valid_token(db, token)
    user = db.get(User, record.user_id)
    if not user:
        raise AppError(400, INVALID_LINK)
    return _mask_email(user.email)


def reset_password(db: Session, token: str, new_password: str) -> tuple[str, str]:
    """Devolve (nome, e-mail) para o aviso de senha alterada."""
    record = _find_valid_token(db, token)
    user = db.get(User, record.user_id)
    if not user:
        raise AppError(400, INVALID_LINK)

    user.password_hash = hash_password(new_password)
    # Consome o token (uso único) e qualquer outro link pendente da conta
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    db.commit()
    return user.name, user.email