from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.ticket import (
    TicketResponse,
)
from app.schemas.common import ErrorResponse
from app.services.ticket_service import TicketService
from app.utils.database import get_db
from app.utils.auth import verify_auth

router = APIRouter(prefix="/api/v1/tickets", tags=["Tickets"])


# ------------------------------------------------------------------ #
#  Get ticket details
# ------------------------------------------------------------------ #

@router.get(
    "/{ticket_id}",
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
#  Reserve ticket
# ------------------------------------------------------------------ #

@router.put(
    "/{ticket_id}/reserve",
    response_model=TicketResponse,
    summary="Reserve ticket",
    description=(
        "Reserve a specific ticket. "
        "Transitions the ticket from 'available' to 'reserved'."
    ),
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse, "description": "Ticket is not in available status"},
    },
)
async def reserve_ticket(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_auth),
):
    existing = await TicketService.get_ticket(db, ticket_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket = await TicketService.reserve_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=409,
            detail="Ticket is not in available status.",
        )
    return ticket


# ------------------------------------------------------------------ #
#  Sell reserved ticket
# ------------------------------------------------------------------ #

@router.put(
    "/{ticket_id}/sell",
    response_model=TicketResponse,
    summary="Sell reserved ticket",
    description=(
        "Finalize the sale of a reserved ticket. "
        "Transitions the ticket from 'reserved' to 'sold'."
    ),
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse, "description": "Ticket is not in reserved status"},
    },
)
async def sell_ticket(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_auth),
):
    existing = await TicketService.get_ticket(db, ticket_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket = await TicketService.sell_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=409,
            detail="Ticket is not in reserved status.",
        )
    return ticket


# ------------------------------------------------------------------ #
#  Use sold ticket
# ------------------------------------------------------------------ #

@router.put(
    "/{ticket_id}/use",
    response_model=TicketResponse,
    summary="Use sold ticket",
    description=(
        "Validate a sold ticket at entry. "
        "Transitions the ticket from 'sold' to 'used'."
    ),
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse, "description": "Ticket is not in sold status"},
    },
)
async def use_ticket(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_auth),
):
    existing = await TicketService.get_ticket(db, ticket_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket = await TicketService.use_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=409,
            detail="Ticket is not in sold status.",
        )
    return ticket


# ------------------------------------------------------------------ #
#  Cancel reserved ticket
# ------------------------------------------------------------------ #

@router.delete(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Cancel reserved ticket",
    description="Cancel a reserved ticket and release it back to the available pool.",
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
    existing = await TicketService.get_ticket(db, ticket_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket = await TicketService.cancel_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=409,
            detail="Ticket is not in reserved status.",
        )
    return ticket
