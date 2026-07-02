from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy import inspect

from ..config import Settings


@dataclass
class ReadinessCheck:
    name: str
    ok: bool
    detail: str
    required_for: str

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "ok": self.ok,
            "detail": self.detail,
            "required_for": self.required_for,
        }


def _https(url: str) -> bool:
    return urlparse(url).scheme == "https"


def _email_configured(settings: Settings) -> bool:
    provider = settings.email_provider.strip().lower()
    if provider == "gmail_api":
        return bool(
            settings.gmail_client_id
            and settings.gmail_client_secret
            and settings.gmail_refresh_token
            and settings.gmail_from_email
        )
    return bool(settings.smtp_host and settings.smtp_from_email)


def _email_detail(settings: Settings) -> str:
    provider = settings.email_provider.strip().lower()
    if provider == "gmail_api":
        return "Gmail API recovery email configured" if _email_configured(settings) else "Gmail API client ID, client secret, refresh token, and from email are required"
    return "SMTP recovery email configured" if _email_configured(settings) else "SMTP is required for non-demo accounts"


def deployment_readiness(settings: Settings, engine) -> dict:
    compliance_provider = settings.compliance_provider.strip().lower()
    checks = [
        ReadinessCheck(
            "database",
            settings.database_url.startswith(("postgresql://", "postgresql+psycopg://")),
            "Managed PostgreSQL configured" if settings.database_url.startswith(("postgresql://", "postgresql+psycopg://")) else "Use PostgreSQL outside tests",
            "staging",
        ),
        ReadinessCheck(
            "jwt_secret",
            len(settings.jwt_secret) >= 32 and settings.jwt_secret not in {"dev-secret", "local-dev-change-me", "change-me-in-production"},
            "Strong JWT signing secret configured" if len(settings.jwt_secret) >= 32 else "JWT_SECRET must be at least 32 characters",
            "staging",
        ),
        ReadinessCheck(
            "frontend_https",
            settings.environment != "production" or _https(settings.frontend_url),
            "HTTPS frontend configured" if _https(settings.frontend_url) else "Production FRONTEND_URL must use HTTPS",
            "production",
        ),
        ReadinessCheck(
            "cors",
            settings.environment != "production" or all(_https(origin) for origin in settings.origins),
            "Explicit HTTPS origins configured" if settings.origins and all(_https(origin) for origin in settings.origins) else "Production CORS origins must be explicit HTTPS URLs",
            "production",
        ),
        ReadinessCheck(
            "password_reset",
            settings.demo_only or _email_configured(settings),
            _email_detail(settings),
            "production",
        ),
        ReadinessCheck(
            "gemini",
            settings.demo_only or bool(settings.active_gemini_key),
            "Gemini key configured" if settings.active_gemini_key else "GEMINI_API_KEY is required for the live Copilot",
            "production",
        ),
    ]

    if not settings.demo_only:
        checks.extend(
            [
                ReadinessCheck(
                    "processor_key",
                    settings.stripe_secret_key.startswith("sk_live_"),
                    "Live processor key configured" if settings.stripe_secret_key.startswith("sk_live_") else "A live processor key is required",
                    "live_money",
                ),
                ReadinessCheck(
                    "signed_webhook",
                    settings.stripe_webhook_secret.startswith("whsec_"),
                    "Signed webhook configured" if settings.stripe_webhook_secret.startswith("whsec_") else "A signed webhook secret is required",
                    "live_money",
                ),
                ReadinessCheck(
                    "compliance",
                    compliance_provider == "manual" or (compliance_provider == "http" and bool(settings.compliance_provider_url)),
                    "Manual compliance review gate configured" if compliance_provider == "manual" else "Compliance screening adapter configured" if compliance_provider == "http" and settings.compliance_provider_url else "Configure manual compliance review or the HTTP KYC/AML screening adapter",
                    "live_money",
                ),
                ReadinessCheck(
                    "database_backups",
                    settings.database_backups_configured,
                    "Database backups and restore drill are configured" if settings.database_backups_configured else "Configure managed PostgreSQL backups and a restore drill",
                    "production",
                ),
                ReadinessCheck(
                    "monitoring",
                    settings.monitoring_configured,
                    "Monitoring, uptime checks, and error alerts are configured" if settings.monitoring_configured else "Configure monitoring, uptime checks, and error alerts",
                    "production",
                ),
                ReadinessCheck(
                    "legal_review",
                    settings.legal_review_completed,
                    "Legal policies and merchant terms are signed off" if settings.legal_review_completed else "Complete terms, privacy, refund, dispute, data-retention, and jurisdiction review",
                    "production",
                ),
                ReadinessCheck(
                    "security_review",
                    settings.security_review_completed,
                    "Security review and payment-flow review are complete" if settings.security_review_completed else "Complete penetration test and payment-security review",
                    "production",
                ),
                ReadinessCheck(
                    "restricted_pilot",
                    settings.restricted_pilot_enabled,
                    "Restricted pilot mode is enabled" if settings.restricted_pilot_enabled else "Run live money through a restricted pilot before public launch",
                    "live_money",
                ),
            ]
        )

    try:
        tables = set(inspect(engine).get_table_names())
        migration_ok = "alembic_version" in tables
    except Exception:
        migration_ok = False
    checks.append(
        ReadinessCheck(
            "migrations",
            migration_ok,
            "Alembic schema version is present" if migration_ok else "Run alembic upgrade head",
            "staging",
        )
    )
    blocking = [check.as_dict() for check in checks if not check.ok]
    return {
        "mode": "demo" if settings.demo_only else "live",
        "ready": not blocking,
        "checks": [check.as_dict() for check in checks],
        "blocking": blocking,
    }
