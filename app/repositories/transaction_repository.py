"""
Repository for transaction queries.
All filtering, pagination, and sorting is SQL-driven.
"""

import math
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func, desc, asc

from app.models.transaction import Transaction
from app.models.merchant import Merchant
from app.enums.status import PaymentStatus, SettlementStatus


class TransactionRepository:
    """Data-access layer for transaction reads and writes."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, transaction_id: str) -> Transaction | None:
        """Fetch a single transaction with merchant and events eagerly loaded."""
        stmt = (
            select(Transaction)
            .options(joinedload(Transaction.merchant))
            .where(Transaction.id == transaction_id)
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def create(
        self,
        transaction_id: str,
        merchant_id: str,
        amount,
        currency: str,
        payment_status: PaymentStatus,
        settlement_status: SettlementStatus,
        created_at: datetime,
    ) -> Transaction:
        """Create a new transaction record."""
        txn = Transaction(
            id=transaction_id,
            merchant_id=merchant_id,
            amount=amount,
            currency=currency,
            payment_status=payment_status,
            settlement_status=settlement_status,
            created_at=created_at,
            updated_at=created_at,
        )
        self.db.add(txn)
        return txn

    def update_status(
        self,
        transaction: Transaction,
        payment_status: PaymentStatus,
        settlement_status: SettlementStatus,
        updated_at: datetime,
    ) -> Transaction:
        """Update the payment/settlement status of an existing transaction."""
        transaction.payment_status = payment_status
        transaction.settlement_status = settlement_status
        transaction.updated_at = updated_at
        return transaction

    def list_filtered(
        self,
        merchant_id: str | None = None,
        payment_status: PaymentStatus | None = None,
        settlement_status: SettlementStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Transaction], int]:
        """
        List transactions with SQL-driven filtering, sorting, pagination.
        Returns (items, total_count).
        """
        # Base query with merchant join for name access
        base_query = select(Transaction).join(Merchant, Transaction.merchant_id == Merchant.id)
        count_query = select(func.count(Transaction.id))

        # Apply filters
        filters = []
        if merchant_id:
            filters.append(Transaction.merchant_id == merchant_id)
        if payment_status:
            filters.append(Transaction.payment_status == payment_status)
        if settlement_status:
            filters.append(Transaction.settlement_status == settlement_status)
        if date_from:
            filters.append(Transaction.created_at >= date_from)
        if date_to:
            filters.append(Transaction.created_at <= date_to)

        for f in filters:
            base_query = base_query.where(f)
            count_query = count_query.where(f)

        # Total count
        total = self.db.execute(count_query).scalar() or 0

        # Sorting
        sort_column_map = {
            "created_at": Transaction.created_at,
            "updated_at": Transaction.updated_at,
            "amount": Transaction.amount,
            "payment_status": Transaction.payment_status,
        }
        sort_col = sort_column_map.get(sort_by, Transaction.created_at)
        order_func = desc if sort_order.lower() == "desc" else asc
        base_query = base_query.order_by(order_func(sort_col))

        # Pagination
        offset = (page - 1) * page_size
        base_query = base_query.offset(offset).limit(page_size)

        items = self.db.execute(base_query).scalars().unique().all()

        return list(items), total
