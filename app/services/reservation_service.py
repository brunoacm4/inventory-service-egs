import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import Reservation, ReservationStatus
from app.models.ticket import Ticket, TicketStatus
from app.schemas.reservation import ReservationCreate
from app.utils.config import settings


class ReservationService:
    """
    Business logic for reservation management.
    Handles temporary stock holds, confirmations, and cancellations.
    """

    @staticmethod
    async def create_reservation(
        db: AsyncSession, data: ReservationCreate
    ) -> Optional[Reservation]:
        """
        Create a temporary reservation, decrementing available stock.
        Returns None if insufficient stock.
        """
        # Get the ticket and lock the row for update
        result = await db.execute(
            select(Ticket).where(Ticket.id == data.ticket_id).with_for_update()
        )
        ticket = result.scalar_one_or_none()

        if not ticket:
            return None

        # Validate stock
        if ticket.available_quantity < data.quantity:
            return None

        if ticket.status != TicketStatus.AVAILABLE:
            return None

        # Check max per order
        if ticket.max_per_order and data.quantity > ticket.max_per_order:
            return None

        # Decrement available stock
        ticket.available_quantity -= data.quantity
        if ticket.available_quantity == 0:
            ticket.status = TicketStatus.SOLD_OUT

        # Create reservation with TTL
        ttl_minutes = settings.reservation_ttl_minutes
        reservation = Reservation(
            id=uuid.uuid4(),
            ticket_id=data.ticket_id,
            quantity=data.quantity,
            status=ReservationStatus.PENDING,
            customer_email=data.customer_email,
            external_reference=data.external_reference,
            expires_at=datetime.utcnow() + timedelta(minutes=ttl_minutes),
        )
        db.add(reservation)
        await db.commit()
        await db.refresh(reservation)
        return reservation

    @staticmethod
    async def get_reservation(
        db: AsyncSession, reservation_id: uuid.UUID
    ) -> Optional[Reservation]:
        result = await db.execute(
            select(Reservation).where(Reservation.id == reservation_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_reservations(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
        ticket_id: Optional[uuid.UUID] = None,
    ) -> Tuple[List[Reservation], int]:
        query = select(Reservation)
        count_query = select(func.count()).select_from(Reservation)

        if status:
            query = query.where(Reservation.status == status)
            count_query = count_query.where(Reservation.status == status)

        if ticket_id:
            query = query.where(Reservation.ticket_id == ticket_id)
            count_query = count_query.where(Reservation.ticket_id == ticket_id)

        query = query.order_by(Reservation.created_at.desc()).offset(skip).limit(limit)

        result = await db.execute(query)
        reservations = list(result.scalars().all())

        count_result = await db.execute(count_query)
        total = count_result.scalar()

        return reservations, total

    @staticmethod
    async def confirm_reservation(
        db: AsyncSession, reservation_id: uuid.UUID
    ) -> Optional[Reservation]:
        """
        Confirm a pending reservation (called after successful payment).
        Stock remains decremented — the sale is final.
        """
        reservation = await ReservationService.get_reservation(db, reservation_id)
        if not reservation:
            return None

        if reservation.status != ReservationStatus.PENDING:
            return None

        reservation.status = ReservationStatus.CONFIRMED
        reservation.confirmed_at = datetime.utcnow()
        reservation.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(reservation)
        return reservation

    @staticmethod
    async def cancel_reservation(
        db: AsyncSession, reservation_id: uuid.UUID
    ) -> Optional[Reservation]:
        """
        Cancel a reservation and release stock back to the pool.
        """
        reservation = await ReservationService.get_reservation(db, reservation_id)
        if not reservation:
            return None

        if reservation.status not in (ReservationStatus.PENDING, ReservationStatus.EXPIRED):
            return None

        # Release stock back
        result = await db.execute(
            select(Ticket).where(Ticket.id == reservation.ticket_id).with_for_update()
        )
        ticket = result.scalar_one_or_none()
        if ticket:
            ticket.available_quantity += reservation.quantity
            if ticket.available_quantity > 0 and ticket.status == TicketStatus.SOLD_OUT:
                ticket.status = TicketStatus.AVAILABLE

        reservation.status = ReservationStatus.CANCELLED
        reservation.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(reservation)
        return reservation
