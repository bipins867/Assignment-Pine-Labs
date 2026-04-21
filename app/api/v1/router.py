"""
V1 API router — aggregates all endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import health, events, transactions, reconciliation

router = APIRouter(prefix="/api/v1")

router.include_router(health.router)
router.include_router(events.router)
router.include_router(transactions.router)
router.include_router(reconciliation.router)
