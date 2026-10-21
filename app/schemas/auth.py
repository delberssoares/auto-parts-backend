import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _check_email(v: str) -> str:
    v = v.strip().lower()
    if len(v) > 255 or not EMAIL_RE.match(v):
        raise ValueError("E-mail inválido")
    return v


def _check_name(v: str) -> str:
    v = v.strip()
    if len(v) < 2:
        raise ValueError("Informe seu nome")
    if len(v) > 120:
        raise ValueError("Nome muito longo")
    return v


# Mesmas regras do passwordSchema.ts. O limite é em bytes, pois é o que o bcrypt aceita
def _check_new_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Use ao menos 8 caracteres")
    if len(v.encode("utf-8")) > 72:
        raise ValueError("Use no máximo 72 caracteres")
    if not re.search(r"[A-Za-z]", v):
        raise ValueError("Inclua ao menos uma letra")
    if not re.search(r"\d", v):
        raise ValueError("Inclua ao menos um número")
    return v


Email = Annotated[str, AfterValidator(_check_email)]
Name = Annotated[str, AfterValidator(_check_name)]
NewPassword = Annotated[str, AfterValidator(_check_new_password)]


class RegisterIn(BaseModel):
    name: Name
    email: Email
    password: NewPassword


class LoginIn(BaseModel):
    email: Email
    password: str  # no login não se valida a força, só se confere


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: NewPassword


class ForgotPasswordIn(BaseModel):
    email: Email


class TokenIn(BaseModel):
    token: str


class ResetPasswordIn(BaseModel):
    token: str
    password: NewPassword


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: Literal["admin", "customer"]


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class MessageOut(BaseModel):
    message: str


class MaskedEmailOut(BaseModel):
    email: str

class ForgotPasswordOut(BaseModel):
    message: str
    demo_reset_token: str | None = None