from datetime import datetime, timedelta
import secrets
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..account_scope import account_user_ids
from ..auth import current_user, require_roles
from ..config import get_settings
from ..database import SessionLocal, get_db
from ..models import AccountPreference, Alert, AuditLog, Customer, DemoMessage, DemoWallet, EventLog, Invoice, Payment, PaymentMethod, QuickLink, ReconciliationRun, Refund, Role, Transaction, User
from ..schemas import DemoChatIn, DemoQuickLinkPayIn, PaymentAppConnectIn, PaymentLinkIn, PaymentMethodIn, QuickLinkCreateIn, RefundCreateIn, WalletRequestIn, WalletTransferIn
from ..services.audit import record_audit
from ..services.compliance_gateway import preflight_collection
from ..services.events import enqueue_event, process_event
from ..services.money_state import transition_payment, transition_quicklink
from ..services.payment_provider import charge_saved_card, create_card_setup_session, create_checkout_link, create_quicklink_checkout, provider_status, retrieve_card_setup_session, retrieve_checkout_session, verified_stripe_event
from ..services.processors import get_processor
from ..services.remittance import build_receipt_pdf, build_remittance_pdf

router = APIRouter(prefix="/api/payment-app", tags=["payment-app"])
DEMO_EMAILS = {"asha.demo@ledgerops.ai", "rohan.demo@ledgerops.ai"}


def is_demo_user(user: User) -> bool:
    return user.email in DEMO_EMAILS


def demo_handle(user: User) -> str:
    return f"{user.email.split('@')[0]}@pay"


def demo_contact_out(user: User) -> dict:
    wallet = getattr(user, "_demo_wallet", None)
    return {
        "id": user.id,
        "name": user.name,
        "handle": demo_handle(user),
        "currency": wallet.currency if wallet else "INR",
        "initial": user.name[:1].upper(),
    }


def demo_message_out(message: DemoMessage, user_id: int) -> dict:
    return {
        "id": message.id,
        "kind": message.kind,
        "direction": "outgoing" if message.sender_id == user_id else "incoming",
        "text": message.text,
        "note": message.note,
        "amount": message.amount_minor / 100 if message.amount_minor is not None else None,
        "currency": message.currency,
        "status": message.status,
        "createdAt": message.created_at.isoformat(),
    }


def demo_customer(db: Session, owner: User, counterparty: User) -> Customer:
    customer = db.query(Customer).filter(Customer.user_id == owner.id, Customer.name == counterparty.name).first()
    if not customer:
        customer = Customer(user_id=owner.id, name=counterparty.name, country="IN", currency="INR", risk_rating="Low", kyc_status="Demo verified")
        db.add(customer)
        db.flush()
    return customer


def payment_method_out(method: PaymentMethod):
    return {
        "id": method.id,
        "label": method.label,
        "cardholder_name": method.cardholder_name,
        "brand": method.brand,
        "last_four": method.last_four,
        "expiry_month": method.expiry_month,
        "expiry_year": method.expiry_year,
        "is_default": method.is_default,
    }


def one_time_limit_for(db: Session, user: User) -> float:
    preferences = db.query(AccountPreference).filter(AccountPreference.user_id == user.id).first()
    account_limit = preferences.one_time_payment_limit if preferences else 5000
    platform_cap = get_settings().max_collection_amount
    if platform_cap and platform_cap > 0:
        return min(account_limit, platform_cap)
    return account_limit


def enforce_one_time_limit(db: Session, user: User, amount: float, currency: str) -> None:
    limit = one_time_limit_for(db, user)
    if amount > limit:
        raise HTTPException(
            status_code=409,
            detail=f"This payment exceeds your one-time {currency.upper()} limit of {limit:,.2f}. Update your account limit in Settings.",
        )


def quicklink_out(link: QuickLink) -> dict:
    now = datetime.utcnow()
    status = "expired" if link.status in {"active", "pending_review"} and link.expires_at and link.expires_at < now else link.status
    return {
        "id": link.id,
        "public_id": link.public_id,
        "title": link.title,
        "payer_name": link.payer_name,
        "payer_email": link.payer_email,
        "payer_country": link.payer_country,
        "amount": link.amount,
        "currency": link.currency,
        "purpose_code": link.purpose_code,
        "status": status,
        "provider": link.provider,
        "mode": link.provider_mode,
        "checkout_id": link.checkout_id,
        "checkout_url": link.checkout_url,
        "invoice_id": link.invoice_id,
        "payment_id": link.payment_id,
        "expires_at": link.expires_at.isoformat() if link.expires_at else None,
        "paid_at": link.paid_at.isoformat() if link.paid_at else None,
        "created_at": link.created_at.isoformat(),
        "remittance_available": status in {"paid", "partially_refunded", "refunded"} and bool(link.payment_id),
        "receipt_available": status in {"paid", "partially_refunded", "refunded"} and bool(link.payment_id),
    }


def public_quicklink_out(link: QuickLink) -> dict:
    data = quicklink_out(link)
    return {
        "public_id": data["public_id"],
        "title": data["title"],
        "amount": data["amount"],
        "currency": data["currency"],
        "purpose_code": data["purpose_code"],
        "status": data["status"],
        "provider": data["provider"],
        "mode": data["mode"],
        "expires_at": data["expires_at"],
    }


def settle_quicklink(db: Session, session: dict, link: QuickLink):
    if session.get("payment_status") != "paid":
        raise HTTPException(status_code=409, detail="The QuickLink has not been paid")
    paid_amount = (session.get("amount_total") or 0) / 100
    paid_currency = (session.get("currency") or "").upper()
    if round(paid_amount, 2) != round(link.amount, 2) or paid_currency != link.currency.upper():
        raise HTTPException(status_code=409, detail="Checkout amount or currency does not match the QuickLink")
    _invoice, payment, customer = record_completed_checkout(db, session, link.invoice_id, user_id=link.user_id)
    transition_quicklink(link, "paid")
    link.payment_id = payment.id
    link.paid_at = datetime.utcnow()
    db.commit()
    db.refresh(link)
    return payment, customer


def reset_demo_state(db: Session) -> dict:
    demo_users = db.query(User).filter(User.email.in_(DEMO_EMAILS)).all()
    demo_ids = [account.id for account in demo_users]
    if len(demo_ids) != 2:
        raise HTTPException(status_code=409, detail="Demo accounts are not ready")

    db.query(DemoMessage).filter(
        (DemoMessage.sender_id.in_(demo_ids)) | (DemoMessage.recipient_id.in_(demo_ids))
    ).delete(synchronize_session=False)
    db.query(Transaction).filter(Transaction.user_id.in_(demo_ids)).delete(synchronize_session=False)
    db.query(QuickLink).filter(QuickLink.user_id.in_(demo_ids)).delete(synchronize_session=False)
    db.query(Payment).filter(Payment.user_id.in_(demo_ids)).delete(synchronize_session=False)
    db.query(EventLog).filter(EventLog.user_id.in_(demo_ids)).delete(synchronize_session=False)
    db.query(Invoice).filter(Invoice.user_id.in_(demo_ids)).delete(synchronize_session=False)
    db.query(Customer).filter(Customer.user_id.in_(demo_ids)).delete(synchronize_session=False)

    starting_balances = {
        "asha.demo@ledgerops.ai": 2_500_000,
        "rohan.demo@ledgerops.ai": 1_800_000,
    }
    for account in demo_users:
        wallet = db.query(DemoWallet).filter(DemoWallet.user_id == account.id).first()
        if wallet:
            wallet.balance_minor = starting_balances[account.email]
    db.commit()
    return {
        "status": "reset",
        "balances": {
            "asha.demo@ledgerops.ai": 25_000,
            "rohan.demo@ledgerops.ai": 18_000,
        },
        "currency": "INR",
    }


