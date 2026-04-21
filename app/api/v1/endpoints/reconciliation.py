"""
Reconciliation endpoints — GET /reconciliation/summary, GET /reconciliation/discrepancies
"""

from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.schemas.reconciliation import ReconciliationSummaryResponse, DiscrepancyResponse
from app.services.reconciliation_service import ReconciliationService
from app.enums.status import DiscrepancyType

router = APIRouter(prefix="/reconciliation", tags=["Reconciliation"])


@router.get(
    "/summary",
    response_model=ReconciliationSummaryResponse,
    summary="Reconciliation Summary",
    description=(
        "Get an aggregated reconciliation summary. Supports grouping by merchant, date, or status. "
        "All aggregation is performed in SQL for efficiency. The response includes per-group "
        "breakdowns and overall totals with settlement rate."
    ),
)
def reconciliation_summary(
    group_by: str = Query(
        "merchant",
        description="Grouping dimension",
        pattern="^(merchant|date|status)$",
    ),
    merchant_id: str | None = Query(None, description="Filter by merchant ID"),
    date_from: datetime | None = Query(None, description="Filter from date (ISO 8601)"),
    date_to: datetime | None = Query(None, description="Filter to date (ISO 8601)"),
    db: Session = Depends(get_db),
):
    """Get reconciliation summary with flexible grouping."""
    service = ReconciliationService(db)
    return service.get_summary(
        group_by=group_by,
        merchant_id=merchant_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/discrepancies",
    response_model=DiscrepancyResponse,
    summary="Detect Discrepancies",
    description=(
        "Detect reconciliation discrepancies across all transactions. "
        "Discrepancy rules:\n\n"
        "1. **unsettled_processed** — Payment processed but not settled within `stale_after_hours` threshold\n"
        "2. **invalid_settlement** — Settlement recorded for a failed payment\n"
        "3. **premature_settlement** — Settlement recorded without payment being processed\n"
        "4. **stale_initiated** — Payment initiated but no further events within threshold\n"
        "5. **duplicate_conflict** — Multiple events of the same type for one transaction\n\n"
        "The `stale_after_hours` parameter controls the staleness threshold for rules 1 and 4. "
        "Default is 24 hours. Rules 2 and 3 are absolute invariant violations."
    ),
)
def reconciliation_discrepancies(
    stale_after_hours: float | None = Query(
        None,
        gt=0,
        le=8760,
        description=(
            "Hours threshold for staleness-based discrepancy detection. "
            "Default: 24 hours. Must be > 0 and <= 8760 (1 year)."
        ),
    ),
    merchant_id: str | None = Query(None, description="Filter by merchant ID"),
    discrepancy_type: DiscrepancyType | None = Query(
        None, description="Filter by specific discrepancy type"
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page (max 200)"),
    db: Session = Depends(get_db),
):
    """Detect and return reconciliation discrepancies."""
    service = ReconciliationService(db)
    return service.get_discrepancies(
        stale_after_hours=stale_after_hours,
        merchant_id=merchant_id,
        discrepancy_type=discrepancy_type,
        page=page,
        page_size=page_size,
    )
