from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..auth import current_user, require_roles
from ..database import SessionLocal, get_db
from ..models import Customer, EventLog, Invoice, Payment, Role, Transaction, User
from ..schemas import PaymentAppConnectIn, PaymentLinkIn
from ..services.events import enqueue_event, process_event

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
    return {
        "provider": "Stripe-compatible payment app",
        "mode": "test",
        "connected": True,
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
def payment_link(payload: PaymentLinkIn, db: Session = Depends(get_db)):
    invoice = db.get(Invoice, payload.invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    customer = db.get(Customer, invoice.customer_id)
    checkout_id = f"ig_chk_{invoice.id}_{int(datetime.utcnow().timestamp())}"
    event = enqueue_event(db, "payment_link.created", {"invoice_id": invoice.id, "provider": "Stripe", "checkout_id": checkout_id})
    return {
        "status": "created",
        "provider": "Stripe",
        "invoice_number": invoice.invoice_number,
        "amount": invoice.amount,
        "currency": invoice.currency,
        "customer": customer.name if customer else None,
        "checkout_url": f"https://checkout.stripe.com/c/pay/{checkout_id}",
        "event_id": event.id,
    }
