from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/infinityguard"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-secret"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    ml_service_url: str = "http://localhost:9000"
    cors_origins: str = "http://localhost:5173"
    frontend_url: str = "http://localhost:8080"
    public_app_url: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    gemini_api_key: str = ""
    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    payment_processor: str = "stripe"
    payment_provider_mode: str = "demo"
    demo_only: bool = False
    password_reset_preview: bool = False
    environment: str = "development"
    rate_limit_auth_per_minute: int = 10
    rate_limit_mutations_per_minute: int = 60
    compliance_provider: str = ""
    compliance_provider_url: str = ""
    compliance_provider_api_key: str = ""
    compliance_provider_timeout_seconds: float = 10
    max_collection_amount: float = 100000
    email_provider: str = "smtp"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_refresh_token: str = ""
    gmail_from_email: str = ""
    database_backups_configured: bool = False
    monitoring_configured: bool = False
    legal_review_completed: bool = False
    security_review_completed: bool = False
    restricted_pilot_enabled: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def active_gemini_key(self) -> str:
        return self.gemini_api_key or self.google_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
