from collections import defaultdict
from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..auth import current_user
from ..database import get_db
from ..models import Alert, Customer, FXRate, Invoice, Payment, Transaction, User

router = APIRouter(prefix="/api", tags=["finance"])


def rows(items):
    return [item.__dict__ | {"_sa_instance_state": None} for item in items]


@router.get("/payments")
def payments(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.query(Payment).order_by(Payment.received_at.desc()).limit(100).all()


@router.get("/invoices")
def invoices(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.query(Invoice).order_by(Invoice.due_date.asc()).limit(100).all()


@router.get("/customers")
def customers(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.query(Customer).order_by(Customer.name.asc()).all()


@router.get("/transactions")
def transactions(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.query(Transaction).order_by(Transaction.created_at.desc()).limit(150).all()


@router.get("/fx-rates")
def fx_rates(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.query(FXRate).order_by(FXRate.as_of.desc()).limit(250).all()


@router.get("/alerts")
def alerts(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.query(Alert).order_by(Alert.created_at.desc()).limit(30).all()


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    total = db.query(func.coalesce(func.sum(Payment.amount), 0)).scalar()
    pending = db.query(Invoice).filter(Invoice.status == "pending").count()
    transactions = db.query(Transaction).order_by(Transaction.created_at.asc()).all()
    invoices = db.query(Invoice).all()
    fx = db.query(FXRate).order_by(FXRate.as_of.asc()).all()
    alerts = db.query(Alert).order_by(Alert.created_at.desc()).limit(8).all()

    monthly = defaultdict(float)
    cash = defaultdict(lambda: {"in": 0, "out": 0})
    heat = defaultdict(float)
    exposure = defaultdict(float)
    anomalies = []
    for tx in transactions:
        key = tx.created_at.strftime("%b")
        monthly[key] += tx.amount
        cash[key]["in"] += tx.amount
        heat[tx.country] += tx.amount
        exposure[tx.currency] += tx.amount
        if tx.risk_score > 65:
            anomalies.append({"name": tx.counterparty, "score": tx.risk_score, "amount": tx.amount})
    for inv in invoices:
        if inv.status == "pending":
            exposure[inv.currency] += inv.amount
    fx_trends = [{"date": rate.as_of.isoformat(), "currency": rate.base_currency, "rate": rate.rate, "volatility": rate.volatility_score} for rate in fx[-90:]]
    risk_score = round(sum(a["score"] for a in anomalies) / max(len(anomalies), 1), 1)
    runway = max(21, 82 - pending * 3)
    return {
        "total_volume": round(total, 2),
        "pending_invoices": pending,
        "cash_runway": runway,
        "currency_exposure": dict(exposure),
        "risk_score": risk_score,
        "alerts": [{"severity": a.severity, "category": a.category, "message": a.message} for a in alerts],
        "monthly_transactions": [{"month": k, "volume": round(v, 2)} for k, v in monthly.items()],
        "cash_flow": [{"month": k, "incoming": round(v["in"], 2), "expenses": round(v["in"] * 0.58, 2)} for k, v in cash.items()],
        "fx_trends": fx_trends,
        "country_heatmap": [{"country": k, "volume": round(v, 2)} for k, v in heat.items()],
        "anomalies": anomalies[:12],
    }
