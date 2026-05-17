from datetime import datetime
import redis
from tenacity import retry, stop_after_attempt, wait_exponential
from sqlalchemy.orm import Session
from ..config import get_settings
from ..models import Alert, EventLog


def enqueue_event(db: Session, event_type: str, payload: dict) -> EventLog:
    event = EventLog(event_type=event_type, payload=payload, status="queued")
    db.add(event)
    db.commit()
    db.refresh(event)
    try:
        client = redis.from_url(get_settings().redis_url, decode_responses=True)
        client.lpush("infinityguard:events", str(event.id))
    except redis.RedisError:
        event.last_error = "Redis unavailable; event retained for API-side processing"
        db.commit()
    return event


@retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3))
def process_event(db: Session, event: EventLog) -> None:
    event.attempts += 1
    payload = event.payload
    if event.event_type == "payment.received" and payload.get("amount", 0) > 75000:
        db.add(Alert(
            severity="high",
            category="large-payment",
            message=f"Large {payload.get('currency')} payment received from {payload.get('customer_name')}",
            entity_type="payment",
            entity_id=payload.get("payment_id"),
        ))
    if event.event_type == "invoice.created" and payload.get("amount", 0) > 40000:
        db.add(Alert(
            severity="medium",
            category="invoice-exposure",
            message=f"High-value invoice {payload.get('invoice_number')} needs delay-risk scoring",
            entity_type="invoice",
            entity_id=payload.get("invoice_id"),
        ))
    event.status = "processed"
    event.processed_at = datetime.utcnow()
    db.commit()
