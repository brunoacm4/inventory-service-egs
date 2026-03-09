from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.ticket import (
    TicketBatchCreate,
    TicketReserveRequest,
    TicketResponse,
    TicketListResponse,
    TicketReserveResponse,
)
from app.schemas.common import ErrorResponse
from app.services.ticket_service import TicketService
from app.services.event_service import EventService
from app.utils.database import get_db
from app.utils.auth import verify_auth

router = APIRouter(prefix="/api/v1", tags=["Tickets"])


# ------------------------------------------------------------------ #
#  Batch-create tickets
# ------------------------------------------------------------------ #

@router.post(
    "/events/{event_id}/tickets",
    response_model=TicketListResponse,
    status_code=201,
    summary="Batch-create tickets",
    description=(
        "Create a batch of tickets for an event. Internally creates a ticket category "
        "(defining the price tier) and N individual ticket records with status 'available'."
    ),
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def batch_create_tickets(
    event_id: UUID,
    data: TicketBatchCreate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_auth),
):
    event = await EventService.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    tickets = await TicketService.batch_create_tickets(db, event_id, data)
    return TicketListResponse(
        data=tickets,
        total=len(tickets),
        skip=0,
        limit=len(tickets),
    )


# ------------------------------------------------------------------ #
#  List tickets for an event
# ------------------------------------------------------------------ #

@router.get(
    "/events/{event_id}/tickets",
    response_model=TicketListResponse,
    summary="List tickets for an event",
    description="Retrieve a paginated list of tickets for a specific event. Optionally filter by status.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def list_tickets(
    event_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(
        None,
        description="Filter by status: available, reserved, confirmed, cancelled",
    ),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_auth),
):
    event = await EventService.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    tickets, total = await TicketService.list_tickets(
        db, event_id, skip=skip, limit=limit, status=status,
    )
    return TicketListResponse(data=tickets, total=total, skip=skip, limit=limit)


# ------------------------------------------------------------------ #
#  Get ticket details
# ------------------------------------------------------------------ #

@router.get(
    "/tickets/{ticket_id}",
    response_model=TicketResponse,
    summary="Get ticket details",
    description="Retrieve detailed information about a specific ticket.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_ticket(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_auth),
):
    ticket = await TicketService.get_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


# ------------------------------------------------------------------ #
#  Reserve tickets
# ------------------------------------------------------------------ #

@router.post(
    "/events/{event_id}/tickets/reserve",
    response_model=TicketReserveResponse,
    summary="Reserve tickets",
    description=(
        "Reserve N available tickets for an event. "
        "The service picks available tickets and transitions them to 'reserved' status. "
        "Uses row-level locking with SKIP LOCKED for concurrency safety."
    ),
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {
            "model": ErrorResponse,
            "description": "Insufficient available tickets or category unavailable",
        },
    },
)
async def reserve_tickets(
    event_id: UUID,
    data: TicketReserveRequest,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_auth),
):
    event = await EventService.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    tickets = await TicketService.reserve_tickets(db, event_id, data)
    if tickets is None:
        raise HTTPException(
            status_code=409,
            detail="Unable to reserve tickets. Insufficient stock or category unavailable.",
        )
    return TicketReserveResponse(reserved_count=len(tickets), tickets=tickets)


# ------------------------------------------------------------------ #
#  Confirm reserved ticket
# ------------------------------------------------------------------ #

@router.post(
    "/tickets/{ticket_id}/confirm",
    response_model=TicketResponse,
    summary="Confirm reserved ticket",
    description=(
        "Confirm a reserved ticket after successful payment. "
        "Transitions the ticket from 'reserved' to 'confirmed'. "
        "Stock remains permanently decremented. "
        "Called by the Composer Service after the Payment Service confirms."
    ),
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse, "description": "Ticket is not in reserved status"},
    },
)
async def confirm_ticket(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_auth),
):
    ticket = await TicketService.confirm_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=409,
            detail="Ticket not found or not in reserved status.",
        )
    return ticket


# ------------------------------------------------------------------ #
#  Cancel reserved ticket
# ------------------------------------------------------------------ #

@router.post(
    "/tickets/{ticket_id}/cancel",
    response_model=TicketResponse,
    summary="Cancel reserved ticket",
    description=(
        "Cancel a reserved ticket, releasing it back to the available pool. "
        "Called when payment fails or the customer abandons checkout."
    ),
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse, "description": "Ticket is not in reserved status"},
    },
)
async def cancel_ticket(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_auth),
):
    ticket = await TicketService.cancel_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=409,
            detail="Ticket not found or not in reserved status.",
        )
    return ticket
