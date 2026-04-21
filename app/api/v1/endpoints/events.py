"""
Event ingestion endpoint — POST /events
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.schemas.event import EventRequest, EventResponse
from app.services.event_service import EventService

router = APIRouter(prefix="/events", tags=["Events"])


@router.post(
    "",
    response_model=EventResponse,
    summary="Ingest Payment Event",
    description=(
        "Ingest a payment lifecycle event. Events are processed idempotently — "
        "submitting the same event_id multiple times is safe and returns the existing "
        "transaction state without modification. The event is always persisted for audit, "
        "but the transaction state only transitions according to the defined state machine."
    ),
    responses={
        201: {"description": "Event accepted and processed"},
        200: {"description": "Duplicate event — already processed (idempotent)"},
        422: {"description": "Validation error in request payload"},
    },
)
def ingest_event(
    payload: EventRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Process a payment event with idempotency guarantees."""
    service = EventService(db)
    result = service.ingest_event(payload)

    # Set appropriate HTTP status code
    if result.is_duplicate:
        response.status_code = 200
    else:
        response.status_code = 201

    return result
