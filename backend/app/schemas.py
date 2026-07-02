from datetime import date, datetime
from pydantic import BaseModel, EmailStr, Field, field_validator
from .models import Role


def strong_password(value: str) -> str:
    if len(value) < 10 or not any(character.isalpha() for character in value) or not any(character.isdigit() for character in value):
        raise ValueError("Password must be at least 10 characters and include a letter and a number")
    return value


class SignupIn(BaseModel):
    email: EmailStr
    name: str
    password: str = Field(min_length=8)
    role: Role = Role.viewer
    account_type: str = Field(default="company", pattern="^(company|individual)$")
    workspace_name: str | None = Field(default=None, max_length=160)

    _strong_password = field_validator("password")(strong_password)


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    otp: str | None = Field(default=None, pattern=r"^\d{6}$")


class RefreshIn(BaseModel):
    refresh_token: str


class ProfileUpdateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class CompanyEmployeeCreateIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8)
    role: Role = Role.viewer

    _strong_password = field_validator("password")(strong_password)


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)

    _strong_password = field_validator("new_password")(strong_password)


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=20)
    new_password: str = Field(min_length=8)

    _strong_password = field_validator("new_password")(strong_password)


class EmailVerificationIn(BaseModel):
    token: str = Field(min_length=20)


class MFAEnableIn(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class MFADisableIn(BaseModel):
    password: str
    code: str = Field(pattern=r"^\d{6}$")


class AccountPreferencesIn(BaseModel):
    paymentAlerts: bool = True
    riskAlerts: bool = True
    weeklyDigest: bool = False
    currency: str = Field(default="USD", min_length=3, max_length=8)
    timezone: str = Field(default="Asia/Kolkata", max_length=80)
    oneTimePaymentLimit: float = Field(default=5000, gt=0, le=1000000000)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized.isalnum():
            raise ValueError("Currency must use an ISO-style alphanumeric code")
        return normalized


class PaymentWebhookIn(BaseModel):
    external_ref: str
    customer_name: str
    country: str
    currency: str
    amount: float = Field(gt=0)
    invoice_number: str | None = None
    rail: str = "SWIFT"


class InvoiceWebhookIn(BaseModel):
    invoice_number: str
    customer_name: str
    country: str
    currency: str
    amount: float = Field(gt=0)
    issued_at: date
    due_date: date


class ComplianceIn(BaseModel):
    entity_type: str = "payment"
    entity_id: int | None = None
    amount: float = Field(gt=0)
    country: str
    payer_name: str
    invoice_amount: float | None = None
    documents: list[str] = Field(default_factory=list)


class CopilotIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    history: list[dict] = Field(default_factory=list)


class PredictionProxyIn(BaseModel):
    invoice_id: int | None = None
    transaction_id: int | None = None
    payload: dict = Field(default_factory=dict)


class PaymentAppConnectIn(BaseModel):
    provider: str = "Card processor"
    account_name: str = "Infinity Payments"
    mode: str = "test"


class PaymentLinkIn(BaseModel):
    invoice_id: int
    customer_email: EmailStr | None = None
    success_url: str | None = None


class QuickLinkCreateIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    amount: float = Field(gt=0, le=1000000000)
    currency: str = Field(min_length=3, max_length=8)
    payer_name: str | None = Field(default=None, max_length=160)
    payer_email: EmailStr | None = None
    payer_country: str | None = Field(default=None, min_length=2, max_length=2)
    purpose_code: str = Field(default="services", min_length=2, max_length=40)
    invoice_id: int | None = None
    expires_in_days: int = Field(default=14, ge=1, le=90)

    @field_validator("currency")
    @classmethod
    def normalize_quicklink_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized.isalnum():
            raise ValueError("Currency must use an ISO-style alphanumeric code")
        return normalized

    @field_validator("payer_country")
    @classmethod
    def normalize_payer_country(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().upper()
        if not normalized.isalpha() or len(normalized) != 2:
            raise ValueError("Payer country must be a two-letter country code")
        return normalized


class DemoQuickLinkPayIn(BaseModel):
    cardholder_name: str = Field(min_length=2, max_length=120)
    card_number: str = Field(min_length=12, max_length=23)
    expiry_month: int = Field(ge=1, le=12)
    expiry_year: int = Field(ge=2026, le=2100)
    cvc: str = Field(pattern=r"^\d{3,4}$")

    @field_validator("card_number")
    @classmethod
    def validate_card_number(cls, value: str) -> str:
        digits = "".join(character for character in value if character.isdigit())
        if not 12 <= len(digits) <= 19:
            raise ValueError("Enter a valid test card number")
        checksum = 0
        parity = len(digits) % 2
        for index, character in enumerate(digits):
            number = int(character)
            if index % 2 == parity:
                number *= 2
                if number > 9:
                    number -= 9
            checksum += number
        if checksum % 10:
            raise ValueError("Enter a valid test card number")
        return digits


class RefundCreateIn(BaseModel):
    amount: float | None = Field(default=None, gt=0)
    reason: str = Field(default="requested_by_customer", pattern="^(duplicate|fraudulent|requested_by_customer|service_not_provided|other)$")
    idempotency_key: str = Field(min_length=16, max_length=120)


class PaymentMethodIn(BaseModel):
    label: str = Field(min_length=2, max_length=80)
    cardholder_name: str = Field(min_length=2, max_length=120)
    brand: str = Field(min_length=2, max_length=30)
    last_four: str = Field(pattern=r"^\d{4}$")
    expiry_month: int = Field(ge=1, le=12)
    expiry_year: int = Field(ge=2026, le=2100)


class WalletTransferIn(BaseModel):
    recipient_name: str
    recipient_handle: str
    amount: float = Field(gt=0)
    currency: str = "USD"
    note: str | None = None
    rail: str = "Wallet"
    payment_method_id: int | None = None
    idempotency_key: str = Field(min_length=16, max_length=120)

    @field_validator("currency")
    @classmethod
    def normalize_transfer_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized.isalnum() or not 3 <= len(normalized) <= 8:
            raise ValueError("Currency must use an ISO-style alphanumeric code")
        return normalized


class WalletRequestIn(BaseModel):
    payer_name: str
    payer_handle: str
    amount: float = Field(gt=0)
    currency: str = "USD"
    note: str | None = None

    @field_validator("currency")
    @classmethod
    def normalize_request_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized.isalnum() or not 3 <= len(normalized) <= 8:
            raise ValueError("Currency must use an ISO-style alphanumeric code")
        return normalized


class DemoChatIn(BaseModel):
    recipient_id: int
    text: str = Field(min_length=1, max_length=1000)


class DashboardOut(BaseModel):
    total_volume: float
    pending_invoices: int
    cash_runway: int | None
    currency_exposure: dict
    risk_score: float
    alerts: list[dict]
    monthly_transactions: list[dict]
    cash_flow: list[dict]
    fx_trends: list[dict]
    country_heatmap: list[dict]
    anomalies: list[dict]
