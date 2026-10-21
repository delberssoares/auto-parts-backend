from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    frontend_url: str = "http://localhost:5173"
    environment: str = "development"  # development | production
    access_token_expire_minutes: int = 60 * 8
    reset_token_ttl_minutes: int = 30
    reset_cooldown_seconds: int = 60
    resend_api_key: str | None = None
    mail_from: str = "Auto Parts <onboarding@resend.dev>"
    log_emails: bool = False
    demo_reset_enabled: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("frontend_url")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @model_validator(mode="after")
    def _check_production(self) -> "Settings":
        if self.environment == "production" and len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY precisa ter ao menos 32 caracteres em produção")
        return self

    @property
    def cors_origins(self) -> list[str]:
        origins = [self.frontend_url]
        if self.environment != "production":
            origins.append("http://localhost:5173")
        return origins


settings = Settings()