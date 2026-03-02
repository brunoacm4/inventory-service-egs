from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.reservation import ReservationCreate, ReservationResponse, ReservationListResponse
from app.schemas.common import ErrorResponse
from app.services.reservation_service import ReservationService
from app.utils.database import get_db
from app.utils.config import settings

router = APIRouter(prefix="/api/v1/reservations", tags=["Reservations"])

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
        "Create a temporary hold on ticket stock. Used by the Composer service "
        "to reserve tickets while the Payment Service processes the transaction. "
        "Reservations expire automatically after the configured TTL (default: 15 min)."
    ),
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse, "description": "Ticket not found"},
        409: {"model": ErrorResponse, "description": "Insufficient stock or ticket unavailable"},
    },
)
async def create_reservation(
    data: ReservationCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    reservation = await ReservationService.create_reservation(db, data)
    if not reservation:
        raise HTTPException(
            status_code=409,
            detail="Unable to create reservation. Ticket may be unavailable, sold out, or requested quantity exceeds limits.",
        )
    return reservation


@router.get(
    "",
    response_model=ReservationListResponse,
    summary="List reservations",
    description="Retrieve a paginated list of reservations. Optionally filter by status or ticket.",
    responses={401: {"model": ErrorResponse}},
)
async def list_reservations(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: pending, confirmed, cancelled, expired"),
    ticket_id: Optional[UUID] = Query(None, description="Filter by ticket category ID"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    reservations, total = await ReservationService.list_reservations(
        db, skip=skip, limit=limit, status=status, ticket_id=ticket_id
    )
    return ReservationListResponse(data=reservations, total=total, skip=skip, limit=limit)


@router.get(
    "/{reservation_id}",
    response_model=ReservationResponse,
    summary="Get reservation details",
    description="Retrieve detailed information about a specific reservation.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_reservation(
    reservation_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    reservation = await ReservationService.get_reservation(db, reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return reservation


@router.post(
    "/{reservation_id}/confirm",
    response_model=ReservationResponse,
    summary="Confirm a reservation",
    description=(
        "Confirm a pending reservation after successful payment. "
        "The stock deduction becomes permanent. Called by the Composer "
        "after receiving payment confirmation from the Payment Service."
    ),
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse, "description": "Reservation is not in pending status"},
    },
)
async def confirm_reservation(
    reservation_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
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
    reservation_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    reservation = await ReservationService.cancel_reservation(db, reservation_id)
    if not reservation:
        raise HTTPException(
            status_code=409,
            detail="Reservation not found or cannot be cancelled (already confirmed).",
        )
    return reservation
