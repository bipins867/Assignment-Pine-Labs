"""
Transaction endpoints — GET /transactions, GET /transactions/{transaction_id}
"""

from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.schemas.transaction import TransactionListItem, TransactionDetail
from app.schemas.common import PaginatedResponse
from app.services.transaction_service import TransactionService
from app.enums.status import PaymentStatus, SettlementStatus

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get(
    "",
    response_model=PaginatedResponse[TransactionListItem],
    summary="List Transactions",
    description=(
        "List transactions with optional filtering by merchant, status, and date range. "
        "Supports pagination and sorting. All filtering and aggregation is SQL-driven."
    ),
)
def list_transactions(
    merchant_id: str | None = Query(None, description="Filter by merchant ID"),
    payment_status: PaymentStatus | None = Query(None, description="Filter by payment status"),
    settlement_status: SettlementStatus | None = Query(None, description="Filter by settlement status"),
    date_from: datetime | None = Query(None, description="Filter from date (ISO 8601)"),
    date_to: datetime | None = Query(None, description="Filter to date (ISO 8601)"),
    sort_by: str = Query(
        "created_at",
        description="Sort field",
        pattern="^(created_at|updated_at|amount|payment_status)$",
    ),
    sort_order: str = Query(
        "desc",
        description="Sort direction",
        pattern="^(asc|desc)$",
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    db: Session = Depends(get_db),
):
    """List transactions with filters, pagination, and sorting."""
    service = TransactionService(db)
    return service.list_transactions(
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


@router.get(
    "/{transaction_id}",
    response_model=TransactionDetail,
    summary="Get Transaction Detail",
    description=(
        "Retrieve complete details for a specific transaction, including "
        "current payment/settlement status, merchant information, and "
        "the full event history sorted chronologically."
    ),
    responses={
        404: {"description": "Transaction not found"},
    },
)
def get_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
):
    """Get a single transaction with full event history."""
    service = TransactionService(db)
    return service.get_transaction_detail(transaction_id)