def process_event_background(event_id: int) -> None:
    db = SessionLocal()
    try:
        event = db.get(EventLog, event_id)
        if event:
            process_event(db, event)
    finally:
        db.close()


def record_completed_checkout(db: Session, session: dict, invoice_id: int | None, user_id: int | None = None):
    if session.get("payment_status") != "paid":
        raise HTTPException(status_code=409, detail="The checkout has not been paid")
    metadata = session.get("metadata") or {}
    resolved_invoice_id = invoice_id or (int(metadata["invoice_id"]) if metadata.get("invoice_id") else None)
    resolved_user_id = user_id or (int(metadata["ledgerops_user_id"]) if metadata.get("ledgerops_user_id") else None)
    invoice = db.get(Invoice, resolved_invoice_id) if resolved_invoice_id else None
    if invoice and resolved_user_id and invoice.user_id != resolved_user_id:
        raise HTTPException(status_code=403, detail="Checkout session does not belong to this account")
    customer = db.get(Customer, invoice.customer_id) if invoice else None
    if invoice:
        paid_amount = (session.get("amount_total") or 0) / 100
        paid_currency = (session.get("currency") or "").upper()
        if round(paid_amount, 2) != round(invoice.amount, 2) or paid_currency != invoice.currency.upper():
            raise HTTPException(status_code=409, detail="Checkout amount or currency does not match the invoice")
        invoice.status = "paid"
        invoice.paid_at = datetime.utcnow().date()
    if not customer:
        customer = db.query(Customer).filter(Customer.user_id == resolved_user_id, Customer.name == metadata.get("customer_name", "Card payer")).first()
    if not customer:
        customer = Customer(user_id=resolved_user_id, name=metadata.get("customer_name", "Card payer"), country="US", currency=(session.get("currency") or "usd").upper(), risk_rating="Medium", kyc_status="Review")
        db.add(customer)
        db.flush()

    external_ref = session.get("payment_intent") or session.get("id")
    payment = db.query(Payment).filter(Payment.user_id == resolved_user_id, Payment.external_ref == external_ref).first()
    if not payment:
        amount = (session.get("amount_total") or 0) / 100
        if amount == 0 and invoice:
            amount = invoice.amount
        payment = Payment(
            invoice_id=invoice.id if invoice else None,
            user_id=resolved_user_id,
            customer_id=customer.id,
            amount=amount,
            currency=(session.get("currency") or customer.currency).upper(),
            country=customer.country,
            status="settled",
            rail="Card checkout",
            external_ref=external_ref,
        )
        db.add(payment)
        db.flush()
        db.add(Transaction(user_id=resolved_user_id, payment_id=payment.id, type="inbound", amount=payment.amount, currency=payment.currency, country=payment.country, counterparty=customer.name, risk_score=18))
    return invoice, payment, customer


@router.get("/status")
def status(db: Session = Depends(get_db), user: User = Depends(current_user)):
    scope = account_user_ids(db, user)
    payment_count = db.query(Payment).filter(Payment.user_id.in_(scope)).count()
    latest_payment = db.query(func.max(Payment.received_at)).filter(Payment.user_id.in_(scope)).scalar()
    last_sync = db.query(EventLog).filter(EventLog.user_id.in_(scope), EventLog.event_type == "payment_app.sync").order_by(EventLog.created_at.desc()).first()
    provider = provider_status()
    if is_demo_user(user):
        wallet = db.query(DemoWallet).filter(DemoWallet.user_id == user.id).first()
        return {
            "provider": "LedgerOps Demo Network",
            "processor": "demo",
            "mode": "demo",
            "connected": True,
            "sync_health": "simulated",
            "last_payment_at": latest_payment.isoformat() if latest_payment else None,
            "last_sync_at": None,
            "webhook_events": db.query(DemoMessage).filter((DemoMessage.sender_id == user.id) | (DemoMessage.recipient_id == user.id)).count(),
            "mapped_payments": payment_count,
            "saved_methods": db.query(PaymentMethod).filter(PaymentMethod.user_id == user.id).count(),
            "webhook_configured": False,
            "real_payments_enabled": False,
            "issuer_agnostic": True,
            "card_networks": ["Visa", "Mastercard", "RuPay (demo)"],
            "available_balance": (wallet.balance_minor / 100) if wallet else 0,
            "currency": wallet.currency if wallet else "INR",
        }
    return {
        "provider": provider["provider"],
        "processor": provider["processor"],
        "mode": provider["mode"],
        "connected": provider["connected"],
        "sync_health": "healthy" if provider["connected"] else "not_configured",
        "last_payment_at": latest_payment.isoformat() if latest_payment else None,
        "last_sync_at": last_sync.created_at.isoformat() if last_sync else None,
        "webhook_events": db.query(EventLog).filter(EventLog.user_id.in_(scope)).count(),
        "mapped_payments": payment_count,
        "saved_methods": db.query(PaymentMethod).filter(PaymentMethod.user_id == user.id).count(),
        "webhook_configured": provider["webhook_configured"],
        "real_payments_enabled": provider["real_payments_enabled"],
        "issuer_agnostic": provider["issuer_agnostic"],
        "card_networks": provider["card_networks"],
    }


