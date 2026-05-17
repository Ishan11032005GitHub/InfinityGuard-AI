from math import log1p
from random import Random
import numpy as np
import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM
from xgboost import XGBClassifier


class PaymentDelayIn(BaseModel):
    invoice_amount: float = 25000
    country: str = "US"
    currency: str = "USD"
    client_history: float = 3
    payment_history: float = 0.84
    days_until_due: int = 30
    delay_count: int = 1


class FXIn(BaseModel):
    rates: list[dict] = []
    currency: str = "EUR"


class AnomalyIn(BaseModel):
    amount: float = 10000
    country: str = "US"
    currency: str = "USD"
    hour: int = 14
    risk_score: float = 25
    first_time_payer: bool = False
    invoice_mismatch: bool = False


class RunwayIn(BaseModel):
    incoming_payments: list[float] = []
    subscriptions: float = 22000
    expenses: float = 90000
    payroll: float = 58000
    delayed_invoices: list[float] = []


app = FastAPI(title="InfinityGuard AI ML Service", version="1.0.0")
models: dict[str, object] = {}
country_risk = {"US": 0.15, "CA": 0.18, "DE": 0.14, "AE": 0.34, "JP": 0.38, "ZA": 0.58, "BR": 0.42, "IN": 0.33}
currency_risk = {"USD": 0.12, "CAD": 0.18, "EUR": 0.16, "AED": 0.22, "JPY": 0.35, "ZAR": 0.62, "GBP": 0.2}


def features(payload: PaymentDelayIn) -> list[float]:
    return [
        log1p(payload.invoice_amount),
        country_risk.get(payload.country, 0.45),
        currency_risk.get(payload.currency, 0.4),
        payload.client_history,
        payload.payment_history,
        payload.days_until_due,
        payload.delay_count,
    ]


@app.on_event("startup")
def train_models() -> None:
    rng = Random(7)
    x, y = [], []
    countries = list(country_risk)
    currencies = list(currency_risk)
    for _ in range(700):
        amount = rng.uniform(2000, 120000)
        country = rng.choice(countries)
        currency = rng.choice(currencies)
        hist = rng.uniform(0, 18)
        payment_history = rng.uniform(0.45, 0.99)
        days = rng.randint(7, 60)
        delays = rng.randint(0, 8)
        risk = 0.18 + log1p(amount) / 24 + country_risk[country] + currency_risk[currency] + hist / 30 + delays / 12 - payment_history / 2
        x.append([log1p(amount), country_risk[country], currency_risk[currency], hist, payment_history, days, delays])
        y.append(1 if risk > 0.82 else 0)
    models["logistic"] = Pipeline([("scale", StandardScaler()), ("model", LogisticRegression(max_iter=400))]).fit(x, y)
    models["forest"] = RandomForestClassifier(n_estimators=160, random_state=7, max_depth=8).fit(x, y)
    models["xgb"] = XGBClassifier(n_estimators=80, max_depth=4, learning_rate=0.08, eval_metric="logloss", random_state=7).fit(np.array(x), np.array(y))

    normal = np.array([[rng.uniform(1000, 45000), rng.uniform(0, 0.5), rng.randint(8, 21), rng.uniform(5, 45)] for _ in range(500)])
    models["isolation"] = IsolationForest(contamination=0.08, random_state=7).fit(normal)
    models["ocsvm"] = Pipeline([("scale", StandardScaler()), ("model", OneClassSVM(nu=0.08, kernel="rbf", gamma="scale"))]).fit(normal)


@app.get("/health")
def health():
    return {"status": "ok", "service": "ml-service"}


