"""
Global exception handlers — maps domain exceptions to HTTP responses.
"""

import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    DuplicateEventError,
    InvalidStateTransitionError,
    TransactionNotFoundError,
)

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers on the FastAPI app."""

    @app.exception_handler(TransactionNotFoundError)
    async def transaction_not_found_handler(request: Request, exc: TransactionNotFoundError):
        return JSONResponse(
            status_code=404,
            content={
                "detail": str(exc),
                "error_code": "TRANSACTION_NOT_FOUND",
            },
        )

    @app.exception_handler(DuplicateEventError)
    async def duplicate_event_handler(request: Request, exc: DuplicateEventError):
        return JSONResponse(
            status_code=200,
            content={
                "detail": str(exc),
                "error_code": "DUPLICATE_EVENT",
            },
        )

    @app.exception_handler(InvalidStateTransitionError)
    async def invalid_transition_handler(request: Request, exc: InvalidStateTransitionError):
        return JSONResponse(
            status_code=409,
            content={
                "detail": str(exc),
                "error_code": "INVALID_STATE_TRANSITION",
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        logger.error(f"Database integrity error: {exc}")
        return JSONResponse(
            status_code=409,
            content={
                "detail": "A database constraint was violated. Possible duplicate.",
                "error_code": "INTEGRITY_ERROR",
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An internal server error occurred.",
                "error_code": "INTERNAL_ERROR",
            },
        )
