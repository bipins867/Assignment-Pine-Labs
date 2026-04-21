"""
Event ingestion service — orchestrates idempotent event processing
with state machine transitions.
"""

import logging
from sqlalchemy.orm import Session

from app.repositories.event_repository import EventRepository
from app.repositories.transaction_repository import TransactionRepository
from app.enums.status import (
    EventType,
    PaymentStatus,
    SettlementStatus,
    STATE_TRANSITIONS,
    TERMINAL_STATES,
)
from app.schemas.event import EventRequest, EventResponse

logger = logging.getLogger(__name__)


class EventService:
    """Handles payment event ingestion with idempotency and state transitions."""

    def __init__(self, db: Session):
        self.db = db
        self.event_repo = EventRepository(db)
        self.txn_repo = TransactionRepository(db)

    def ingest_event(self, payload: EventRequest) -> EventResponse:
        """
        Process an incoming payment event.

        1. Check for duplicate event_id → return idempotent response
        2. Upsert merchant
        3. Create or update transaction with state machine logic
        4. Persist the event record
        5. Commit and return result
        """
        # Step 1: Duplicate check
        existing_event = self.event_repo.get_event_by_event_id(payload.event_id)
        if existing_event is not None:
            # Fetch current transaction state for response
            txn = self.txn_repo.get_by_id(payload.transaction_id)
            logger.info(f"Duplicate event ignored: {payload.event_id}")
            return EventResponse(
                status="duplicate",
                is_duplicate=True,
                event_id=payload.event_id,
                transaction_id=payload.transaction_id,
                payment_status=txn.payment_status if txn else "unknown",
                settlement_status=txn.settlement_status if txn else "unknown",
                message="Event already processed. No state change applied.",
            )

        # Step 2: Upsert merchant
        self.event_repo.upsert_merchant(payload.merchant_id, payload.merchant_name)

        # Step 3: Get or create transaction + apply state machine
        txn = self.txn_repo.get_by_id(payload.transaction_id)
        message = None

        if txn is None:
            # New transaction
            transition = STATE_TRANSITIONS.get((None, payload.event_type))
            if transition is None:
                # First event for this transaction isn't payment_initiated
                # Still create the transaction but derive state from event type
                new_ps, new_ss = self._derive_initial_state(payload.event_type)
                message = (
                    f"Transaction created from non-initial event '{payload.event_type.value}'. "
                    f"State derived as {new_ps.value}/{new_ss.value}."
                )
            else:
                new_ps, new_ss = transition

            txn = self.txn_repo.create(
                transaction_id=payload.transaction_id,
                merchant_id=payload.merchant_id,
                amount=payload.amount,
                currency=payload.currency,
                payment_status=new_ps,
                settlement_status=new_ss,
                created_at=payload.timestamp,
            )
            self.db.flush()
        else:
            # Existing transaction — check state machine
            current_state = (
                PaymentStatus(txn.payment_status),
                SettlementStatus(txn.settlement_status),
            )

            if current_state in TERMINAL_STATES:
                # Terminal state — event is preserved but state doesn't change
                message = (
                    f"Transaction in terminal state ({txn.payment_status}/{txn.settlement_status}). "
                    f"Event recorded but no state transition applied."
                )
                logger.info(
                    f"Event {payload.event_id} for terminal transaction {payload.transaction_id}"
                )
            else:
                transition_key = (PaymentStatus(txn.payment_status), payload.event_type)
                transition = STATE_TRANSITIONS.get(transition_key)

                if transition is not None:
                    new_ps, new_ss = transition
                    self.txn_repo.update_status(txn, new_ps, new_ss, payload.timestamp)
                    logger.info(
                        f"Transition: {payload.transaction_id} "
                        f"{txn.payment_status}->{new_ps.value}"
                    )
                else:
                    # Invalid transition — store event but don't change state
                    message = (
                        f"No valid transition from '{txn.payment_status}' via '{payload.event_type.value}'. "
                        f"Event recorded but state unchanged."
                    )
                    logger.warning(
                        f"Invalid transition for {payload.transaction_id}: "
                        f"{txn.payment_status} + {payload.event_type.value}"
                    )

        # Step 4: Always persist the event
        self.event_repo.create_event(
            event_id=payload.event_id,
            transaction_id=payload.transaction_id,
            event_type=payload.event_type.value,
            amount=payload.amount,
            timestamp=payload.timestamp,
            raw_payload=payload.model_dump(mode="json"),
        )

        # Step 5: Commit
        self.db.commit()
        self.db.refresh(txn)

        return EventResponse(
            status="accepted",
            is_duplicate=False,
            event_id=payload.event_id,
            transaction_id=txn.id,
            payment_status=txn.payment_status,
            settlement_status=txn.settlement_status,
            message=message,
        )

    def _derive_initial_state(
        self, event_type: EventType
    ) -> tuple[PaymentStatus, SettlementStatus]:
        """
        Derive initial transaction state when the first event
        is not payment_initiated (out-of-order scenario).
        """
        mapping = {
            EventType.PAYMENT_INITIATED: (PaymentStatus.INITIATED, SettlementStatus.PENDING),
            EventType.PAYMENT_PROCESSED: (PaymentStatus.PROCESSED, SettlementStatus.PENDING),
            EventType.PAYMENT_FAILED: (PaymentStatus.FAILED, SettlementStatus.NOT_APPLICABLE),
            EventType.SETTLED: (PaymentStatus.PROCESSED, SettlementStatus.SETTLED),
        }
        return mapping.get(
            event_type,
            (PaymentStatus.INITIATED, SettlementStatus.PENDING),
        )
