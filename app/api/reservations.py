from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.reservation import ReservationCreate, ReservationResponse, ReservationListResponse
from app.schemas.common import ErrorResponse
from app.services.reservation_service import ReservationService
from app.services.ticket_category_service import TicketCategoryService
from app.utils.database import get_db
from app.utils.config import settings

router = APIRouter(
    prefix="/api/v1/ticket-categories/{ticket_category_id}/reservations",
    tags=["Reservations"],
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    if not api_key or api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key


@router.post(
    "",
    response_model=ReservationResponse,
    status_code=201,
    summary="Create a reservation",
    description=(
        "Create a temporary hold on ticket category stock. Used by the Composer service "
        "to reserve tickets while the Payment Service processes the transaction. "
        "Reservations expire automatically after the configured TTL (default: 15 min). "
        "Stock is decremented atomically using row-level locking."
    ),
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse, "description": "Ticket category not found"},
        409: {"model": ErrorResponse, "description": "Insufficient stock or category unavailable"},
    },
)
async def create_reservation(
    ticket_category_id: UUID,
    data: ReservationCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    # Verify ticket category exists
    category = await TicketCategoryService.get_ticket_category(db, ticket_category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Ticket category not found")

    reservation = await ReservationService.create_reservation(db, ticket_category_id, data)
    if not reservation:
        raise HTTPException(
            status_code=409,
            detail="Unable to create reservation. Category may be unavailable, sold out, or requested quantity exceeds limits.",
        )
    return reservation


@router.get(
    "",
    response_model=ReservationListResponse,
    summary="List reservations for a ticket category",
    description="Retrieve a paginated list of reservations for a specific ticket category. Optionally filter by status.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def list_reservations(
    ticket_category_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: pending, confirmed, cancelled, expired"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    category = await TicketCategoryService.get_ticket_category(db, ticket_category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Ticket category not found")

    reservations, total = await ReservationService.list_reservations(
        db, ticket_category_id=ticket_category_id, skip=skip, limit=limit, status=status
    )
    return ReservationListResponse(data=reservations, total=total, skip=skip, limit=limit)


@router.get(
    "/{reservation_id}",
    response_model=ReservationResponse,
    summary="Get reservation details",
    description="Retrieve detailed information about a specific reservation, including any issued tickets.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_reservation(
    ticket_category_id: UUID,
    reservation_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    reservation = await ReservationService.get_reservation(db, reservation_id)
    if not reservation or reservation.ticket_category_id != ticket_category_id:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return reservation


@router.post(
    "/{reservation_id}/confirm",
    response_model=ReservationResponse,
    summary="Confirm a reservation (lazy minting)",
    description=(
        "Confirm a pending reservation after successful payment. "
        "Triggers lazy minting: individual IssuedTicket records are created "
        "for each unit in the reservation quantity. The response includes "
        "the newly minted ticket IDs. Called by the Composer after payment confirmation."
    ),
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse, "description": "Reservation is not in pending status"},
    },
)
async def confirm_reservation(
    ticket_category_id: UUID,
    reservation_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    # Verify reservation belongs to this ticket category
    existing = await ReservationService.get_reservation(db, reservation_id)
    if not existing or existing.ticket_category_id != ticket_category_id:
        raise HTTPException(status_code=404, detail="Reservation not found")

    reservation = await ReservationService.confirm_reservation(db, reservation_id)
    if not reservation:
        raise HTTPException(
            status_code=409,
            detail="Reservation not found or not in pending status.",
        )
    return reservation


@router.post(
    "/{reservation_id}/cancel",
    response_model=ReservationResponse,
    summary="Cancel a reservation",
    description=(
        "Cancel a reservation and release the held stock back to the pool. "
        "Can be called when payment fails or the customer abandons checkout."
    ),
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse, "description": "Reservation cannot be cancelled"},
    },
)
async def cancel_reservation(
    ticket_category_id: UUID,
    reservation_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    existing = await ReservationService.get_reservation(db, reservation_id)
    if not existing or existing.ticket_category_id != ticket_category_id:
        raise HTTPException(status_code=404, detail="Reservation not found")

    reservation = await ReservationService.cancel_reservation(db, reservation_id)
    if not reservation:
        raise HTTPException(
            status_code=409,
            detail="Reservation not found or cannot be cancelled (already confirmed).",
        )
    return reservation