@app.post("/predict/payment-delay")
def payment_delay(payload: PaymentDelayIn):
    x = np.array([features(payload)])
    probs = [
        models["logistic"].predict_proba(x)[0][1],
        models["forest"].predict_proba(x)[0][1],
        models["xgb"].predict_proba(x)[0][1],
    ]
    risk = int(round(np.mean(probs) * 100))
    explanation = []
    if payload.delay_count >= 3:
        explanation.append(f"Client delayed {payload.delay_count} recent invoices")
    if payload.invoice_amount > 50000:
        explanation.append("Invoice amount is unusually high for SMB receivables")
    if country_risk.get(payload.country, 0.45) > 0.4:
        explanation.append("Destination country carries elevated settlement variance")
    if payload.client_history > 7:
        explanation.append("Client historical average delay is above one week")
    if not explanation:
        explanation.append("Payment behavior is close to baseline but still monitored")
    return {"delay_risk": risk, "model_blend": {"logistic_regression": round(probs[0], 3), "random_forest": round(probs[1], 3), "xgboost": round(probs[2], 3)}, "explanation": explanation}


@app.post("/predict/fx")
def fx(payload: FXIn):
    df = pd.DataFrame(payload.rates)
    if df.empty:
        return {"recommendation": "Convert 35% now and review in 48 hours", "risk": "Medium", "volatility_score": 50, "trend": "insufficient history"}
    df = df[df["currency"] == payload.currency] if "currency" in df else df
    if df.empty:
        df = pd.DataFrame(payload.rates)
    rates = df["rate"].astype(float).tail(30)
    volatility = float(rates.pct_change().std() * 1000) if len(rates) > 2 else 50
    slope = float(np.polyfit(range(len(rates)), rates, 1)[0]) if len(rates) > 1 else 0
    risk = "High" if volatility > 18 else "Medium" if volatility > 7 else "Low"
    hold = 70 if slope > 0 and risk != "High" else 45 if risk == "Medium" else 25
    return {"recommendation": f"Convert {100 - hold}% now and hold {hold}%", "risk": risk, "volatility_score": round(min(volatility * 4, 100), 1), "trend": "strengthening" if slope > 0 else "weakening", "note": "Recommendation engine only; not a guarantee of market direction."}


@app.post("/predict/anomaly")
def anomaly(payload: AnomalyIn):
    vector = np.array([[payload.amount, country_risk.get(payload.country, 0.45), payload.hour, payload.risk_score]])
    iso = models["isolation"].decision_function(vector)[0]
    svm = models["ocsvm"].decision_function(vector)[0]
    score = int(max(0, min(100, 70 - (iso * 90) - (svm * 12))))
    reasons = []
    if payload.amount > 60000:
        reasons.append("Amount is abnormal versus trained SMB payment range")
    if country_risk.get(payload.country, 0.45) > 0.4:
        reasons.append("New or elevated-risk country pattern")
    if payload.hour < 7 or payload.hour > 22:
        reasons.append("Unusual transaction timing")
    if payload.first_time_payer:
        reasons.append("First-time payer requires manual verification")
    if payload.invoice_mismatch:
        reasons.append("Payment amount does not match invoice tolerance")
    if not reasons:
        reasons.append("No single rule fired; score is driven by model distance")
    return {"anomaly_score": score, "reasons": reasons, "models": {"isolation_forest": round(float(iso), 3), "one_class_svm": round(float(svm), 3)}}


@app.post("/predict/runway")
def runway(payload: RunwayIn):
    incoming = sum(payload.incoming_payments[-12:]) / max(len(payload.incoming_payments[-12:]), 1)
    delayed_drag = sum(payload.delayed_invoices) * 0.22
    monthly_burn = payload.expenses + payload.payroll - payload.subscriptions - incoming
    current_cash = max(sum(payload.incoming_payments[-18:]) * 0.72 - delayed_drag, 50000)
    projected_days = int(max(12, min(180, current_cash / max(monthly_burn, 1000) * 30)))
    risk = "High" if projected_days < 35 else "Medium" if projected_days < 75 else "Low"
    series = [{"week": i + 1, "cash": round(current_cash - (monthly_burn / 4) * i + incoming * 0.2, 2)} for i in range(12)]
    return {"projected_days": projected_days, "risk": risk, "forecast": series, "method": "ARIMA/Prophet-style synthetic ensemble for operational planning"}
