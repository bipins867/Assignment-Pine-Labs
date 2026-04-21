"""
Repository for payment event persistence.
Handles idempotent event insertion and merchant upsert.
"""

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.payment_event import PaymentEvent
from app.models.merchant import Merchant


class EventRepository:
    """Data-access layer for payment events and merchants."""

    def __init__(self, db: Session):
        self.db = db

    def get_event_by_event_id(self, event_id: str) -> PaymentEvent | None:
        """Check if an event with this event_id already exists."""
        stmt = select(PaymentEvent).where(PaymentEvent.event_id == event_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create_event(
        self,
        event_id: str,
        transaction_id: str,
        event_type: str,
        amount: float | None,
        timestamp,
        raw_payload: dict | None = None,
    ) -> PaymentEvent:
        """Insert a new event record (append-only)."""
        event = PaymentEvent(
            event_id=event_id,
            transaction_id=transaction_id,
            event_type=event_type,
            amount=amount,
            timestamp=timestamp,
            raw_payload=raw_payload,
        )
        self.db.add(event)
        return event

    def upsert_merchant(self, merchant_id: str, merchant_name: str) -> Merchant:
        """Get or create a merchant record."""
        merchant = self.db.get(Merchant, merchant_id)
        if merchant is None:
            merchant = Merchant(id=merchant_id, name=merchant_name)
            self.db.add(merchant)
            self.db.flush()
        return merchant
