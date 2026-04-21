"""
Pydantic schemas for event ingestion request/response.
"""

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator

from app.enums.status import EventType


class EventRequest(BaseModel):
    """Incoming payment event payload."""

    event_id: str = Field(
        ..., min_length=1, max_length=100,
        description="Unique identifier for this event (idempotency key)",
    )
    event_type: EventType = Field(
        ..., description="Type of payment event",
    )
    transaction_id: str = Field(
        ..., min_length=1, max_length=100,
        description="Transaction this event belongs to",
    )
    merchant_id: str = Field(
        ..., min_length=1, max_length=36,
        description="Merchant identifier",
    )
    merchant_name: str = Field(
        ..., min_length=1, max_length=255,
        description="Merchant display name",
    )
    amount: Decimal = Field(
        ..., gt=0, max_digits=12, decimal_places=2,
        description="Transaction amount (must be positive)",
    )
    currency: str = Field(
        default="INR", min_length=3, max_length=3,
        description="ISO 4217 currency code",
    )
    timestamp: datetime = Field(
        ..., description="When this event occurred (ISO 8601)",
    )

    @field_validator("currency")
    @classmethod
    def currency_uppercase(cls, v: str) -> str:
        return v.upper()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "event_id": "evt_001",
                    "event_type": "payment_initiated",
                    "transaction_id": "txn_001",
                    "merchant_id": "merchant_A",
                    "merchant_name": "Acme Corp",
                    "amount": 1500.00,
                    "currency": "INR",
                    "timestamp": "2026-04-20T10:30:00Z",
                }
            ]
        }
    }


class EventResponse(BaseModel):
    """Response after event ingestion."""

    status: str = Field(..., description="'accepted' or 'duplicate'")
    is_duplicate: bool = Field(..., description="True if event was already ingested")
    event_id: str
    transaction_id: str
    payment_status: str
    settlement_status: str
    message: str | None = None
