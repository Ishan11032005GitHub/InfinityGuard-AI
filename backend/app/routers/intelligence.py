import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..auth import current_user, require_roles
from ..config import get_settings
from ..database import get_db
from ..models import ComplianceCheck, Customer, FXRate, Invoice, Payment, Prediction, Role, Transaction, User
from ..schemas import ComplianceIn, CopilotIn, PredictionProxyIn
from ..services.compliance import evaluate_compliance

router = APIRouter(prefix="/api", tags=["intelligence"])


@router.post("/compliance/check", dependencies=[Depends(require_roles(Role.admin, Role.finance_manager))])
def compliance_check(payload: ComplianceIn, db: Session = Depends(get_db)):
    result = evaluate_compliance(payload.model_dump())
    check = ComplianceCheck(entity_type=payload.entity_type, entity_id=payload.entity_id, score=result["score"], status=result["status"], recommendations=result["recommendations"])
    db.add(check)
    db.commit()
    return result | {"check_id": check.id}


async def call_ml(path: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.post(f"{get_settings().ml_service_url}{path}", json=payload)
        response.raise_for_status()
        return response.json()


@router.post("/predict/payment-delay")
async def payment_delay(payload: PredictionProxyIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    invoice = db.get(Invoice, payload.invoice_id) if payload.invoice_id else None
    customer = db.get(Customer, invoice.customer_id) if invoice else None
    body = payload.payload | ({
        "invoice_amount": invoice.amount,
        "country": invoice.country,
        "currency": invoice.currency,
        "client_history": customer.avg_delay_days,
        "delay_count": customer.delayed_invoice_count,
        "days_until_due": (invoice.due_date - invoice.issued_at).days,
    } if invoice and customer else {})
    result = await call_ml("/predict/payment-delay", body)
    db.add(Prediction(prediction_type="payment-delay", entity_type="invoice", entity_id=payload.invoice_id, score=result["delay_risk"], output=result))
    db.commit()
    return result


@router.post("/predict/fx")
async def fx_prediction(payload: PredictionProxyIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    rates = db.query(FXRate).order_by(FXRate.as_of.desc()).limit(90).all()
    body = payload.payload | {"rates": [{"currency": r.base_currency, "rate": r.rate, "volatility": r.volatility_score, "date": r.as_of.isoformat()} for r in rates]}
    result = await call_ml("/predict/fx", body)
    db.add(Prediction(prediction_type="fx", entity_type="currency", entity_id=None, score=result.get("volatility_score", 50), output=result))
    db.commit()
    return result


@router.post("/predict/anomaly")
async def anomaly(payload: PredictionProxyIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    tx = db.get(Transaction, payload.transaction_id) if payload.transaction_id else None
    body = payload.payload | ({"amount": tx.amount, "country": tx.country, "currency": tx.currency, "hour": tx.created_at.hour, "risk_score": tx.risk_score} if tx else {})
    result = await call_ml("/predict/anomaly", body)
    db.add(Prediction(prediction_type="anomaly", entity_type="transaction", entity_id=payload.transaction_id, score=result["anomaly_score"], output=result))
    db.commit()
    return result


@router.post("/predict/runway")
async def runway(payload: PredictionProxyIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    payments = db.query(Payment).order_by(Payment.received_at.desc()).limit(40).all()
    invoices = db.query(Invoice).filter(Invoice.status == "pending").all()
    body = payload.payload | {"incoming_payments": [p.amount for p in payments], "delayed_invoices": [i.amount for i in invoices], "expenses": 92000, "payroll": 58000}
    result = await call_ml("/predict/runway", body)
    db.add(Prediction(prediction_type="runway", entity_type="company", entity_id=None, score=result["projected_days"], output=result))
    db.commit()
    return result


@router.post("/copilot")
def copilot(payload: CopilotIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = payload.question.lower()
    pending = db.query(Invoice).filter(Invoice.status == "pending").all()
    risky_customers = db.query(Customer).filter(Customer.risk_rating.in_(["Medium", "High"])).all()
    recent_predictions = db.query(Prediction).order_by(Prediction.created_at.desc()).limit(8).all()
    exposure = {}
    for invoice in pending:
        exposure[invoice.currency] = exposure.get(invoice.currency, 0) + invoice.amount

    if "usd" in q or "conversion" in q or "fx" in q:
        answer = f"USD conversion can be staged. Current open exposure is {exposure}. Recent FX intelligence favors partial conversion when volatility is above 55, so avoid an all-at-once conversion unless payroll timing requires it."
    elif "cash" in q or "runway" in q:
        from datetime import date
        overdue = sum(1 for i in pending if i.due_date < date.today())
        answer = f"Cash flow risk is medium: {len(pending)} invoices are pending and {overdue} are overdue. The most useful action is accelerating high-value receivables before new discretionary spend."
    elif "dangerous" in q or "risky" in q or "invoices" in q:
        top = sorted(pending, key=lambda i: i.amount, reverse=True)[:3]
        answer = "Highest attention invoices: " + ", ".join(f"{i.invoice_number} {i.currency} {i.amount:,.0f} in {i.country}" for i in top)
    else:
        answer = f"I checked live system state: {len(pending)} pending invoices, {len(risky_customers)} medium/high-risk customers, and {len(recent_predictions)} recent model outputs. Ask about FX, runway, or risky invoices for a tighter recommendation."
    return {"answer": answer, "state_used": {"pending_invoices": len(pending), "currency_exposure": exposure, "recent_predictions": [p.output for p in recent_predictions[:3]]}}
