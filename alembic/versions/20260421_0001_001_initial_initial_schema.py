"""Initial schema — merchants, transactions, payment_events

Revision ID: 001_initial
Revises:
Create Date: 2026-04-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Merchants ---
    op.create_table(
        "merchants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )

    # --- Transactions ---
    op.create_table(
        "transactions",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("merchant_id", sa.String(36), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column(
            "payment_status",
            sa.Enum("initiated", "processed", "failed", name="paymentstatus"),
            nullable=False,
            server_default="initiated",
        ),
        sa.Column(
            "settlement_status",
            sa.Enum("pending", "settled", "not_applicable", name="settlementstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    # Individual indexes
    op.create_index("ix_transactions_merchant_id", "transactions", ["merchant_id"])
    op.create_index("ix_transactions_payment_status", "transactions", ["payment_status"])
    op.create_index("ix_transactions_settlement_status", "transactions", ["settlement_status"])
    op.create_index("ix_transactions_created_at", "transactions", ["created_at"])

    # Composite indexes for query patterns
    op.create_index(
        "ix_transactions_merchant_payment", "transactions", ["merchant_id", "payment_status"]
    )
    op.create_index(
        "ix_transactions_merchant_settlement", "transactions", ["merchant_id", "settlement_status"]
    )
    op.create_index(
        "ix_transactions_status_updated",
        "transactions",
        ["payment_status", "settlement_status", "updated_at"],
    )

    # --- Payment Events ---
    op.create_table(
        "payment_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(100), nullable=False, unique=True),
        sa.Column(
            "transaction_id", sa.String(100), sa.ForeignKey("transactions.id"), nullable=False
        ),
        sa.Column(
            "event_type",
            sa.Enum(
                "payment_initiated",
                "payment_processed",
                "payment_failed",
                "settled",
                name="eventtype",
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("raw_payload", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )

    op.create_index("ix_payment_events_event_id", "payment_events", ["event_id"], unique=True)
    op.create_index("ix_payment_events_transaction_id", "payment_events", ["transaction_id"])
    op.create_index("ix_payment_events_timestamp", "payment_events", ["timestamp"])


def downgrade() -> None:
    op.drop_table("payment_events")
    op.drop_table("transactions")
    op.drop_table("merchants")
    # Drop enums (MySQL handles this implicitly, but explicit for clarity)
    op.execute("DROP TYPE IF EXISTS paymentstatus")
    op.execute("DROP TYPE IF EXISTS settlementstatus")
    op.execute("DROP TYPE IF EXISTS eventtype")
