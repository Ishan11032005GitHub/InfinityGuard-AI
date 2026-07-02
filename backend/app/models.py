from datetime import datetime, date
from enum import Enum
from sqlalchemy import Boolean, Date, DateTime, Enum as SqlEnum, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


class Role(str, Enum):
    admin = "Admin"
    finance_manager = "Finance Manager"
    viewer = "Viewer"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    account_type: Mapped[str] = mapped_column(String(30), default="company")
    workspace_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    workspace_key: Mapped[str] = mapped_column(String(64), index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(SqlEnum(Role), default=Role.viewer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AccountPreference(Base):
    __tablename__ = "account_preferences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    payment_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    risk_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    weekly_digest: Mapped[bool] = mapped_column(Boolean, default=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Kolkata")
    one_time_payment_limit: Mapped[float] = mapped_column(Float, default=5000)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PaymentMethod(Base):
    __tablename__ = "payment_methods"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    label: Mapped[str] = mapped_column(String(80))
    cardholder_name: Mapped[str] = mapped_column(String(120))
    brand: Mapped[str] = mapped_column(String(30))
    last_four: Mapped[str] = mapped_column(String(4))
    expiry_month: Mapped[int] = mapped_column(Integer)
    expiry_year: Mapped[int] = mapped_column(Integer)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    provider_token: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DemoWallet(Base):
    __tablename__ = "demo_wallets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    balance_minor: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DemoMessage(Base):
    __tablename__ = "demo_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24), default="text")
    text: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(String(240), nullable=True)
    amount_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="sent")
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    country: Mapped[str] = mapped_column(String(80))
    currency: Mapped[str] = mapped_column(String(8))
    risk_rating: Mapped[str] = mapped_column(String(20), default="Medium")
    avg_delay_days: Mapped[float] = mapped_column(Float, default=0)
    delayed_invoice_count: Mapped[int] = mapped_column(Integer, default=0)
    kyc_status: Mapped[str] = mapped_column(String(40), default="Verified")
    invoices = relationship("Invoice", back_populates="customer")


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("workspace_key", "invoice_number", name="uq_invoices_workspace_number"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    workspace_key: Mapped[str] = mapped_column(String(64), index=True)
    invoice_number: Mapped[str] = mapped_column(String(40), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8))
    country: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    issued_at: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    paid_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    customer = relationship("Customer", back_populates="invoices")


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8))
    country: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default="settled")
    rail: Mapped[str] = mapped_column(String(40), default="SWIFT")
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    external_ref: Mapped[str] = mapped_column(String(80), unique=True, index=True)


class QuickLink(Base):
    __tablename__ = "quick_links"
    __table_args__ = (UniqueConstraint("checkout_id", name="uq_quick_links_checkout_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    public_id: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    payer_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    payer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payer_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8))
    purpose_code: Mapped[str] = mapped_column(String(40), default="services")
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    provider: Mapped[str] = mapped_column(String(40), default="Card processor")
    provider_mode: Mapped[str] = mapped_column(String(24), default="unconfigured")
    checkout_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    checkout_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Refund(Base):
    __tablename__ = "refunds"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"), index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8))
    reason: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    provider_ref: Mapped[str | None] = mapped_column(String(160), nullable=True, unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="running", index=True)
    checked_count: Mapped[int] = mapped_column(Integer, default=0)
    matched_count: Mapped[int] = mapped_column(Integer, default=0)
    exception_count: Mapped[int] = mapped_column(Integer, default=0)
    exceptions: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    workspace_name: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    outcome: Mapped[str] = mapped_column(String(30), default="success")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(30))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8))
    country: Mapped[str] = mapped_column(String(80))
    counterparty: Mapped[str] = mapped_column(String(160))
    risk_score: Mapped[float] = mapped_column(Float, default=20)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FXRate(Base):
    __tablename__ = "fx_rates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    base_currency: Mapped[str] = mapped_column(String(8))
    quote_currency: Mapped[str] = mapped_column(String(8), default="USD")
    rate: Mapped[float] = mapped_column(Float)
    volatility_score: Mapped[float] = mapped_column(Float)
    as_of: Mapped[date] = mapped_column(Date)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(60))
    message: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    prediction_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[float] = mapped_column(Float)
    output: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ComplianceCheck(Base):
    __tablename__ = "compliance_checks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30))
    recommendations: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EventLog(Base):
    __tablename__ = "event_logs"
    __table_args__ = (UniqueConstraint("external_id", name="uq_event_logs_external_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    external_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
