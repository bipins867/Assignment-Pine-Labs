"""
Transaction service — handles listing and detail retrieval.
"""

import math
from sqlalchemy.orm import Session

from app.repositories.transaction_repository import TransactionRepository
from app.core.exceptions import TransactionNotFoundError
from app.schemas.transaction import TransactionListItem, TransactionDetail, TransactionEventItem
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.enums.status import PaymentStatus, SettlementStatus


class TransactionService:
    """Business logic for transaction queries."""

    def __init__(self, db: Session):
        self.db = db
        self.txn_repo = TransactionRepository(db)

    def list_transactions(
        self,
        merchant_id: str | None = None,
        payment_status: PaymentStatus | None = None,
        settlement_status: SettlementStatus | None = None,
        date_from=None,
        date_to=None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[TransactionListItem]:
        """List transactions with filtering, sorting, pagination."""
        items, total = self.txn_repo.list_filtered(
            merchant_id=merchant_id,
            payment_status=payment_status,
            settlement_status=settlement_status,
            date_from=date_from,
            date_to=date_to,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

        total_pages = math.ceil(total / page_size) if total > 0 else 0

        transaction_items = []
        for txn in items:
            merchant_name = txn.merchant.name if txn.merchant else None
            transaction_items.append(
                TransactionListItem(
                    id=txn.id,
                    merchant_id=txn.merchant_id,
                    merchant_name=merchant_name,
                    amount=txn.amount,
                    currency=txn.currency,
                    payment_status=txn.payment_status,
                    settlement_status=txn.settlement_status,
                    created_at=txn.created_at,
                    updated_at=txn.updated_at,
                )
            )

        return PaginatedResponse(
            items=transaction_items,
            pagination=PaginationMeta(
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            ),
        )

    def get_transaction_detail(self, transaction_id: str) -> TransactionDetail:
        """Get full transaction detail with event history."""
        txn = self.txn_repo.get_by_id(transaction_id)
        if txn is None:
            raise TransactionNotFoundError(transaction_id)

        merchant_name = txn.merchant.name if txn.merchant else None
        events = [
            TransactionEventItem(
                event_id=evt.event_id,
                event_type=evt.event_type,
                amount=evt.amount,
                timestamp=evt.timestamp,
                created_at=evt.created_at,
            )
            for evt in sorted(txn.events, key=lambda e: e.timestamp)
        ]

        return TransactionDetail(
            id=txn.id,
            merchant_id=txn.merchant_id,
            merchant_name=merchant_name,
            amount=txn.amount,
            currency=txn.currency,
            payment_status=txn.payment_status,
            settlement_status=txn.settlement_status,
            created_at=txn.created_at,
            updated_at=txn.updated_at,
            events=events,
            event_count=len(events),
        )
