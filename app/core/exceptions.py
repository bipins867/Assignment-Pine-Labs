"""
Custom exception classes for structured error handling.
"""

from fastapi import HTTPException, status


class DuplicateEventError(Exception):
    """Raised when an event with the same event_id already exists."""

    def __init__(self, event_id: str, transaction_id: str):
        self.event_id = event_id
        self.transaction_id = transaction_id
        super().__init__(f"Duplicate event: {event_id}")


class InvalidStateTransitionError(Exception):
    """Raised when an event would cause an invalid state transition."""

    def __init__(self, transaction_id: str, current_status: str, event_type: str):
        self.transaction_id = transaction_id
        self.current_status = current_status
        self.event_type = event_type
        super().__init__(
            f"Invalid transition for {transaction_id}: "
            f"{current_status} -> {event_type}"
        )


class TransactionNotFoundError(Exception):
    """Raised when a transaction is not found."""

    def __init__(self, transaction_id: str):
        self.transaction_id = transaction_id
        super().__init__(f"Transaction not found: {transaction_id}")
