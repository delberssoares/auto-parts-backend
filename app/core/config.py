from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    frontend_url: str = "http://localhost:5173"
    environment: str = "development"  # development | production
    access_token_expire_minutes: int = 60 * 8
    reset_token_ttl_minutes: int = 30
    reset_cooldown_seconds: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()