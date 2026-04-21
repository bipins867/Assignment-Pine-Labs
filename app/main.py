"""
FastAPI application entrypoint.
Payment Event Ingestion & Reconciliation Service.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.v1.router import router as v1_router
from app.middleware.error_handler import register_exception_handlers

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Payment Reconciliation Service",
    description=(
        "A production-minded backend service for payment event ingestion and reconciliation. "
        "Supports idempotent event processing, transaction lifecycle tracking, and "
        "automated discrepancy detection across payment and settlement states."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers
register_exception_handlers(app)

# Include API router
app.include_router(v1_router)


@app.get("/", tags=["System"])
async def root():
    """Root endpoint providing service information."""
    return {
        "service": "Payment Reconciliation API",
        "status": "online",
        "documentation": "/docs",
        "health_check": "/api/v1/health",
        "version": "1.0.0"
    }


@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting Payment Reconciliation Service ({settings.APP_ENV})")
    logger.info(f"Database: {settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Payment Reconciliation Service")
