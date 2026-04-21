"""
Enums for payment status, settlement status, and event types.
These drive the state machine and reconciliation logic.
"""

import enum


class EventType(str, enum.Enum):
    """Types of payment events that can be ingested."""
    PAYMENT_INITIATED = "payment_initiated"
    PAYMENT_PROCESSED = "payment_processed"
    PAYMENT_FAILED = "payment_failed"
    SETTLED = "settled"


class PaymentStatus(str, enum.Enum):
    """Current payment status of a transaction."""
    INITIATED = "initiated"
    PROCESSED = "processed"
    FAILED = "failed"


class SettlementStatus(str, enum.Enum):
    """Current settlement status of a transaction."""
    PENDING = "pending"
    SETTLED = "settled"
    NOT_APPLICABLE = "not_applicable"


class DiscrepancyType(str, enum.Enum):
    """Categories of reconciliation discrepancies."""
    UNSETTLED_PROCESSED = "unsettled_processed"
    INVALID_SETTLEMENT = "invalid_settlement"
    PREMATURE_SETTLEMENT = "premature_settlement"
    STALE_INITIATED = "stale_initiated"
    DUPLICATE_CONFLICT = "duplicate_conflict"


# --- State Machine Transition Map ---
# Maps (current_payment_status, event_type) -> (new_payment_status, new_settlement_status)
# None as current status means the transaction does not yet exist.
STATE_TRANSITIONS: dict[
    tuple[PaymentStatus | None, EventType],
    tuple[PaymentStatus, SettlementStatus] | None,
] = {
    # New transaction creation
    (None, EventType.PAYMENT_INITIATED): (PaymentStatus.INITIATED, SettlementStatus.PENDING),
    # Normal forward transitions
    (PaymentStatus.INITIATED, EventType.PAYMENT_PROCESSED): (PaymentStatus.PROCESSED, SettlementStatus.PENDING),
    (PaymentStatus.INITIATED, EventType.PAYMENT_FAILED): (PaymentStatus.FAILED, SettlementStatus.NOT_APPLICABLE),
    (PaymentStatus.PROCESSED, EventType.SETTLED): (PaymentStatus.PROCESSED, SettlementStatus.SETTLED),
    (PaymentStatus.PROCESSED, EventType.PAYMENT_FAILED): (PaymentStatus.FAILED, SettlementStatus.NOT_APPLICABLE),
}

# Terminal states — no further transitions allowed from these
TERMINAL_STATES: set[tuple[PaymentStatus, SettlementStatus]] = {
    (PaymentStatus.FAILED, SettlementStatus.NOT_APPLICABLE),
    (PaymentStatus.PROCESSED, SettlementStatus.SETTLED),
}
