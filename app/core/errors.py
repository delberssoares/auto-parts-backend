class AppError(Exception):
    """Erro de regra de negócio, devolvido ao cliente como {"detail": mensagem}."""

    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        headers: dict[str, str] | None = None,
        extra: dict | None = None,
    ):
        self.status_code = status_code
        self.message = message
        self.headers = headers
        self.extra = extra or {}