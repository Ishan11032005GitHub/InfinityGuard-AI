from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..auth import current_user, require_roles
from ..database import SessionLocal, get_db
from ..models import Customer, EventLog, Invoice, Payment, Role, Transaction, User
from ..schemas import PaymentAppConnectIn, PaymentLinkIn, WalletRequestIn, WalletTransferIn
from ..services.events import enqueue_event, process_event
from ..services.payment_provider import create_checkout_link, provider_status, verified_stripe_event

router = APIRouter(prefix="/api/payment-app", tags=["payment-app"])


def process_event_background(event_id: int) -> None:
    db = SessionLocal()
    try:
        event = db.get(EventLog, event_id)
        if event:
            process_event(db, event)
    finally:
        db.close()


@router.get("/status")
def status(db: Session = Depends(get_db), user: User = Depends(current_user)):
    payment_count = db.query(Payment).count()
    latest_payment = db.query(func.max(Payment.received_at)).scalar()
    last_sync = db.query(EventLog).filter(EventLog.event_type == "payment_app.sync").order_by(EventLog.created_at.desc()).first()
    provider = provider_status()
    return {
        "provider": provider["provider"],
        "mode": provider["mode"],
        "connected": provider["connected"],
        "sync_health": "healthy" if payment_count else "needs_data",
        "last_payment_at": latest_payment.isoformat() if latest_payment else None,
        "last_sync_at": last_sync.created_at.isoformat() if last_sync else None,
        "webhook_events": db.query(EventLog).count(),
        "mapped_payments": payment_count,
    }


@router.post("/connect", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
def connect(payload: PaymentAppConnectIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    event = enqueue_event(db, "payment_app.connected", payload.model_dump())
    background.add_task(process_event_background, event.id)
    return {
        "status": "connected",
        "provider": payload.provider,
        "account_name": payload.account_name,
        "mode": payload.mode,
        "event_id": event.id,
    }


@router.post("/sync-demo", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
def sync_demo(background: BackgroundTasks, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.name == "Northstar Robotics").first()
    if not customer:
        customer = Customer(name="Northstar Robotics", country="US", currency="USD", risk_rating="Low", kyc_status="Verified")
        db.add(customer)
        db.flush()

    external_ref = f"stripe_pi_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    payment = Payment(
        customer_id=customer.id,
        amount=18420.75,
        currency=customer.currency,
        country=customer.country,
        status="settled",
        rail="Stripe",
        external_ref=external_ref,
    )
    db.add(payment)
    db.flush()
    db.add(Transaction(payment_id=payment.id, type="inbound", amount=payment.amount, currency=payment.currency, country=payment.country, counterparty=customer.name, risk_score=28))
    event = enqueue_event(db, "payment_app.sync", {"provider": "Stripe", "payment_id": payment.id, "external_ref": external_ref})
    background.add_task(process_event_background, event.id)
    return {"status": "synced", "imported_payments": 1, "payment_id": payment.id, "external_ref": external_ref, "event_id": event.id}


@router.post("/payment-link", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
async def payment_link(payload: PaymentLinkIn, db: Session = Depends(get_db)):
    invoice = db.get(Invoice, payload.invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    customer = db.get(Customer, invoice.customer_id)
    checkout = await create_checkout_link(invoice, customer, payload.customer_email, payload.success_url)
    event = enqueue_event(db, "payment_link.created", {"invoice_id": invoice.id, "provider": checkout.provider, "checkout_id": checkout.checkout_id})
    return {
        "status": "created",
        "provider": checkout.provider,
        "mode": checkout.mode,
        "invoice_number": invoice.invoice_number,
        "amount": invoice.amount,
        "currency": invoice.currency,
        "customer": customer.name if customer else None,
        "checkout_url": checkout.checkout_url,
        "event_id": event.id,
    }


@router.post("/stripe-webhook")
async def stripe_webhook(request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    event = await verified_stripe_event(request)
    if event.get("type") != "checkout.session.completed":
        stored = enqueue_event(db, "stripe.webhook.ignored", {"stripe_event_id": event.get("id"), "type": event.get("type")})
        return {"status": "ignored", "event_id": stored.id}

    session = event.get("data", {}).get("object", {})
    metadata = session.get("metadata") or {}
    invoice_id = int(metadata["invoice_id"]) if metadata.get("invoice_id") else None
    invoice = db.get(Invoice, invoice_id) if invoice_id else None
    customer = db.get(Customer, invoice.customer_id) if invoice else None
    if invoice:
        invoice.status = "paid"
        invoice.paid_at = datetime.utcnow().date()
    if not customer:
        customer = db.query(Customer).filter(Customer.name == metadata.get("customer_name", "Stripe customer")).first()
    if not customer:
        customer = Customer(name=metadata.get("customer_name", "Stripe customer"), country="US", currency=(session.get("currency") or "usd").upper(), risk_rating="Medium", kyc_status="Review")
        db.add(customer)
        db.flush()

    external_ref = session.get("payment_intent") or session.get("id")
    existing = db.query(Payment).filter(Payment.external_ref == external_ref).first()
    if not existing:
        amount = (session.get("amount_total") or 0) / 100
        payment = Payment(
            invoice_id=invoice.id if invoice else None,
            customer_id=customer.id,
            amount=amount,
            currency=(session.get("currency") or customer.currency).upper(),
            country=customer.country,
            status="settled",
            rail="Stripe Checkout",
            external_ref=external_ref,
        )
        db.add(payment)
        db.flush()
        db.add(Transaction(payment_id=payment.id, type="inbound", amount=payment.amount, currency=payment.currency, country=payment.country, counterparty=customer.name, risk_score=18))
    stored = enqueue_event(db, "stripe.checkout.completed", {"stripe_event_id": event.get("id"), "invoice_id": invoice_id, "external_ref": external_ref})
    background.add_task(process_event_background, stored.id)
    return {"status": "processed", "event_id": stored.id}


@router.post("/pay", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
def pay(payload: WalletTransferIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.name == payload.recipient_name).first()
    if not customer:
        customer = Customer(name=payload.recipient_name, country="US", currency=payload.currency, risk_rating="Medium", kyc_status="Review")
        db.add(customer)
        db.flush()
    external_ref = f"wallet_pay_{int(datetime.utcnow().timestamp())}"
    payment = Payment(
        customer_id=customer.id,
        amount=payload.amount,
        currency=payload.currency,
        country=customer.country,
        status="processing",
        rail=payload.rail,
        external_ref=external_ref,
    )
    db.add(payment)
    db.flush()
    db.add(Transaction(payment_id=payment.id, type="outbound", amount=payload.amount, currency=payload.currency, country=customer.country, counterparty=payload.recipient_name, risk_score=22))
    event = enqueue_event(db, "wallet.payment.sent", payload.model_dump() | {"payment_id": payment.id, "external_ref": external_ref})
    background.add_task(process_event_background, event.id)
    return {"status": "processing", "payment_id": payment.id, "external_ref": external_ref, "recipient": payload.recipient_name, "amount": payload.amount, "currency": payload.currency}


@router.post("/request", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
def request_money(payload: WalletRequestIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    request_id = f"wallet_req_{int(datetime.utcnow().timestamp())}"
    event = enqueue_event(db, "wallet.payment.requested", payload.model_dump() | {"request_id": request_id})
    background.add_task(process_event_background, event.id)
    return {"status": "requested", "request_id": request_id, "payer": payload.payer_name, "amount": payload.amount, "currency": payload.currency}
