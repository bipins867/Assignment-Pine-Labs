"""
PaymentEvent ORM model — append-only audit log of all ingested events.
"""

from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, JSON, Enum, func
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.enums.status import EventType


class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(100), unique=True, nullable=False, index=True)
    transaction_id = Column(String(100), ForeignKey("transactions.id"), nullable=False, index=True)
    event_type = Column(
        Enum(EventType, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    amount = Column(Numeric(12, 2), nullable=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    raw_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    transaction = relationship("Transaction", back_populates="events")

    def __repr__(self) -> str:
        return f"<PaymentEvent(event_id={self.event_id}, type={self.event_type})>"
