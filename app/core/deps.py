from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    error = AppError(401, "Sessão inválida ou expirada.", headers={"WWW-Authenticate": "Bearer"})
    if creds is None:
        raise error
    user_id = decode_access_token(creds.credentials)
    if user_id is None:
        raise error
    user = db.get(User, user_id)
    if user is None:
        raise error
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise AppError(403, "Acesso restrito a administradores.")
    return user