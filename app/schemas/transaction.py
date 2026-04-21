"""
Pydantic schemas for transaction list/detail responses.
"""

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field

from app.enums.status import PaymentStatus, SettlementStatus, EventType


class TransactionEventItem(BaseModel):
    """Single event in a transaction's history."""
    event_id: str
    event_type: EventType
    amount: Decimal | None
    timestamp: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionListItem(BaseModel):
    """Transaction item in paginated list response."""
    id: str
    merchant_id: str
    merchant_name: str | None = None
    amount: Decimal
    currency: str
    payment_status: PaymentStatus
    settlement_status: SettlementStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TransactionDetail(BaseModel):
    """Full transaction detail with event history."""
    id: str
    merchant_id: str
    merchant_name: str | None = None
    amount: Decimal
    currency: str
    payment_status: PaymentStatus
    settlement_status: SettlementStatus
    created_at: datetime
    updated_at: datetime
    events: list[TransactionEventItem] = Field(
        default_factory=list,
        description="Full event history, ordered by timestamp ascending",
    )
    event_count: int = Field(0, description="Total number of events")

    model_config = {"from_attributes": True}
