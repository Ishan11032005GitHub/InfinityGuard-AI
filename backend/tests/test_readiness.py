from app.config import Settings
from app.services.readiness import deployment_readiness


class Inspector:
    def get_table_names(self):
        return ["alembic_version"]


def test_live_readiness_fails_closed_without_payment_and_compliance(monkeypatch):
    monkeypatch.setattr("app.services.readiness.inspect", lambda _engine: Inspector())
    settings = Settings(
        _env_file=None,
        environment="production",
        demo_only=False,
        database_url="postgresql+psycopg://example",
        jwt_secret="x" * 40,
        frontend_url="https://app.example.com",
        cors_origins="https://app.example.com",
        smtp_host="smtp.example.com",
        smtp_from_email="security@example.com",
        gemini_api_key="configured",
    )
    report = deployment_readiness(settings, object())
    assert report["ready"] is False
    assert {
        "processor_key",
        "signed_webhook",
        "compliance",
        "database_backups",
        "monitoring",
        "legal_review",
        "security_review",
        "restricted_pilot",
    }.issubset(
        {item["name"] for item in report["blocking"]}
    )


def test_demo_readiness_does_not_require_live_processor(monkeypatch):
    monkeypatch.setattr("app.services.readiness.inspect", lambda _engine: Inspector())
    settings = Settings(
        _env_file=None,
        environment="production",
        demo_only=True,
        database_url="postgresql+psycopg://example",
        jwt_secret="x" * 40,
        frontend_url="https://demo.example.com",
        cors_origins="https://demo.example.com",
    )
    report = deployment_readiness(settings, object())
    assert report["ready"] is True


def test_live_readiness_passes_when_all_launch_gates_are_configured(monkeypatch):
    monkeypatch.setattr("app.services.readiness.inspect", lambda _engine: Inspector())
    settings = Settings(
        _env_file=None,
        environment="production",
        demo_only=False,
        database_url="postgresql+psycopg://example",
        jwt_secret="x" * 40,
        frontend_url="https://app.example.com",
        cors_origins="https://app.example.com",
        smtp_host="smtp.example.com",
        smtp_from_email="security@example.com",
        gemini_api_key="configured",
        stripe_secret_key="sk_live_configured",
        stripe_webhook_secret="whsec_configured",
        compliance_provider="http",
        compliance_provider_url="https://screening.example.com/check",
        database_backups_configured=True,
        monitoring_configured=True,
        legal_review_completed=True,
        security_review_completed=True,
        restricted_pilot_enabled=True,
    )
    report = deployment_readiness(settings, object())
    assert report["ready"] is True
    assert report["blocking"] == []


def test_live_readiness_accepts_manual_compliance_gate(monkeypatch):
    monkeypatch.setattr("app.services.readiness.inspect", lambda _engine: Inspector())
    settings = Settings(
        _env_file=None,
        environment="production",
        demo_only=False,
        database_url="postgresql+psycopg://example",
        jwt_secret="x" * 40,
        frontend_url="https://app.example.com",
        cors_origins="https://app.example.com",
        smtp_host="smtp.example.com",
        smtp_from_email="security@example.com",
        gemini_api_key="configured",
        stripe_secret_key="sk_live_configured",
        stripe_webhook_secret="whsec_configured",
        compliance_provider="manual",
        database_backups_configured=True,
        monitoring_configured=True,
        legal_review_completed=True,
        security_review_completed=True,
        restricted_pilot_enabled=True,
    )
    report = deployment_readiness(settings, object())
    assert report["ready"] is True
    assert report["blocking"] == []


def test_live_readiness_accepts_gmail_api_email_provider(monkeypatch):
    monkeypatch.setattr("app.services.readiness.inspect", lambda _engine: Inspector())
    settings = Settings(
        _env_file=None,
        environment="production",
        demo_only=False,
        database_url="postgresql+psycopg://example",
        jwt_secret="x" * 40,
        frontend_url="https://app.example.com",
        cors_origins="https://app.example.com",
        email_provider="gmail_api",
        gmail_client_id="client-id",
        gmail_client_secret="client-secret",
        gmail_refresh_token="refresh-token",
        gmail_from_email="security@example.com",
        gemini_api_key="configured",
        stripe_secret_key="sk_live_configured",
        stripe_webhook_secret="whsec_configured",
        compliance_provider="manual",
        database_backups_configured=True,
        monitoring_configured=True,
        legal_review_completed=True,
        security_review_completed=True,
        restricted_pilot_enabled=True,
    )
    report = deployment_readiness(settings, object())
    assert report["ready"] is True
    assert report["blocking"] == []
