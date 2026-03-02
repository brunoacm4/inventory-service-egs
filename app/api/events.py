from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.event import EventCreate, EventUpdate, EventResponse, EventListResponse
from app.schemas.common import ErrorResponse
from app.services.event_service import EventService
from app.utils.database import get_db
from app.utils.config import settings

router = APIRouter(prefix="/api/v1/events", tags=["Events"])

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    if not api_key or api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key


@router.post(
    "",
    response_model=EventResponse,
    status_code=201,
    summary="Create an event",
    description="Create a new event in the inventory catalog. The event starts in 'draft' status.",
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def create_event(
    data: EventCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    event = await EventService.create_event(db, data)
    return event


@router.get(
    "",
    response_model=EventListResponse,
    summary="List events",
    description="Retrieve a paginated list of events. Optionally filter by status.",
    responses={401: {"model": ErrorResponse}},
)
async def list_events(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max records to return"),
    status: Optional[str] = Query(None, description="Filter by status: draft, published, cancelled, sold_out, completed"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    events, total = await EventService.list_events(db, skip=skip, limit=limit, status=status)
    return EventListResponse(data=events, total=total, skip=skip, limit=limit)


@router.get(
    "/{event_id}",
    response_model=EventResponse,
    summary="Get event details",
    description="Retrieve detailed information about a specific event.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    event = await EventService.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.put(
    "/{event_id}",
    response_model=EventResponse,
    summary="Update an event",
    description="Update one or more fields of an existing event.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def update_event(
    event_id: UUID,
    data: EventUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    event = await EventService.update_event(db, event_id, data)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.delete(
    "/{event_id}",
    status_code=204,
    summary="Delete an event",
    description="Delete an event and all associated ticket categories and reservations.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def delete_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    deleted = await EventService.delete_event(db, event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Event not found")
    return None
