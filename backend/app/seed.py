from datetime import date, datetime, timedelta
from random import Random
from sqlalchemy.orm import Session
from .auth import hash_password
from .models import Alert, Customer, FXRate, Invoice, Payment, Role, Transaction, User


def seed(db: Session) -> None:
    if db.query(User).first():
        return

    db.add_all([
        User(email="admin@infinityguard.ai", name="Avery Shah", hashed_password=hash_password("AdminPass123"), role=Role.admin),
        User(email="finance@infinityguard.ai", name="Mira Chen", hashed_password=hash_password("FinancePass123"), role=Role.finance_manager),
        User(email="viewer@infinityguard.ai", name="Leo Grant", hashed_password=hash_password("ViewerPass123"), role=Role.viewer),
    ])

    customers = [
        Customer(name="Northstar Robotics", country="US", currency="USD", risk_rating="Low", avg_delay_days=2, delayed_invoice_count=1, kyc_status="Verified"),
        Customer(name="Kairo Retail Group", country="AE", currency="AED", risk_rating="Medium", avg_delay_days=7, delayed_invoice_count=3, kyc_status="Verified"),
        Customer(name="Blue Harbor GmbH", country="DE", currency="EUR", risk_rating="Low", avg_delay_days=1, delayed_invoice_count=0, kyc_status="Verified"),
        Customer(name="Sakura Supply KK", country="JP", currency="JPY", risk_rating="Medium", avg_delay_days=9, delayed_invoice_count=4, kyc_status="Review"),
        Customer(name="Atlas Minerals", country="ZA", currency="ZAR", risk_rating="High", avg_delay_days=13, delayed_invoice_count=5, kyc_status="Review"),
        Customer(name="Maple Cloud Ltd", country="CA", currency="CAD", risk_rating="Low", avg_delay_days=3, delayed_invoice_count=1, kyc_status="Verified"),
    ]
    db.add_all(customers)
    db.flush()

    rng = Random(42)
    today = date.today()
    invoices: list[Invoice] = []
    payments: list[Payment] = []
    transactions: list[Transaction] = []
    for idx in range(42):
        customer = customers[idx % len(customers)]
        issued = today - timedelta(days=idx * 6 + 8)
        due = issued + timedelta(days=30)
        amount = round(rng.uniform(3500, 85000), 2)
        paid = idx % 4 != 0
        paid_at = due + timedelta(days=rng.randint(-3, 16)) if paid else None
        invoice = Invoice(
            invoice_number=f"INV-{2026}-{1000 + idx}",
            customer_id=customer.id,
            amount=amount,
            currency=customer.currency,
            country=customer.country,
            status="paid" if paid else "pending",
            issued_at=issued,
            due_date=due,
            paid_at=paid_at,
            metadata_json={"contract": "cross-border services", "payment_terms": "net30"},
        )
        invoices.append(invoice)
        db.add(invoice)
        db.flush()
        if paid:
            payment = Payment(
                invoice_id=invoice.id,
                customer_id=customer.id,
                amount=amount,
                currency=customer.currency,
                country=customer.country,
                status="settled",
                rail="ACH" if customer.country in {"US", "CA"} else "SWIFT",
                received_at=datetime.combine(paid_at, datetime.min.time()) + timedelta(hours=rng.randint(8, 22)),
                external_ref=f"pay_{idx:05d}",
            )
            payments.append(payment)
            db.add(payment)
            db.flush()
            transactions.append(Transaction(
                payment_id=payment.id,
                type="inbound",
                amount=amount,
                currency=customer.currency,
                country=customer.country,
                counterparty=customer.name,
                risk_score=min(92, customer.avg_delay_days * 4 + rng.randint(8, 30)),
                created_at=payment.received_at,
            ))

    fx_series = {"EUR": 1.08, "GBP": 1.26, "JPY": 0.0067, "AED": 0.272, "CAD": 0.73, "ZAR": 0.054, "USD": 1.0}
    for ccy, base in fx_series.items():
        for day in range(30):
            db.add(FXRate(
                base_currency=ccy,
                quote_currency="USD",
                rate=round(base * (1 + rng.uniform(-0.025, 0.025)), 5),
                volatility_score=round(rng.uniform(12, 78), 2),
                as_of=today - timedelta(days=day),
            ))
    db.add_all(transactions)
    db.add_all([
        Alert(severity="high", category="fraud", message="JPY payment pattern changed outside normal settlement window.", entity_type="transaction", entity_id=8),
        Alert(severity="medium", category="fx", message="EUR exposure rose 18% while volatility is trending upward.", entity_type="fx", entity_id=None),
        Alert(severity="medium", category="cash", message="Delayed invoices could reduce runway below 60 days.", entity_type="forecast", entity_id=None),
    ])
    db.commit()
