RESTRICTED_COUNTRIES = {"IR", "KP", "SY", "CU"}


def evaluate_compliance(payload: dict) -> dict:
    score = 100
    recommendations: list[str] = []

    if payload.get("country") in RESTRICTED_COUNTRIES:
        score -= 45
        recommendations.append("Escalate restricted-country exposure before settlement.")
    if payload.get("amount", 0) >= 50000:
        score -= 18
        recommendations.append("Collect enhanced due diligence for large transaction.")
    if "kyc" not in [doc.lower() for doc in payload.get("documents", [])]:
        score -= 15
        recommendations.append("Attach current KYC document package.")
    invoice_amount = payload.get("invoice_amount")
    if invoice_amount and abs(invoice_amount - payload.get("amount", 0)) > max(invoice_amount * 0.05, 100):
        score -= 22
        recommendations.append("Resolve invoice amount mismatch before reconciliation.")
    if not payload.get("payer_name"):
        score -= 10
        recommendations.append("Verify payer identity against customer account.")

    score = max(score, 0)
    status = "pass" if score >= 80 else "review" if score >= 55 else "blocked"
    if not recommendations:
        recommendations.append("No material compliance gaps detected.")
    return {"score": score, "status": status, "recommendations": recommendations}
