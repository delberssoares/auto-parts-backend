import logging

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")


def send_email(to: str, subject: str, body: str, action_url: str | None = None) -> None:
    # TODO: trocar por um provedor real (Resend) na etapa de e-mail
    if settings.environment == "development":
        logger.info("E-MAIL para %s | %s\n%s\n%s", to, subject, body, action_url or "")
    else:
        logger.info("E-mail '%s' enfileirado para %s (provedor ainda não configurado)", subject, to)


def send_password_reset_email(name: str, email: str, token: str) -> None:
    link = f"{settings.frontend_url}/redefinir-senha?token={token}"
    send_email(
        to=email,
        subject="Redefinição de senha - Auto Parts",
        body=(
            f"Olá, {name}!\n\n"
            f"Recebemos um pedido para redefinir a senha da sua conta. "
            f"O link abaixo vale por {settings.reset_token_ttl_minutes} minutos e só pode ser usado uma vez.\n\n"
            f"Se você não fez esse pedido, ignore este e-mail: sua senha continua a mesma."
        ),
        action_url=link,
    )


def send_password_changed_email(name: str, email: str) -> None:
    send_email(
        to=email,
        subject="Sua senha foi alterada - Auto Parts",
        body=(
            f"Olá, {name}!\n\n"
            f"A senha da sua conta foi alterada com sucesso. "
            f"Se não foi você, redefina a senha novamente e entre em contato com o suporte."
        ),
    )