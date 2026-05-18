import hashlib
import hmac
import json
import time
from dataclasses import dataclass
import httpx
from fastapi import HTTPException, Request
from ..config import get_settings
from ..models import Customer, Invoice


@dataclass
class CheckoutLink:
    provider: str
    mode: str
    checkout_id: str
    checkout_url: str
    raw: dict


def provider_status() -> dict:
    settings = get_settings()
    stripe_enabled = bool(settings.stripe_secret_key)
    return {
        "provider": "Stripe" if stripe_enabled else "Demo wallet provider",
        "mode": "stripe_test" if stripe_enabled else settings.payment_provider_mode,
        "connected": stripe_enabled,
    }


async def create_checkout_link(invoice: Invoice, customer: Customer | None, customer_email: str | None = None, success_url: str | None = None) -> CheckoutLink:
    settings = get_settings()
    if not settings.stripe_secret_key:
        checkout_id = f"ig_chk_{invoice.id}_{int(time.time())}"
        return CheckoutLink(
            provider="Demo wallet provider",
            mode="demo",
            checkout_id=checkout_id,
            checkout_url=f"{settings.frontend_url}/payment-app?checkout={checkout_id}",
            raw={"demo": True},
        )

    currency = invoice.currency.lower()
    amount_minor = int(round(invoice.amount * 100))
    final_success_url = success_url or f"{settings.frontend_url}/payment-app?checkout=success&invoice={invoice.id}"
    cancel_url = f"{settings.frontend_url}/payment-app?checkout=cancelled&invoice={invoice.id}"
    data = {
        "mode": "payment",
        "success_url": final_success_url,
        "cancel_url": cancel_url,
        "client_reference_id": invoice.invoice_number,
        "metadata[invoice_id]": str(invoice.id),
        "metadata[invoice_number]": invoice.invoice_number,
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": currency,
        "line_items[0][price_data][unit_amount]": str(amount_minor),
        "line_items[0][price_data][product_data][name]": f"Invoice {invoice.invoice_number}",
    }
    if customer_email:
        data["customer_email"] = customer_email
    elif customer:
        data["metadata[customer_name]"] = customer.name

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            "https://api.stripe.com/v1/checkout/sessions",
            data=data,
            auth=(settings.stripe_secret_key, ""),
        )
    if response.status_code >= 400:
        detail = response.json().get("error", {}).get("message", "Stripe checkout session failed")
        raise HTTPException(status_code=502, detail=detail)
    payload = response.json()
    return CheckoutLink(
        provider="Stripe",
        mode="stripe_test",
        checkout_id=payload["id"],
        checkout_url=payload["url"],
        raw=payload,
    )


async def verified_stripe_event(request: Request) -> dict:
    settings = get_settings()
    body = await request.body()
    signature = request.headers.get("stripe-signature", "")
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=400, detail="Stripe webhook secret is not configured")

    parts = dict(item.split("=", 1) for item in signature.split(",") if "=" in item)
    timestamp = parts.get("t")
    received_signature = parts.get("v1")
    if not timestamp or not received_signature:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature header")

    signed_payload = f"{timestamp}.{body.decode()}".encode()
    expected = hmac.new(settings.stripe_webhook_secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_signature):
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature")
    if abs(time.time() - int(timestamp)) > 300:
        raise HTTPException(status_code=400, detail="Stale Stripe webhook signature")

    return json.loads(body)
