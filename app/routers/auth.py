from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.db.session import get_db
from app.models import User
from app.schemas.auth import (
    ChangePasswordIn,
    ForgotPasswordIn,
    LoginIn,
    MaskedEmailOut,
    MessageOut,
    RegisterIn,
    ResetPasswordIn,
    TokenIn,
    TokenOut,
    UserOut,
)
from app.services import auth_service, mail_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    user = auth_service.register_user(db, data.name, data.email, data.password)
    return _token_response(user)


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = auth_service.authenticate(db, data.email, data.password)
    return _token_response(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password", status_code=204)
def change_password(
    data: ChangePasswordIn,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    name, email = user.name, user.email
    auth_service.change_password(db, user, data.current_password, data.new_password)
    background.add_task(mail_service.send_password_changed_email, name, email)


@router.post("/forgot-password", response_model=MessageOut, status_code=202)
def forgot_password(
    data: ForgotPasswordIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    result = auth_service.request_password_reset(db, data.email)
    if result:
        name, token = result
        background.add_task(mail_service.send_password_reset_email, name, data.email, token)
    # Mesma resposta exista ou não a conta
    return MessageOut(message="Se existir uma conta com este e-mail, enviaremos o link de redefinição.")


@router.post("/reset-password/validate", response_model=MaskedEmailOut)
def validate_reset_token(data: TokenIn, db: Session = Depends(get_db)):
    return MaskedEmailOut(email=auth_service.validate_reset_token(db, data.token))


@router.post("/reset-password", status_code=204)
def reset_password(
    data: ResetPasswordIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> None:
    name, email = auth_service.reset_password(db, data.token, data.password)
    background.add_task(mail_service.send_password_changed_email, name, email)