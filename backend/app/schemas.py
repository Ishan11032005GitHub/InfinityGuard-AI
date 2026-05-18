from datetime import date, datetime
from pydantic import BaseModel, EmailStr, Field
from .models import Role


class SignupIn(BaseModel):
    email: EmailStr
    name: str
    password: str = Field(min_length=8)
    role: Role = Role.viewer


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class PaymentWebhookIn(BaseModel):
    external_ref: str
    customer_name: str
    country: str
    currency: str
    amount: float
    invoice_number: str | None = None
    rail: str = "SWIFT"


class InvoiceWebhookIn(BaseModel):
    invoice_number: str
    customer_name: str
    country: str
    currency: str
    amount: float
    issued_at: date
    due_date: date


class ComplianceIn(BaseModel):
    entity_type: str = "payment"
    entity_id: int | None = None
    amount: float
    country: str
    payer_name: str
    invoice_amount: float | None = None
    documents: list[str] = []


class CopilotIn(BaseModel):
    question: str


class PredictionProxyIn(BaseModel):
    invoice_id: int | None = None
    transaction_id: int | None = None
    payload: dict = {}


class PaymentAppConnectIn(BaseModel):
    provider: str = "Stripe"
    account_name: str = "Infinity Payments"
    mode: str = "test"


class PaymentLinkIn(BaseModel):
    invoice_id: int
    customer_email: EmailStr | None = None
    success_url: str | None = None


class DashboardOut(BaseModel):
    total_volume: float
    pending_invoices: int
    cash_runway: int
    currency_exposure: dict
    risk_score: float
    alerts: list[dict]
    monthly_transactions: list[dict]
    cash_flow: list[dict]
    fx_trends: list[dict]
    country_heatmap: list[dict]
    anomalies: list[dict]
