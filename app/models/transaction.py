"""
Transaction ORM model — holds the derived current state of each transaction.
"""

from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey, Index, Enum, func
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.enums.status import PaymentStatus, SettlementStatus


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String(100), primary_key=True)
    merchant_id = Column(String(36), ForeignKey("merchants.id"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    payment_status = Column(
        Enum(PaymentStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        default=PaymentStatus.INITIATED,
        index=True,
    )
    settlement_status = Column(
        Enum(SettlementStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        default=SettlementStatus.PENDING,
        index=True,
    )
    created_at = Column(DateTime, nullable=False, index=True)
    updated_at = Column(DateTime, nullable=False, onupdate=func.now())

    # Relationships
    merchant = relationship("Merchant", back_populates="transactions")
    events = relationship(
        "PaymentEvent",
        back_populates="transaction",
        order_by="PaymentEvent.timestamp",
        lazy="selectin",
    )

    # Composite indexes for common query patterns
    __table_args__ = (
        Index("ix_transactions_merchant_payment", "merchant_id", "payment_status"),
        Index("ix_transactions_merchant_settlement", "merchant_id", "settlement_status"),
        Index("ix_transactions_status_updated", "payment_status", "settlement_status", "updated_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Transaction(id={self.id}, payment={self.payment_status}, "
            f"settlement={self.settlement_status})>"
        )
