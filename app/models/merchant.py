"""
Merchant ORM model.
"""

from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    transactions = relationship("Transaction", back_populates="merchant", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Merchant(id={self.id}, name={self.name})>"
