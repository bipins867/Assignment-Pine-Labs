"""
Pydantic schemas for reconciliation summary and discrepancy responses.
"""

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field

from app.enums.status import DiscrepancyType


class ReconciliationGroupItem(BaseModel):
    """A single group in the reconciliation summary."""
    group_key: str = Field(..., description="Grouping key value (merchant_id, date, or status)")
    total_transactions: int
    total_amount: Decimal
    initiated_count: int = 0
    processed_count: int = 0
    failed_count: int = 0
    settled_count: int = 0
    pending_settlement_count: int = 0
    settled_amount: Decimal = Decimal("0")
    unsettled_amount: Decimal = Decimal("0")


class ReconciliationTotals(BaseModel):
    """Overall totals across all groups."""
    total_transactions: int
    total_amount: Decimal
    total_settled: int
    total_unsettled: int
    total_failed: int
    settlement_rate: float = Field(..., description="Percentage of processed transactions that are settled")


class ReconciliationSummaryResponse(BaseModel):
    """Full reconciliation summary response."""
    group_by: str
    groups: list[ReconciliationGroupItem]
    totals: ReconciliationTotals


class DiscrepancyItem(BaseModel):
    """Single discrepancy record."""
    transaction_id: str
    merchant_id: str
    merchant_name: str | None = None
    amount: Decimal
    payment_status: str
    settlement_status: str
    discrepancy_type: DiscrepancyType
    description: str
    last_event_at: datetime | None = None
    created_at: datetime


class DiscrepancySummary(BaseModel):
    """Summary of discrepancies by type."""
    unsettled_processed: int = 0
    invalid_settlement: int = 0
    premature_settlement: int = 0
    stale_initiated: int = 0
    duplicate_conflict: int = 0
    total: int = 0


class DiscrepancyResponse(BaseModel):
    """Full discrepancy detection response."""
    items: list[DiscrepancyItem]
    total: int
    summary: DiscrepancySummary
    stale_after_hours: float = Field(..., description="Threshold used for staleness detection")
