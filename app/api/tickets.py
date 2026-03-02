from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.ticket import (
    TicketCreate,
    TicketUpdate,
    TicketResponse,
    TicketListResponse,
    TicketAvailability,
)
from app.schemas.common import ErrorResponse
from app.services.ticket_service import TicketService
from app.services.event_service import EventService
from app.utils.database import get_db
from app.utils.config import settings

router = APIRouter(prefix="/api/v1", tags=["Tickets"])

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    if not api_key or api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key


@router.post(
    "/events/{event_id}/tickets",
    response_model=TicketResponse,
    status_code=201,
    summary="Create a ticket category",
    description="Create a new ticket category (e.g., VIP, General Admission) for a specific event.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def create_ticket(
    event_id: UUID,
    data: TicketCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    # Verify event exists
    event = await EventService.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    ticket = await TicketService.create_ticket(db, event_id, data)
    return ticket


@router.get(
    "/events/{event_id}/tickets",
    response_model=TicketListResponse,
    summary="List ticket categories for an event",
    description="Retrieve all ticket categories available for a specific event.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def list_tickets_by_event(
    event_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    event = await EventService.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    tickets, total = await TicketService.list_tickets_by_event(db, event_id, skip, limit)
    return TicketListResponse(data=tickets, total=total, skip=skip, limit=limit)


@router.get(
    "/tickets/{ticket_id}",
    response_model=TicketResponse,
    summary="Get ticket category details",
    description="Retrieve detailed information about a specific ticket category.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_ticket(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    ticket = await TicketService.get_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket category not found")
    return ticket


@router.put(
    "/tickets/{ticket_id}",
    response_model=TicketResponse,
    summary="Update a ticket category",
    description="Update one or more fields of an existing ticket category.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def update_ticket(
    ticket_id: UUID,
    data: TicketUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    ticket = await TicketService.update_ticket(db, ticket_id, data)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket category not found")
    return ticket


@router.delete(
    "/tickets/{ticket_id}",
    status_code=204,
    summary="Delete a ticket category",
    description="Delete a ticket category and all associated reservations.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def delete_ticket(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    deleted = await TicketService.delete_ticket(db, ticket_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Ticket category not found")
    return None


@router.get(
    "/tickets/{ticket_id}/availability",
    response_model=TicketAvailability,
    summary="Check ticket availability",
    description="Check real-time availability and sale status for a specific ticket category. Used by the Composer to verify stock before initiating payment.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def check_ticket_availability(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    availability = await TicketService.check_availability(db, ticket_id)
    if not availability:
        raise HTTPException(status_code=404, detail="Ticket category not found")
    return availability
