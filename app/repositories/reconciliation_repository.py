"""
Repository for reconciliation queries.
All aggregation and discrepancy detection is SQL-driven.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select, func, case, and_, literal

from app.models.transaction import Transaction
from app.models.merchant import Merchant
from app.models.payment_event import PaymentEvent
from app.enums.status import PaymentStatus, SettlementStatus, DiscrepancyType


class ReconciliationRepository:
    """Data-access layer for reconciliation summary and discrepancy detection."""

    def __init__(self, db: Session):
        self.db = db

    def get_summary_by_merchant(
        self,
        merchant_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict]:
        """Aggregate reconciliation data grouped by merchant."""
        return self._get_summary(
            group_col=Transaction.merchant_id,
            group_label="merchant_id",
            merchant_id=merchant_id,
            date_from=date_from,
            date_to=date_to,
        )

    def get_summary_by_date(
        self,
        merchant_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict]:
        """Aggregate reconciliation data grouped by date."""
        date_col = func.date(Transaction.created_at)
        return self._get_summary(
            group_col=date_col,
            group_label="date",
            merchant_id=merchant_id,
            date_from=date_from,
            date_to=date_to,
        )

    def get_summary_by_status(
        self,
        merchant_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict]:
        """Aggregate reconciliation data grouped by payment_status + settlement_status."""
        # Use concatenated status as group key
        group_col = func.concat(Transaction.payment_status, ":", Transaction.settlement_status)
        return self._get_summary(
            group_col=group_col,
            group_label="status",
            merchant_id=merchant_id,
            date_from=date_from,
            date_to=date_to,
        )

    def _get_summary(
        self,
        group_col,
        group_label: str,
        merchant_id: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[dict]:
        """Internal helper: build and run aggregation query."""
        stmt = select(
            group_col.label("group_key"),
            func.count(Transaction.id).label("total_transactions"),
            func.coalesce(func.sum(Transaction.amount), 0).label("total_amount"),
            func.sum(
                case((Transaction.payment_status == PaymentStatus.INITIATED.value, 1), else_=0)
            ).label("initiated_count"),
            func.sum(
                case((Transaction.payment_status == PaymentStatus.PROCESSED.value, 1), else_=0)
            ).label("processed_count"),
            func.sum(
                case((Transaction.payment_status == PaymentStatus.FAILED.value, 1), else_=0)
            ).label("failed_count"),
            func.sum(
                case((Transaction.settlement_status == SettlementStatus.SETTLED.value, 1), else_=0)
            ).label("settled_count"),
            func.sum(
                case(
                    (Transaction.settlement_status == SettlementStatus.PENDING.value, 1), else_=0
                )
            ).label("pending_settlement_count"),
            func.coalesce(
                func.sum(
                    case(
                        (Transaction.settlement_status == SettlementStatus.SETTLED.value, Transaction.amount),
                        else_=0,
                    )
                ),
                0,
            ).label("settled_amount"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                Transaction.payment_status == PaymentStatus.PROCESSED.value,
                                Transaction.settlement_status == SettlementStatus.PENDING.value,
                            ),
                            Transaction.amount,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("unsettled_amount"),
        )

        # Apply filters
        if merchant_id:
            stmt = stmt.where(Transaction.merchant_id == merchant_id)
        if date_from:
            stmt = stmt.where(Transaction.created_at >= date_from)
        if date_to:
            stmt = stmt.where(Transaction.created_at <= date_to)

        stmt = stmt.group_by(group_col).order_by(group_col)

        rows = self.db.execute(stmt).all()
        return [
            {
                "group_key": str(row.group_key),
                "total_transactions": row.total_transactions,
                "total_amount": Decimal(str(row.total_amount)),
                "initiated_count": row.initiated_count,
                "processed_count": row.processed_count,
                "failed_count": row.failed_count,
                "settled_count": row.settled_count,
                "pending_settlement_count": row.pending_settlement_count,
                "settled_amount": Decimal(str(row.settled_amount)),
                "unsettled_amount": Decimal(str(row.unsettled_amount)),
            }
            for row in rows
        ]

    def get_totals(
        self,
        merchant_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict:
        """Get overall reconciliation totals (not grouped)."""
        stmt = select(
            func.count(Transaction.id).label("total_transactions"),
            func.coalesce(func.sum(Transaction.amount), 0).label("total_amount"),
            func.sum(
                case((Transaction.settlement_status == SettlementStatus.SETTLED.value, 1), else_=0)
            ).label("total_settled"),
            func.sum(
                case(
                    (
                        and_(
                            Transaction.payment_status.in_([
                                PaymentStatus.INITIATED.value,
                                PaymentStatus.PROCESSED.value,
                            ]),
                            Transaction.settlement_status == SettlementStatus.PENDING.value,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("total_unsettled"),
            func.sum(
                case((Transaction.payment_status == PaymentStatus.FAILED.value, 1), else_=0)
            ).label("total_failed"),
        )

        if merchant_id:
            stmt = stmt.where(Transaction.merchant_id == merchant_id)
        if date_from:
            stmt = stmt.where(Transaction.created_at >= date_from)
        if date_to:
            stmt = stmt.where(Transaction.created_at <= date_to)

        row = self.db.execute(stmt).one()

        total_processed = row.total_settled + (
            row.total_unsettled if row.total_unsettled else 0
        )
        settlement_rate = (
            round((row.total_settled / total_processed) * 100, 2)
            if total_processed > 0
            else 0.0
        )

        return {
            "total_transactions": row.total_transactions,
            "total_amount": Decimal(str(row.total_amount)),
            "total_settled": row.total_settled,
            "total_unsettled": row.total_unsettled,
            "total_failed": row.total_failed,
            "settlement_rate": settlement_rate,
        }

    def get_discrepancies(
        self,
        stale_after_hours: float = 24.0,
        merchant_id: str | None = None,
        discrepancy_type: DiscrepancyType | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], dict]:
        """
        Detect reconciliation discrepancies via SQL queries.
        Returns (items, summary_counts).

        Discrepancy rules:
        1. unsettled_processed — processed but settlement still pending after threshold
        2. invalid_settlement — settled but payment_status is failed
        3. premature_settlement — settled but payment_status is still initiated
        4. stale_initiated — initiated and no progress after threshold
        5. duplicate_conflict — transactions with multiple events of the same type
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=stale_after_hours)

        # Subquery for last event time per transaction
        last_event_subq = (
            select(
                PaymentEvent.transaction_id,
                func.max(PaymentEvent.timestamp).label("last_event_at"),
            )
            .group_by(PaymentEvent.transaction_id)
            .subquery()
        )

        # Subquery for duplicate event type detection
        dup_event_subq = (
            select(
                PaymentEvent.transaction_id,
            )
            .group_by(PaymentEvent.transaction_id, PaymentEvent.event_type)
            .having(func.count(PaymentEvent.id) > 1)
            .subquery()
        )

        all_discrepancies = []

        # --- Rule 1: unsettled_processed ---
        if discrepancy_type is None or discrepancy_type == DiscrepancyType.UNSETTLED_PROCESSED:
            stmt = (
                select(
                    Transaction.id,
                    Transaction.merchant_id,
                    Merchant.name.label("merchant_name"),
                    Transaction.amount,
                    Transaction.payment_status,
                    Transaction.settlement_status,
                    Transaction.created_at,
                    last_event_subq.c.last_event_at,
                    literal(DiscrepancyType.UNSETTLED_PROCESSED.value).label("discrepancy_type"),
                    literal("Payment processed but not settled within threshold").label("description"),
                )
                .join(Merchant, Transaction.merchant_id == Merchant.id)
                .outerjoin(last_event_subq, Transaction.id == last_event_subq.c.transaction_id)
                .where(
                    and_(
                        Transaction.payment_status == PaymentStatus.PROCESSED.value,
                        Transaction.settlement_status == SettlementStatus.PENDING.value,
                        Transaction.updated_at < cutoff_time,
                    )
                )
            )
            if merchant_id:
                stmt = stmt.where(Transaction.merchant_id == merchant_id)
            rows = self.db.execute(stmt).all()
            all_discrepancies.extend(self._rows_to_dicts(rows))

        # --- Rule 2: invalid_settlement ---
        if discrepancy_type is None or discrepancy_type == DiscrepancyType.INVALID_SETTLEMENT:
            stmt = (
                select(
                    Transaction.id,
                    Transaction.merchant_id,
                    Merchant.name.label("merchant_name"),
                    Transaction.amount,
                    Transaction.payment_status,
                    Transaction.settlement_status,
                    Transaction.created_at,
                    last_event_subq.c.last_event_at,
                    literal(DiscrepancyType.INVALID_SETTLEMENT.value).label("discrepancy_type"),
                    literal("Settlement recorded for a failed payment").label("description"),
                )
                .join(Merchant, Transaction.merchant_id == Merchant.id)
                .outerjoin(last_event_subq, Transaction.id == last_event_subq.c.transaction_id)
                .where(
                    and_(
                        Transaction.payment_status == PaymentStatus.FAILED.value,
                        Transaction.settlement_status == SettlementStatus.SETTLED.value,
                    )
                )
            )
            if merchant_id:
                stmt = stmt.where(Transaction.merchant_id == merchant_id)
            rows = self.db.execute(stmt).all()
            all_discrepancies.extend(self._rows_to_dicts(rows))

        # --- Rule 3: premature_settlement ---
        if discrepancy_type is None or discrepancy_type == DiscrepancyType.PREMATURE_SETTLEMENT:
            stmt = (
                select(
                    Transaction.id,
                    Transaction.merchant_id,
                    Merchant.name.label("merchant_name"),
                    Transaction.amount,
                    Transaction.payment_status,
                    Transaction.settlement_status,
                    Transaction.created_at,
                    last_event_subq.c.last_event_at,
                    literal(DiscrepancyType.PREMATURE_SETTLEMENT.value).label("discrepancy_type"),
                    literal("Settlement recorded without payment being processed").label("description"),
                )
                .join(Merchant, Transaction.merchant_id == Merchant.id)
                .outerjoin(last_event_subq, Transaction.id == last_event_subq.c.transaction_id)
                .where(
                    and_(
                        Transaction.payment_status == PaymentStatus.INITIATED.value,
                        Transaction.settlement_status == SettlementStatus.SETTLED.value,
                    )
                )
            )
            if merchant_id:
                stmt = stmt.where(Transaction.merchant_id == merchant_id)
            rows = self.db.execute(stmt).all()
            all_discrepancies.extend(self._rows_to_dicts(rows))

        # --- Rule 4: stale_initiated ---
        if discrepancy_type is None or discrepancy_type == DiscrepancyType.STALE_INITIATED:
            stmt = (
                select(
                    Transaction.id,
                    Transaction.merchant_id,
                    Merchant.name.label("merchant_name"),
                    Transaction.amount,
                    Transaction.payment_status,
                    Transaction.settlement_status,
                    Transaction.created_at,
                    last_event_subq.c.last_event_at,
                    literal(DiscrepancyType.STALE_INITIATED.value).label("discrepancy_type"),
                    literal("Payment initiated but no further events within threshold").label("description"),
                )
                .join(Merchant, Transaction.merchant_id == Merchant.id)
                .outerjoin(last_event_subq, Transaction.id == last_event_subq.c.transaction_id)
                .where(
                    and_(
                        Transaction.payment_status == PaymentStatus.INITIATED.value,
                        Transaction.settlement_status == SettlementStatus.PENDING.value,
                        Transaction.updated_at < cutoff_time,
                    )
                )
            )
            if merchant_id:
                stmt = stmt.where(Transaction.merchant_id == merchant_id)
            rows = self.db.execute(stmt).all()
            all_discrepancies.extend(self._rows_to_dicts(rows))

        # --- Rule 5: duplicate_conflict ---
        if discrepancy_type is None or discrepancy_type == DiscrepancyType.DUPLICATE_CONFLICT:
            stmt = (
                select(
                    Transaction.id,
                    Transaction.merchant_id,
                    Merchant.name.label("merchant_name"),
                    Transaction.amount,
                    Transaction.payment_status,
                    Transaction.settlement_status,
                    Transaction.created_at,
                    last_event_subq.c.last_event_at,
                    literal(DiscrepancyType.DUPLICATE_CONFLICT.value).label("discrepancy_type"),
                    literal("Multiple events of same type detected for transaction").label("description"),
                )
                .join(Merchant, Transaction.merchant_id == Merchant.id)
                .outerjoin(last_event_subq, Transaction.id == last_event_subq.c.transaction_id)
                .where(Transaction.id.in_(select(dup_event_subq.c.transaction_id)))
            )
            if merchant_id:
                stmt = stmt.where(Transaction.merchant_id == merchant_id)
            rows = self.db.execute(stmt).all()
            all_discrepancies.extend(self._rows_to_dicts(rows))

        # Build summary
        summary = {
            "unsettled_processed": 0,
            "invalid_settlement": 0,
            "premature_settlement": 0,
            "stale_initiated": 0,
            "duplicate_conflict": 0,
            "total": 0,
        }
        # Deduplicate by transaction_id (a txn can match multiple rules)
        seen = set()
        unique_discrepancies = []
        for d in all_discrepancies:
            key = (d["transaction_id"], d["discrepancy_type"])
            if key not in seen:
                seen.add(key)
                unique_discrepancies.append(d)
                summary[d["discrepancy_type"]] += 1
                summary["total"] += 1

        # Paginate in-memory (discrepancy count is typically small)
        total = len(unique_discrepancies)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = unique_discrepancies[start:end]

        return paginated, summary

    def _rows_to_dicts(self, rows) -> list[dict]:
        """Convert SQL result rows to dicts."""
        return [
            {
                "transaction_id": row.id,
                "merchant_id": row.merchant_id,
                "merchant_name": row.merchant_name,
                "amount": row.amount,
                "payment_status": row.payment_status,
                "settlement_status": row.settlement_status,
                "discrepancy_type": row.discrepancy_type,
                "description": row.description,
                "last_event_at": row.last_event_at,
                "created_at": row.created_at,
            }
            for row in rows
        ]