@router.get("/demo/contacts")
def demo_contacts(db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not is_demo_user(user):
        return []
    contacts = db.query(User).filter(User.email.in_(DEMO_EMAILS), User.id != user.id).order_by(User.name).all()
    wallets = {wallet.user_id: wallet for wallet in db.query(DemoWallet).filter(DemoWallet.user_id.in_([contact.id for contact in contacts])).all()}
    for contact in contacts:
        contact._demo_wallet = wallets.get(contact.id)
    return [demo_contact_out(contact) for contact in contacts]


@router.get("/demo/messages/{contact_id}")
def demo_messages(contact_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not is_demo_user(user):
        raise HTTPException(status_code=404, detail="Demo chat is only available to demo accounts")
    contact = db.query(User).filter(User.id == contact_id, User.email.in_(DEMO_EMAILS)).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Demo contact not found")
    records = db.query(DemoMessage).filter(
        ((DemoMessage.sender_id == user.id) & (DemoMessage.recipient_id == contact.id)) |
        ((DemoMessage.sender_id == contact.id) & (DemoMessage.recipient_id == user.id))
    ).order_by(DemoMessage.created_at.asc()).limit(200).all()
    unread = [message for message in records if message.recipient_id == user.id and message.read_at is None]
    for message in unread:
        message.read_at = datetime.utcnow()
    if unread:
        db.commit()
    return [demo_message_out(message, user.id) for message in records]


@router.post("/demo/messages")
def send_demo_message(payload: DemoChatIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not is_demo_user(user):
        raise HTTPException(status_code=404, detail="Demo chat is only available to demo accounts")
    recipient = db.query(User).filter(User.id == payload.recipient_id, User.email.in_(DEMO_EMAILS)).first()
    if not recipient or recipient.id == user.id:
        raise HTTPException(status_code=404, detail="Demo contact not found")
    message = DemoMessage(sender_id=user.id, recipient_id=recipient.id, kind="text", text=payload.text.strip(), status="sent")
    db.add(message)
    db.commit()
    db.refresh(message)
    return demo_message_out(message, user.id)


@router.get("/payment-methods")
def payment_methods(db: Session = Depends(get_db), user: User = Depends(current_user)):
    methods = db.query(PaymentMethod).filter(PaymentMethod.user_id == user.id).order_by(PaymentMethod.is_default.desc(), PaymentMethod.created_at.desc()).all()
    return [payment_method_out(method) for method in methods]


@router.post("/payment-methods", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
def add_payment_method(payload: PaymentMethodIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    provider = provider_status()
    if not is_demo_user(user) and provider["mode"] != "demo":
        raise HTTPException(status_code=400, detail="Cards must be added through the secure processor-hosted setup")
    is_first = not db.query(PaymentMethod).filter(PaymentMethod.user_id == user.id).first()
    method = PaymentMethod(user_id=user.id, is_default=is_first, **payload.model_dump())
    db.add(method)
    record_audit(
        db,
        user=user,
        action="payment_method.added",
        entity_type="payment_method",
        details={"brand": payload.brand, "last_four": payload.last_four, "is_default": is_first},
    )
    db.commit()
    db.refresh(method)
    return payment_method_out(method)


@router.post("/payment-methods/setup", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
async def start_payment_method_setup(user: User = Depends(current_user)):
    if is_demo_user(user):
        return {"mode": "manual"}
    provider = provider_status()
    if not provider["connected"] and provider["mode"] != "demo":
        raise HTTPException(status_code=503, detail="Payment provider is not configured")
    checkout = await create_card_setup_session(user)
    if not checkout:
        return {"mode": "manual"}
    return {"mode": checkout.mode, "checkout_id": checkout.checkout_id, "checkout_url": checkout.checkout_url}


@router.post("/demo/reset")
def reset_demo(db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not is_demo_user(user):
        raise HTTPException(status_code=404, detail="Demo reset is only available to demo accounts")
    result = reset_demo_state(db)
    wallet = db.query(DemoWallet).filter(DemoWallet.user_id == user.id).first()
    return result | {"available_balance": wallet.balance_minor / 100 if wallet else 0}


@router.post("/demo/public-reset")
def public_reset_demo(db: Session = Depends(get_db)):
    return reset_demo_state(db)


@router.get("/demo/public-accounts")
def public_demo_accounts(db: Session = Depends(get_db)):
    accounts = db.query(User).filter(User.email.in_(DEMO_EMAILS)).order_by(User.name.asc()).all()
    wallets = {
        wallet.user_id: wallet
        for wallet in db.query(DemoWallet).filter(DemoWallet.user_id.in_([account.id for account in accounts])).all()
    }
    return [
        {
            "email": account.email,
            "name": account.name,
            "balance": wallets[account.id].balance_minor / 100 if account.id in wallets else 0,
            "currency": wallets[account.id].currency if account.id in wallets else "INR",
        }
        for account in accounts
    ]


@router.post("/payment-methods/setup/{checkout_id}/complete", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
async def complete_payment_method_setup(checkout_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    session = await retrieve_card_setup_session(checkout_id)
    if str(session.get("metadata", {}).get("ledgerops_user_id")) != str(user.id):
        raise HTTPException(status_code=403, detail="Card setup session does not belong to this account")
    setup_intent = session.get("setup_intent") or {}
    payment_method = setup_intent.get("payment_method") if isinstance(setup_intent, dict) else None
    card = payment_method.get("card") if isinstance(payment_method, dict) else None
    if not card or not payment_method.get("id") or not session.get("customer"):
        raise HTTPException(status_code=400, detail="Card setup has not been completed")
    provider_token = f"{session['customer']}:{payment_method['id']}"
    existing = db.query(PaymentMethod).filter(PaymentMethod.user_id == user.id, PaymentMethod.provider_token == provider_token).first()
    if existing:
        return payment_method_out(existing)
    is_first = not db.query(PaymentMethod).filter(PaymentMethod.user_id == user.id).first()
    method = PaymentMethod(
        user_id=user.id,
        label=f"{card.get('brand', 'Card').title()} card",
        cardholder_name=user.name,
        brand=card.get("brand", "card").replace("_", " ").title(),
        last_four=card["last4"],
        expiry_month=card["exp_month"],
        expiry_year=card["exp_year"],
        is_default=is_first,
        provider_token=provider_token,
    )
    db.add(method)
    record_audit(
        db,
        user=user,
        action="payment_method.setup_completed",
        entity_type="payment_method",
        details={"checkout_id": checkout_id, "brand": method.brand, "last_four": method.last_four, "is_default": is_first},
    )
    db.commit()
    db.refresh(method)
    return payment_method_out(method)


@router.patch("/payment-methods/{method_id}/default", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
def set_default_payment_method(method_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    method = db.query(PaymentMethod).filter(PaymentMethod.id == method_id, PaymentMethod.user_id == user.id).first()
    if not method:
        raise HTTPException(status_code=404, detail="Payment method not found")
    db.query(PaymentMethod).filter(PaymentMethod.user_id == user.id).update({PaymentMethod.is_default: False})
    method.is_default = True
    record_audit(
        db,
        user=user,
        action="payment_method.default_changed",
        entity_type="payment_method",
        entity_id=method.id,
        details={"brand": method.brand, "last_four": method.last_four},
    )
    db.commit()
    db.refresh(method)
    return payment_method_out(method)


@router.delete("/payment-methods/{method_id}", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
def remove_payment_method(method_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    method = db.query(PaymentMethod).filter(PaymentMethod.id == method_id, PaymentMethod.user_id == user.id).first()
    if not method:
        raise HTTPException(status_code=404, detail="Payment method not found")
    was_default = method.is_default
    record_audit(
        db,
        user=user,
        action="payment_method.removed",
        entity_type="payment_method",
        entity_id=method.id,
        details={"brand": method.brand, "last_four": method.last_four, "was_default": was_default},
    )
    db.delete(method)
    db.commit()
    if was_default:
        next_method = db.query(PaymentMethod).filter(PaymentMethod.user_id == user.id).order_by(PaymentMethod.created_at.desc()).first()
        if next_method:
            next_method.is_default = True
            db.commit()
    return {"status": "removed", "id": method_id}


@router.post("/connect", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
def connect(payload: PaymentAppConnectIn, background: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(current_user)):
    event = enqueue_event(db, "payment_app.connected", payload.model_dump(), user_id=user.id)
    background.add_task(process_event_background, event.id)
    return {
        "status": "connected",
        "provider": payload.provider,
        "account_name": payload.account_name,
        "mode": payload.mode,
        "event_id": event.id,
    }


@router.post("/sync-demo", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
def sync_demo(background: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if provider_status()["mode"] != "demo":
        raise HTTPException(status_code=404, detail="Demo synchronization is disabled")
    scope = account_user_ids(db, user)
    customer = db.query(Customer).filter(Customer.user_id.in_(scope), Customer.name == "Northstar Robotics").first()
    if not customer:
        customer = Customer(user_id=user.id, name="Northstar Robotics", country="US", currency="USD", risk_rating="Low", kyc_status="Verified")
        db.add(customer)
        db.flush()

    external_ref = f"card_sync_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    payment = Payment(
        customer_id=customer.id,
        user_id=user.id,
        amount=18420.75,
        currency=customer.currency,
        country=customer.country,
        status="settled",
        rail="Card processor",
        external_ref=external_ref,
    )
    db.add(payment)
    db.flush()
    db.add(Transaction(user_id=user.id, payment_id=payment.id, type="inbound", amount=payment.amount, currency=payment.currency, country=payment.country, counterparty=customer.name, risk_score=28))
    event = enqueue_event(db, "payment_app.sync", {"provider": "Card processor", "payment_id": payment.id, "external_ref": external_ref}, user_id=user.id)
    background.add_task(process_event_background, event.id)
    return {"status": "synced", "imported_payments": 1, "payment_id": payment.id, "external_ref": external_ref, "event_id": event.id}


@router.post("/payment-link", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
async def payment_link(payload: PaymentLinkIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    invoice = db.query(Invoice).filter(Invoice.id == payload.invoice_id, Invoice.user_id.in_(account_user_ids(db, user))).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    customer = db.get(Customer, invoice.customer_id)
    checkout = await create_checkout_link(invoice, customer, user, payload.customer_email, payload.success_url)
    event = enqueue_event(db, "payment_link.created", {"invoice_id": invoice.id, "provider": checkout.provider, "checkout_id": checkout.checkout_id}, user_id=user.id)
    return {
        "status": "created",
        "provider": checkout.provider,
        "mode": checkout.mode,
        "checkout_id": checkout.checkout_id,
        "invoice_number": invoice.invoice_number,
        "amount": invoice.amount,
        "currency": invoice.currency,
        "customer": customer.name if customer else None,
        "checkout_url": checkout.checkout_url,
        "event_id": event.id,
    }


@router.get("/quicklinks")
def quicklinks(db: Session = Depends(get_db), user: User = Depends(current_user)):
    scope = account_user_ids(db, user)
    links = db.query(QuickLink).filter(QuickLink.user_id.in_(scope)).order_by(QuickLink.created_at.desc()).limit(100).all()
    return [quicklink_out(link) for link in links]


@router.get("/public/quicklinks/{public_id}")
def public_quicklink(public_id: str, db: Session = Depends(get_db)):
    link = db.query(QuickLink).filter(QuickLink.public_id == public_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="This payment link does not exist")
    return public_quicklink_out(link)


@router.post("/public/quicklinks/{public_id}/demo-pay")
def pay_demo_quicklink(public_id: str, payload: DemoQuickLinkPayIn, db: Session = Depends(get_db)):
    link = db.query(QuickLink).filter(QuickLink.public_id == public_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="This payment link does not exist")
    if link.provider_mode != "demo":
        raise HTTPException(status_code=409, detail="Use the secure processor checkout for this payment link")
    if link.status != "active":
        raise HTTPException(status_code=409, detail=f"This payment link is {link.status}")
    if link.expires_at and link.expires_at < datetime.utcnow():
        transition_quicklink(link, "expired")
        db.commit()
        raise HTTPException(status_code=409, detail="This payment link has expired")
    session = {
        "id": link.checkout_id,
        "payment_intent": f"demo_card_{link.public_id}",
        "payment_status": "paid",
        "amount_total": int(round(link.amount * 100)),
        "currency": link.currency.lower(),
        "metadata": {
            "quicklink_id": str(link.id),
            "ledgerops_user_id": str(link.user_id),
            "customer_name": link.payer_name or payload.cardholder_name,
        },
    }
    payment, _customer = settle_quicklink(db, session, link)
    enqueue_event(db, "quicklink.paid", {"quicklink_id": link.id, "payment_id": payment.id, "external_ref": payment.external_ref}, user_id=link.user_id)
    return public_quicklink_out(link) | {"message": "Demo card payment completed"}


@router.post("/quicklinks")
async def create_quicklink(payload: QuickLinkCreateIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    settings = get_settings()
    live_operation = not (is_demo_user(user) or settings.demo_only)
    if live_operation and not user.email_verified:
        raise HTTPException(status_code=403, detail="Verify your email before creating a live payment link")
    if live_operation and not user.mfa_enabled:
        raise HTTPException(status_code=403, detail="Enable authenticator MFA before creating a live payment link")
    enforce_one_time_limit(db, user, payload.amount, payload.currency)
    invoice = None
    if payload.invoice_id:
        invoice = db.query(Invoice).filter(Invoice.id == payload.invoice_id, Invoice.user_id.in_(account_user_ids(db, user))).first()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if invoice.status != "pending":
            raise HTTPException(status_code=409, detail="Only pending invoices can be collected")
        if round(invoice.amount, 2) != round(payload.amount, 2) or invoice.currency.upper() != payload.currency.upper():
            raise HTTPException(status_code=409, detail="QuickLink amount and currency must match the invoice")

    normalized_purpose = payload.purpose_code.strip().lower().replace(" ", "_")
    screening = preflight_collection(
        amount=payload.amount,
        currency=payload.currency,
        purpose_code=normalized_purpose,
        payer_name=payload.payer_name,
        payer_email=str(payload.payer_email) if payload.payer_email else None,
        payer_country=payload.payer_country,
        demo=is_demo_user(user) or settings.demo_only,
    )
    link = QuickLink(
        user_id=invoice.user_id if invoice and invoice.user_id else user.id,
        public_id=secrets.token_urlsafe(12),
        title=payload.title.strip(),
        payer_name=payload.payer_name.strip() if payload.payer_name else None,
        payer_email=str(payload.payer_email) if payload.payer_email else None,
        payer_country=payload.payer_country,
        amount=payload.amount,
        currency=payload.currency,
        purpose_code=normalized_purpose,
        invoice_id=invoice.id if invoice else None,
        status="pending_review" if screening.requires_manual_review else "active",
        expires_at=datetime.utcnow() + timedelta(days=payload.expires_in_days),
    )
    db.add(link)
    db.flush()
    record_audit(
        db,
        user=user,
        action="quicklink.compliance_preflight",
        entity_type="quicklink",
        entity_id=link.id,
        details={"status": screening.status, "provider": screening.provider, "purpose_code": normalized_purpose, "manual_review": screening.requires_manual_review},
    )
    if screening.requires_manual_review:
        event = enqueue_event(
            db,
            "quicklink.manual_review_required",
            {"quicklink_id": link.id, "public_id": link.public_id, "amount": link.amount, "currency": link.currency, "purpose_code": normalized_purpose},
            user_id=user.id,
        )
        return quicklink_out(link) | {
            "event_id": event.id,
            "message": "QuickLink created and waiting for manual compliance approval before checkout is enabled.",
        }
    checkout = await create_quicklink_checkout(link, user)
    link.provider = checkout.provider
    link.provider_mode = checkout.mode
    link.checkout_id = checkout.checkout_id
    link.checkout_url = checkout.checkout_url
    event = enqueue_event(
        db,
        "quicklink.created",
        {"quicklink_id": link.id, "public_id": link.public_id, "checkout_id": checkout.checkout_id, "amount": link.amount, "currency": link.currency},
        user_id=user.id,
    )
    return quicklink_out(link) | {"event_id": event.id}


@router.post("/quicklinks/{link_id}/approve", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
async def approve_quicklink(link_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    link = db.query(QuickLink).filter(QuickLink.id == link_id, QuickLink.user_id.in_(account_user_ids(db, user))).first()
    if not link:
        raise HTTPException(status_code=404, detail="QuickLink not found")
    if link.status == "active":
        return quicklink_out(link) | {"message": "QuickLink is already approved."}
    if link.status != "pending_review":
        raise HTTPException(status_code=409, detail=f"QuickLink cannot be approved from {link.status} status")
    if link.expires_at and link.expires_at < datetime.utcnow():
        transition_quicklink(link, "expired")
        db.commit()
        return quicklink_out(link) | {"message": "QuickLink expired before approval."}
    transition_quicklink(link, "active")
    checkout = await create_quicklink_checkout(link, user)
    link.provider = checkout.provider
    link.provider_mode = checkout.mode
    link.checkout_id = checkout.checkout_id
    link.checkout_url = checkout.checkout_url
    record_audit(
        db,
        user=user,
        action="quicklink.manual_compliance_approved",
        entity_type="quicklink",
        entity_id=link.id,
        details={"amount": link.amount, "currency": link.currency, "purpose_code": link.purpose_code},
    )
    event = enqueue_event(
        db,
        "quicklink.approved",
        {"quicklink_id": link.id, "public_id": link.public_id, "checkout_id": checkout.checkout_id, "amount": link.amount, "currency": link.currency},
        user_id=user.id,
    )
    return quicklink_out(link) | {"event_id": event.id, "message": "Manual compliance approved. Checkout is ready to share."}


@router.post("/quicklinks/{link_id}/verify", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
async def verify_quicklink(link_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    link = db.query(QuickLink).filter(QuickLink.id == link_id, QuickLink.user_id.in_(account_user_ids(db, user))).first()
    if not link:
        raise HTTPException(status_code=404, detail="QuickLink not found")
    if link.status == "paid":
        return quicklink_out(link)
    if link.status == "pending_review":
        return quicklink_out(link) | {"message": "Manual compliance approval is required before checkout verification."}
    if link.expires_at and link.expires_at < datetime.utcnow():
        transition_quicklink(link, "expired")
        db.commit()
        return quicklink_out(link)
    session = await retrieve_checkout_session(link.checkout_id)
    if session.get("demo"):
        return quicklink_out(link) | {"message": "No demo card payment has been submitted from the payer checkout yet."}
    if session.get("payment_status") != "paid":
        return quicklink_out(link) | {"message": "The card payment has not settled yet."}
    payment, _customer = settle_quicklink(db, session, link)
    enqueue_event(db, "quicklink.paid", {"quicklink_id": link.id, "payment_id": payment.id, "external_ref": payment.external_ref}, user_id=link.user_id)
    record_audit(
        db,
        user=user,
        action="quicklink.verified_paid",
        entity_type="quicklink",
        entity_id=link.id,
        details={"payment_id": payment.id, "external_ref": payment.external_ref, "amount": payment.amount, "currency": payment.currency},
    )
    db.commit()
    return quicklink_out(link)


@router.delete("/quicklinks/{link_id}", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
def disable_quicklink(link_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    link = db.query(QuickLink).filter(QuickLink.id == link_id, QuickLink.user_id.in_(account_user_ids(db, user))).first()
    if not link:
        raise HTTPException(status_code=404, detail="QuickLink not found")
    if link.status == "paid":
        raise HTTPException(status_code=409, detail="Paid QuickLinks remain in the settlement record")
    transition_quicklink(link, "disabled")
    record_audit(
        db,
        user=user,
        action="quicklink.disabled",
        entity_type="quicklink",
        entity_id=link.id,
        details={"public_id": link.public_id, "amount": link.amount, "currency": link.currency},
    )
    db.commit()
    return quicklink_out(link)


@router.get("/quicklinks/{link_id}/remittance")
def quicklink_remittance(link_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    link = db.query(QuickLink).filter(QuickLink.id == link_id, QuickLink.user_id.in_(account_user_ids(db, user))).first()
    if not link:
        raise HTTPException(status_code=404, detail="QuickLink not found")
    if link.status not in {"paid", "partially_refunded", "refunded"} or not link.payment_id:
        raise HTTPException(status_code=409, detail="Remittance advice is available after payment settles")
    payment = db.get(Payment, link.payment_id)
    owner = db.get(User, link.user_id)
    if not payment or not owner:
        raise HTTPException(status_code=404, detail="Settlement record not found")
    pdf = build_remittance_pdf(
        workspace=owner.workspace_name or owner.name,
        recipient=owner.name,
        payer=link.payer_name or "Card payer",
        payer_email=link.payer_email or "",
        amount=payment.amount,
        currency=payment.currency,
        purpose_code=link.purpose_code,
        reference=payment.external_ref,
        paid_at=link.paid_at or payment.received_at,
        payment_rail=payment.rail,
        payment_status=payment.status,
    )
    filename = f"remittance-{link.public_id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/quicklinks/{link_id}/receipt")
def quicklink_receipt(link_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    link = db.query(QuickLink).filter(QuickLink.id == link_id, QuickLink.user_id.in_(account_user_ids(db, user))).first()
    if not link or link.status not in {"paid", "partially_refunded", "refunded"} or not link.payment_id:
        raise HTTPException(status_code=409, detail="Receipt is available after payment settles")
    payment = db.get(Payment, link.payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Settlement record not found")
    owner = db.get(User, link.user_id)
    if not payment or not owner:
        raise HTTPException(status_code=404, detail="Settlement record not found")
    refunded = db.query(func.coalesce(func.sum(Refund.amount), 0)).filter(
        Refund.payment_id == payment.id,
        Refund.status.in_(["pending", "succeeded"]),
    ).scalar()
    pdf = build_receipt_pdf(
        workspace=owner.workspace_name or owner.name,
        merchant=owner.name,
        payer=link.payer_name or "Card payer",
        amount=payment.amount,
        currency=payment.currency,
        reference=payment.external_ref,
        paid_at=link.paid_at or payment.received_at,
        payment_rail=payment.rail,
        purpose=link.purpose_code,
        refunded_amount=float(refunded or 0),
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="receipt-{link.public_id}.pdf"'},
    )


@router.get("/payments/{payment_id}/receipt")
def payment_receipt(payment_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.user_id.in_(account_user_ids(db, user))).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    customer = db.get(Customer, payment.customer_id)
    refunds = db.query(Refund).filter(Refund.payment_id == payment.id, Refund.status.in_(["succeeded", "refunded", "completed"])).all()
    refunded_amount = sum(refund.amount for refund in refunds)
    pdf = build_receipt_pdf(
        workspace=user.workspace_name or user.name,
        merchant=user.name,
        payer=customer.name if customer else "Card payer",
        amount=payment.amount,
        currency=payment.currency,
        reference=payment.external_ref,
        paid_at=payment.received_at,
        payment_rail=payment.rail,
        purpose=f"Payment {payment.status}",
        refunded_amount=refunded_amount,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="receipt-payment-{payment.id}.pdf"'},
    )


@router.post("/quicklinks/{link_id}/refund", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
async def refund_quicklink(link_id: int, payload: RefundCreateIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    link = db.query(QuickLink).filter(QuickLink.id == link_id, QuickLink.user_id.in_(account_user_ids(db, user))).first()
    if not link or link.status not in {"paid", "partially_refunded", "refunded"} or not link.payment_id:
        raise HTTPException(status_code=409, detail="Only settled QuickLinks can be refunded")
    prior = db.query(Refund).filter(Refund.idempotency_key == payload.idempotency_key).first()
    if prior:
        return {
            "id": prior.id,
            "status": prior.status,
            "amount": prior.amount,
            "currency": prior.currency,
            "provider_ref": prior.provider_ref,
        }
    payment = db.get(Payment, link.payment_id)
    refunded = float(db.query(func.coalesce(func.sum(Refund.amount), 0)).filter(
        Refund.payment_id == payment.id,
        Refund.status.in_(["pending", "succeeded"]),
    ).scalar() or 0)
    remaining = round(payment.amount - refunded, 2)
    amount = round(payload.amount if payload.amount is not None else remaining, 2)
    if amount <= 0 or amount > remaining:
        raise HTTPException(status_code=409, detail=f"Refund must not exceed the remaining {payment.currency} {remaining:,.2f}")
    if link.provider_mode == "demo":
        result = type("DemoRefund", (), {
            "provider_ref": f"demo_refund_{payload.idempotency_key[-12:]}",
            "status": "succeeded",
            "amount": amount,
            "currency": payment.currency,
        })()
    else:
        result = await get_processor().refund(
            payment_ref=payment.external_ref,
            amount=amount,
            currency=payment.currency,
            reason=payload.reason,
            idempotency_key=payload.idempotency_key,
        )
    refund = Refund(
        user_id=link.user_id,
        payment_id=payment.id,
        amount=result.amount,
        currency=result.currency,
        reason=payload.reason,
        status=result.status,
        provider_ref=result.provider_ref,
        idempotency_key=payload.idempotency_key,
        completed_at=datetime.utcnow() if result.status == "succeeded" else None,
    )
    db.add(refund)
    total_refunded = round(refunded + result.amount, 2)
    next_status = "refunded" if total_refunded >= payment.amount else "partially_refunded"
    transition_quicklink(link, next_status)
    transition_payment(payment, next_status)
    record_audit(
        db,
        user=user,
        action="payment.refund.created",
        entity_type="payment",
        entity_id=payment.id,
        details={"amount": result.amount, "currency": result.currency, "reason": payload.reason, "quicklink_id": link.id},
    )
    db.commit()
    db.refresh(refund)
    enqueue_event(db, "payment.refunded", {"refund_id": refund.id, "payment_id": payment.id, "amount": refund.amount, "currency": refund.currency}, user_id=link.user_id)
    return {
        "id": refund.id,
        "status": refund.status,
        "amount": refund.amount,
        "currency": refund.currency,
        "provider_ref": refund.provider_ref,
        "quicklink_status": link.status,
    }


@router.post("/reconciliation", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
async def reconcile_payments(db: Session = Depends(get_db), user: User = Depends(current_user)):
    scope = account_user_ids(db, user)
    run = ReconciliationRun(user_id=user.id)
    db.add(run)
    db.flush()
    payments = db.query(Payment).filter(Payment.user_id.in_(scope)).order_by(Payment.received_at.desc()).limit(500).all()
    exceptions = []
    matched = 0
    seen_refs: dict[str, int] = {}
    for payment in payments:
        invoice = db.get(Invoice, payment.invoice_id) if payment.invoice_id else None
        issues = []
        if payment.external_ref and payment.external_ref in seen_refs:
            issues.append("duplicate_processor_reference")
        elif payment.external_ref:
            seen_refs[payment.external_ref] = payment.id
        if payment.amount <= 0:
            issues.append("invalid_amount")
        if invoice and round(invoice.amount, 2) != round(payment.amount, 2):
            issues.append("amount_mismatch")
        if invoice and invoice.currency.upper() != payment.currency.upper():
            issues.append("currency_mismatch")
        if invoice and payment.status in {"settled", "partially_refunded", "refunded"} and invoice.status != "paid":
            issues.append("invoice_not_marked_paid")
        if not payment.external_ref:
            issues.append("missing_processor_reference")
        if payment.status not in {"processing", "settled", "partially_refunded", "refunded", "disputed", "failed", "cancelled"}:
            issues.append("unknown_payment_status")
        if payment.status == "processing" and (datetime.utcnow() - payment.received_at).total_seconds() > 86400:
            issues.append("stale_processing_payment")
        if payment.rail == "Card checkout" and not payment.external_ref.startswith(("pi_", "cs_", "demo_card_")):
            issues.append("processor_reference_format")
        if issues:
            exceptions.append({"payment_id": payment.id, "external_ref": payment.external_ref, "issues": issues})
        else:
            matched += 1
    run.checked_count = len(payments)
    run.matched_count = matched
    run.exception_count = len(exceptions)
    run.exceptions = exceptions
    run.status = "completed"
    run.completed_at = datetime.utcnow()
    record_audit(
        db,
        user=user,
        action="reconciliation.completed",
        entity_type="reconciliation_run",
        entity_id=run.id,
        details={"checked": len(payments), "matched": matched, "exceptions": len(exceptions)},
    )
    db.commit()
    return {
        "id": run.id,
        "status": run.status,
        "checked_count": run.checked_count,
        "matched_count": run.matched_count,
        "exception_count": run.exception_count,
        "exceptions": run.exceptions,
        "completed_at": run.completed_at.isoformat(),
    }


@router.get("/reconciliation", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
def reconciliation_history(db: Session = Depends(get_db), user: User = Depends(current_user)):
    scope = account_user_ids(db, user)
    runs = db.query(ReconciliationRun).filter(ReconciliationRun.user_id.in_(scope)).order_by(ReconciliationRun.started_at.desc()).limit(25).all()
    return [
        {
            "id": run.id,
            "status": run.status,
            "checked_count": run.checked_count,
            "matched_count": run.matched_count,
            "exception_count": run.exception_count,
            "exceptions": run.exceptions,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }
        for run in runs
    ]


@router.get("/audit-log", dependencies=[Depends(require_roles(Role.admin))])
def audit_log(db: Session = Depends(get_db), user: User = Depends(current_user)):
    scope = account_user_ids(db, user)
    rows = db.query(AuditLog).filter(AuditLog.user_id.in_(scope)).order_by(AuditLog.created_at.desc()).limit(200).all()
    return [
        {
            "id": row.id,
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "outcome": row.outcome,
            "details": row.details,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.post("/stripe-webhook")
async def stripe_webhook(request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    event = await verified_stripe_event(request)
    stripe_event_id = event.get("id")
    duplicate = db.query(EventLog).filter(EventLog.external_id == stripe_event_id).first() if stripe_event_id else None
    if duplicate:
        return {"status": "already_processed", "event_id": duplicate.id}
    if event.get("type") == "charge.dispute.created":
        dispute = event.get("data", {}).get("object", {})
        payment_ref = dispute.get("payment_intent")
        payment = db.query(Payment).filter(Payment.external_ref == payment_ref).first() if payment_ref else None
        if payment:
            transition_payment(payment, "disputed")
            db.query(QuickLink).filter(QuickLink.payment_id == payment.id).update({"status": "disputed"})
            db.add(Alert(
                user_id=payment.user_id,
                severity="high",
                category="payment-dispute",
                message=f"Card dispute opened for {payment.currency} {payment.amount:,.2f}.",
                entity_type="payment",
                entity_id=payment.id,
            ))
            owner = db.get(User, payment.user_id) if payment.user_id else None
            record_audit(
                db,
                user=owner,
                action="payment.dispute.opened",
                entity_type="payment",
                entity_id=payment.id,
                details={"dispute_id": dispute.get("id"), "reason": dispute.get("reason")},
            )
            db.commit()
        stored = enqueue_event(db, "payment.dispute.opened", {"stripe_event_id": stripe_event_id, "payment_id": payment.id if payment else None, "dispute_id": dispute.get("id")}, user_id=payment.user_id if payment else None, external_id=stripe_event_id)
        return {"status": "processed", "event_id": stored.id}
    if event.get("type") == "charge.refunded":
        charge = event.get("data", {}).get("object", {})
        payment_ref = charge.get("payment_intent")
        payment = db.query(Payment).filter(Payment.external_ref == payment_ref).first() if payment_ref else None
        if payment:
            refunded_amount = (charge.get("amount_refunded") or 0) / 100
            next_status = "refunded" if refunded_amount >= payment.amount else "partially_refunded"
            transition_payment(payment, next_status)
            db.query(QuickLink).filter(QuickLink.payment_id == payment.id).update({"status": next_status})
            db.commit()
        stored = enqueue_event(db, "payment.refund.updated", {"stripe_event_id": stripe_event_id, "payment_id": payment.id if payment else None, "amount_refunded": (charge.get("amount_refunded") or 0) / 100}, user_id=payment.user_id if payment else None, external_id=stripe_event_id)
        return {"status": "processed", "event_id": stored.id}
    if event.get("type") not in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        stored = enqueue_event(db, "stripe.webhook.ignored", {"stripe_event_id": event.get("id"), "type": event.get("type")}, external_id=stripe_event_id)
        return {"status": "ignored", "event_id": stored.id}

    session = event.get("data", {}).get("object", {})
    metadata = session.get("metadata") or {}
    if (not metadata.get("invoice_id") and not metadata.get("quicklink_id")) or not metadata.get("ledgerops_user_id"):
        stored = enqueue_event(db, "stripe.webhook.ignored", {"stripe_event_id": stripe_event_id, "type": event.get("type"), "reason": "not_a_ledgerops_checkout"}, external_id=stripe_event_id)
        return {"status": "ignored", "event_id": stored.id}
    if event.get("type") == "checkout.session.completed" and session.get("payment_status") != "paid":
        stored = enqueue_event(db, "stripe.checkout.pending", {"stripe_event_id": stripe_event_id, "invoice_id": metadata.get("invoice_id")}, external_id=stripe_event_id)
        return {"status": "pending", "event_id": stored.id}
    quicklink_id = int(metadata["quicklink_id"]) if metadata.get("quicklink_id") else None
    invoice_id = int(metadata["invoice_id"]) if metadata.get("invoice_id") else None
    if quicklink_id:
        link = db.get(QuickLink, quicklink_id)
        if not link or str(link.user_id) != str(metadata.get("ledgerops_user_id")):
            raise HTTPException(status_code=403, detail="QuickLink ownership does not match checkout")
        payment, _customer = settle_quicklink(db, session, link)
        event_payload = {"stripe_event_id": event.get("id"), "quicklink_id": link.id, "external_ref": payment.external_ref}
    else:
        invoice, payment, _customer = record_completed_checkout(db, session, invoice_id)
        event_payload = {"stripe_event_id": event.get("id"), "invoice_id": invoice.id if invoice else invoice_id, "external_ref": payment.external_ref}
    stored = enqueue_event(db, "stripe.checkout.completed", event_payload, user_id=payment.user_id, external_id=stripe_event_id)
    background.add_task(process_event_background, stored.id)
    return {"status": "processed", "event_id": stored.id}


@router.post("/verify-checkout/{checkout_id}", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
async def verify_checkout(checkout_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    session = await retrieve_checkout_session(checkout_id)
    metadata = session.get("metadata") or {}
    invoice_id = int(metadata["invoice_id"]) if metadata.get("invoice_id") else None
    if not invoice_id:
        events = db.query(EventLog).filter(EventLog.user_id.in_(account_user_ids(db, user)), EventLog.event_type == "payment_link.created").order_by(EventLog.created_at.desc()).limit(50).all()
        event = next((item for item in events if item.payload.get("checkout_id") == checkout_id), None)
        invoice_id = event.payload.get("invoice_id") if event else None
    if session.get("payment_status") != "paid":
        return {
            "status": "unpaid",
            "checkout_id": checkout_id,
            "payment_status": session.get("payment_status", "unknown"),
            "message": "The card processor has not marked this checkout session as paid yet.",
        }
    invoice_record = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.user_id.in_(account_user_ids(db, user))).first() if invoice_id else None
    if not invoice_record:
        raise HTTPException(status_code=403, detail="Checkout session does not belong to this workspace")
    metadata_owner = (session.get("metadata") or {}).get("ledgerops_user_id")
    if metadata_owner and str(metadata_owner) != str(invoice_record.user_id):
        raise HTTPException(status_code=403, detail="Checkout ownership does not match the invoice")
    invoice, payment, customer = record_completed_checkout(db, session, invoice_id, user_id=invoice_record.user_id)
    stored = enqueue_event(db, "stripe.checkout.manually_verified", {"checkout_id": checkout_id, "invoice_id": invoice.id if invoice else invoice_id, "external_ref": payment.external_ref}, user_id=user.id)
    record_audit(
        db,
        user=user,
        action="checkout.manually_verified",
        entity_type="payment",
        entity_id=payment.id,
        details={"checkout_id": checkout_id, "invoice_id": invoice.id if invoice else invoice_id, "external_ref": payment.external_ref},
    )
    db.commit()
    return {
        "status": "verified",
        "checkout_id": checkout_id,
        "invoice_id": invoice.id if invoice else invoice_id,
        "invoice_number": invoice.invoice_number if invoice else None,
        "payment_id": payment.id,
        "recipient": customer.name,
        "amount": payment.amount,
        "currency": payment.currency,
        "event_id": stored.id,
    }


@router.post("/pay")
async def pay(payload: WalletTransferIn, background: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(current_user)):
    enforce_one_time_limit(db, user, payload.amount, payload.currency)
    prior = db.query(EventLog).filter(EventLog.user_id == user.id, EventLog.event_type == "wallet.payment.sent").order_by(EventLog.created_at.desc()).limit(100).all()
    prior_event = next((event for event in prior if event.payload.get("idempotency_key") == payload.idempotency_key), None)
    if prior_event:
        payment = db.get(Payment, prior_event.payload.get("payment_id"))
        if payment:
            return {"status": payment.status, "payment_id": payment.id, "external_ref": payment.external_ref, "recipient": payload.recipient_name, "amount": payment.amount, "currency": payment.currency, "funding_source": payment.rail}

    if is_demo_user(user):
        recipient = db.query(User).filter(User.email.in_(DEMO_EMAILS), User.id != user.id).first()
        if not recipient or payload.recipient_name != recipient.name:
            raise HTTPException(status_code=404, detail="Demo recipient not found")
        sender_wallet = db.query(DemoWallet).filter(DemoWallet.user_id == user.id).with_for_update().first()
        recipient_wallet = db.query(DemoWallet).filter(DemoWallet.user_id == recipient.id).with_for_update().first()
        amount_minor = int(round(payload.amount * 100))
        if not sender_wallet or not recipient_wallet:
            raise HTTPException(status_code=409, detail="Demo wallet is unavailable")
        if payload.currency != sender_wallet.currency or recipient_wallet.currency != sender_wallet.currency:
            raise HTTPException(status_code=400, detail="Demo wallets use INR")
        if amount_minor > sender_wallet.balance_minor:
            raise HTTPException(status_code=402, detail="Insufficient demo balance")

        sender_wallet.balance_minor -= amount_minor
        recipient_wallet.balance_minor += amount_minor
        reference = f"demo_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        sender_customer = demo_customer(db, user, recipient)
        recipient_customer = demo_customer(db, recipient, user)
        sender_payment = Payment(user_id=user.id, customer_id=sender_customer.id, amount=payload.amount, currency="INR", country="IN", status="settled", rail="LedgerOps Demo", external_ref=f"{reference}_out")
        recipient_payment = Payment(user_id=recipient.id, customer_id=recipient_customer.id, amount=payload.amount, currency="INR", country="IN", status="settled", rail="LedgerOps Demo", external_ref=f"{reference}_in")
        db.add_all([sender_payment, recipient_payment])
        db.flush()
        db.add_all([
            Transaction(user_id=user.id, payment_id=sender_payment.id, type="outbound", amount=payload.amount, currency="INR", country="IN", counterparty=recipient.name, risk_score=5),
            Transaction(user_id=recipient.id, payment_id=recipient_payment.id, type="inbound", amount=payload.amount, currency="INR", country="IN", counterparty=user.name, risk_score=5),
            DemoMessage(sender_id=user.id, recipient_id=recipient.id, kind="payment", text=f"Paid INR {payload.amount:,.2f}", note=payload.note, amount_minor=amount_minor, currency="INR", status="completed"),
        ])
        event = enqueue_event(db, "wallet.payment.sent", payload.model_dump() | {"payment_id": sender_payment.id, "external_ref": sender_payment.external_ref, "funding_source": "Demo balance"}, user_id=user.id)
        record_audit(
            db,
            user=user,
            action="wallet.payment.sent",
            entity_type="payment",
            entity_id=sender_payment.id,
            details={"recipient": recipient.name, "amount": payload.amount, "currency": "INR", "external_ref": sender_payment.external_ref, "demo": True},
        )
        db.commit()
        return {"status": "settled", "payment_id": sender_payment.id, "external_ref": sender_payment.external_ref, "recipient": recipient.name, "amount": payload.amount, "currency": "INR", "funding_source": "Demo balance", "event_id": event.id}

    provider = provider_status()
    if provider["mode"] == "stripe_live":
        raise HTTPException(status_code=501, detail="Live recipient payouts require connected recipient accounts and are not enabled yet. Use invoice checkout for live collections.")
    if not provider["connected"] and provider["mode"] != "demo":
        raise HTTPException(status_code=503, detail="Payment provider is not configured")
    method = None
    if payload.payment_method_id:
        method = db.query(PaymentMethod).filter(PaymentMethod.id == payload.payment_method_id, PaymentMethod.user_id == user.id).first()
        if not method:
            raise HTTPException(status_code=404, detail="Payment method not found")
    customer = db.query(Customer).filter(Customer.user_id.in_(account_user_ids(db, user)), Customer.name == payload.recipient_name).first()
    if not customer:
        customer = Customer(user_id=user.id, name=payload.recipient_name, country="US", currency=payload.currency, risk_rating="Medium", kyc_status="Review")
        db.add(customer)
        db.flush()
    if provider["connected"] and not method:
        raise HTTPException(status_code=400, detail="Select a securely saved payment card")
    card_charge = await charge_saved_card(method.provider_token if method else None, payload.amount, payload.currency, f"Payment to {payload.recipient_name}", f"ledgerops-pay-{user.id}-{payload.idempotency_key}")
    external_ref = card_charge["id"] if card_charge else f"wallet_pay_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    payment_rail = f"{method.brand} ending {method.last_four}" if method else payload.rail
    payment = Payment(
        customer_id=customer.id,
        user_id=user.id,
        amount=payload.amount,
        currency=payload.currency,
        country=customer.country,
        status="settled" if card_charge else "processing",
        rail=payment_rail,
        external_ref=external_ref,
    )
    db.add(payment)
    db.flush()
    db.add(Transaction(user_id=user.id, payment_id=payment.id, type="outbound", amount=payload.amount, currency=payload.currency, country=customer.country, counterparty=payload.recipient_name, risk_score=22))
    event = enqueue_event(db, "wallet.payment.sent", payload.model_dump() | {"payment_id": payment.id, "external_ref": external_ref, "funding_source": payment_rail}, user_id=user.id)
    record_audit(
        db,
        user=user,
        action="wallet.payment.sent",
        entity_type="payment",
        entity_id=payment.id,
        details={"recipient": payload.recipient_name, "amount": payload.amount, "currency": payload.currency, "external_ref": external_ref, "funding_source": payment_rail},
    )
    db.commit()
    background.add_task(process_event_background, event.id)
    return {"status": payment.status, "payment_id": payment.id, "external_ref": external_ref, "recipient": payload.recipient_name, "amount": payload.amount, "currency": payload.currency, "funding_source": payment_rail}


@router.post("/request", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
def request_money(payload: WalletRequestIn, background: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if is_demo_user(user):
        payer = db.query(User).filter(User.email.in_(DEMO_EMAILS), User.id != user.id).first()
        if not payer or payload.payer_name != payer.name:
            raise HTTPException(status_code=404, detail="Demo payer not found")
        wallet = db.query(DemoWallet).filter(DemoWallet.user_id == user.id).first()
        if not wallet or payload.currency != wallet.currency:
            raise HTTPException(status_code=400, detail="Demo wallets use INR")
        message = DemoMessage(sender_id=user.id, recipient_id=payer.id, kind="request", text=f"Requested INR {payload.amount:,.2f}", note=payload.note, amount_minor=int(round(payload.amount * 100)), currency="INR", status="pending")
        db.add(message)
        record_audit(
            db,
            user=user,
            action="wallet.payment.requested",
            entity_type="demo_message",
            details={"payer": payer.name, "amount": payload.amount, "currency": "INR", "demo": True},
        )
        db.commit()
        db.refresh(message)
        return {"status": "requested", "request_id": f"demo_request_{message.id}", "payer": payer.name, "amount": payload.amount, "currency": "INR"}
    request_id = f"wallet_req_{int(datetime.utcnow().timestamp())}"
    event = enqueue_event(db, "wallet.payment.requested", payload.model_dump() | {"request_id": request_id}, user_id=user.id)
    record_audit(
        db,
        user=user,
        action="wallet.payment.requested",
        entity_type="payment_request",
        entity_id=request_id,
        details={"payer": payload.payer_name, "amount": payload.amount, "currency": payload.currency},
    )
    db.commit()
    background.add_task(process_event_background, event.id)
    return {"status": "requested", "request_id": request_id, "payer": payload.payer_name, "amount": payload.amount, "currency": payload.currency}
