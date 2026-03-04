from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.ticket_category import (
    TicketCategoryCreate,
    TicketCategoryUpdate,
    TicketCategoryResponse,
    TicketCategoryListResponse,
    TicketCategoryAvailability,
)
from app.schemas.common import ErrorResponse
from app.services.ticket_category_service import TicketCategoryService
from app.services.event_service import EventService
from app.utils.database import get_db
from app.utils.config import settings

router = APIRouter(prefix="/api/v1", tags=["Ticket Categories"])

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    if not api_key or api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key


@router.post(
    "/events/{event_id}/ticket-categories",
    response_model=TicketCategoryResponse,
    status_code=201,
    summary="Create a ticket category",
    description=(
        "Create a new ticket category batch (e.g., 5000 VIP seats) for a specific event. "
        "Individual tickets are not created here — they are minted lazily upon reservation confirmation."
    ),
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def create_ticket_category(
    event_id: UUID,
    data: TicketCategoryCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    event = await EventService.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    category = await TicketCategoryService.create_ticket_category(db, event_id, data)
    return category


@router.get(
    "/events/{event_id}/ticket-categories",
    response_model=TicketCategoryListResponse,
    summary="List ticket categories for an event",
    description="Retrieve all ticket category batches available for a specific event.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def list_ticket_categories(
    event_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    event = await EventService.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    categories, total = await TicketCategoryService.list_by_event(db, event_id, skip, limit)
    return TicketCategoryListResponse(data=categories, total=total, skip=skip, limit=limit)


@router.get(
    "/ticket-categories/{ticket_category_id}",
    response_model=TicketCategoryResponse,
    summary="Get ticket category details",
    description="Retrieve detailed information about a specific ticket category batch.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_ticket_category(
    ticket_category_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    category = await TicketCategoryService.get_ticket_category(db, ticket_category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Ticket category not found")
    return category


@router.put(
    "/ticket-categories/{ticket_category_id}",
    response_model=TicketCategoryResponse,
    summary="Update a ticket category",
    description="Update one or more fields of an existing ticket category batch.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def update_ticket_category(
    ticket_category_id: UUID,
    data: TicketCategoryUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    category = await TicketCategoryService.update_ticket_category(db, ticket_category_id, data)
    if not category:
        raise HTTPException(status_code=404, detail="Ticket category not found")
    return category


@router.delete(
    "/ticket-categories/{ticket_category_id}",
    status_code=204,
    summary="Delete a ticket category",
    description="Delete a ticket category batch and all associated reservations and issued tickets.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def delete_ticket_category(
    ticket_category_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    deleted = await TicketCategoryService.delete_ticket_category(db, ticket_category_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Ticket category not found")
    return None


@router.get(
    "/ticket-categories/{ticket_category_id}/availability",
    response_model=TicketCategoryAvailability,
    summary="Check ticket category availability",
    description=(
        "Check real-time availability and sale status for a specific ticket category. "
        "Used by the Composer to verify stock before initiating a reservation."
    ),
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def check_availability(
    ticket_category_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    availability = await TicketCategoryService.check_availability(db, ticket_category_id)
    if not availability:
        raise HTTPException(status_code=404, detail="Ticket category not found")
    return availability
