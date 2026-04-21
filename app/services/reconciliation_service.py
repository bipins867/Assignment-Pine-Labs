"""
Reconciliation service — summary aggregation and discrepancy detection.
"""

from decimal import Decimal
from sqlalchemy.orm import Session

from app.repositories.reconciliation_repository import ReconciliationRepository
from app.schemas.reconciliation import (
    ReconciliationSummaryResponse,
    ReconciliationGroupItem,
    ReconciliationTotals,
    DiscrepancyResponse,
    DiscrepancyItem,
    DiscrepancySummary,
)
from app.enums.status import DiscrepancyType
from app.core.config import get_settings


class ReconciliationService:
    """Business logic for reconciliation queries."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = ReconciliationRepository(db)

    def get_summary(
        self,
        group_by: str = "merchant",
        merchant_id: str | None = None,
        date_from=None,
        date_to=None,
    ) -> ReconciliationSummaryResponse:
        """Get reconciliation summary with flexible grouping."""
        group_method_map = {
            "merchant": self.repo.get_summary_by_merchant,
            "date": self.repo.get_summary_by_date,
            "status": self.repo.get_summary_by_status,
        }

        get_groups = group_method_map.get(group_by, self.repo.get_summary_by_merchant)
        raw_groups = get_groups(
            merchant_id=merchant_id,
            date_from=date_from,
            date_to=date_to,
        )

        groups = [ReconciliationGroupItem(**g) for g in raw_groups]

        totals_raw = self.repo.get_totals(
            merchant_id=merchant_id,
            date_from=date_from,
            date_to=date_to,
        )
        totals = ReconciliationTotals(**totals_raw)

        return ReconciliationSummaryResponse(
            group_by=group_by,
            groups=groups,
            totals=totals,
        )

    def get_discrepancies(
        self,
        stale_after_hours: float | None = None,
        merchant_id: str | None = None,
        discrepancy_type: DiscrepancyType | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> DiscrepancyResponse:
        """Detect and return reconciliation discrepancies."""
        settings = get_settings()
        threshold = stale_after_hours or settings.DEFAULT_STALE_AFTER_HOURS

        items_raw, summary_raw = self.repo.get_discrepancies(
            stale_after_hours=threshold,
            merchant_id=merchant_id,
            discrepancy_type=discrepancy_type,
            page=page,
            page_size=page_size,
        )

        items = [DiscrepancyItem(**item) for item in items_raw]
        summary = DiscrepancySummary(**summary_raw)

        return DiscrepancyResponse(
            items=items,
            total=summary.total,
            summary=summary,
            stale_after_hours=threshold,
        )
