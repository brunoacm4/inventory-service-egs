import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.reservation import Reservation, ReservationStatus
from app.models.ticket_category import TicketCategory, TicketCategoryStatus
from app.models.issued_ticket import IssuedTicket, IssuedTicketStatus
from app.schemas.reservation import ReservationCreate
from app.utils.config import settings


class ReservationService:
    """
    Business logic for reservation management.
    Handles temporary stock holds, confirmations (with lazy minting), and cancellations.
    """

    @staticmethod
    async def create_reservation(
        db: AsyncSession,
        ticket_category_id: uuid.UUID,
        data: ReservationCreate,
    ) -> Optional[Reservation]:
        """
        Create a temporary reservation, decrementing available stock atomically.
        The ticket_category_id comes from the URL path parameter.
        Returns None if insufficient stock or category unavailable.
        """
        # Lock the row for atomic stock update
        result = await db.execute(
            select(TicketCategory)
            .where(TicketCategory.id == ticket_category_id)
            .with_for_update()
        )
        category = result.scalar_one_or_none()

        if not category:
            return None

        # Validate stock
        if category.available_quantity < data.quantity:
            return None

        if category.status != TicketCategoryStatus.AVAILABLE:
            return None

        # Check max per order
        if category.max_per_order and data.quantity > category.max_per_order:
            return None

        # Decrement available stock atomically
        category.available_quantity -= data.quantity
        if category.available_quantity == 0:
            category.status = TicketCategoryStatus.SOLD_OUT

        # Create reservation with TTL
        ttl_minutes = settings.reservation_ttl_minutes
        reservation = Reservation(
            id=uuid.uuid4(),
            ticket_category_id=ticket_category_id,
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
            select(Reservation)
            .where(Reservation.id == reservation_id)
            .options(selectinload(Reservation.issued_tickets))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_reservations(
        db: AsyncSession,
        ticket_category_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> Tuple[List[Reservation], int]:
        query = select(Reservation).where(
            Reservation.ticket_category_id == ticket_category_id
        )
        count_query = select(func.count()).select_from(Reservation).where(
            Reservation.ticket_category_id == ticket_category_id
        )

        if status:
            query = query.where(Reservation.status == status)
            count_query = count_query.where(Reservation.status == status)

        query = (
            query.options(selectinload(Reservation.issued_tickets))
            .order_by(Reservation.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

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
        Confirm a pending reservation after successful payment.
        Performs lazy minting: creates individual IssuedTicket records
        for each unit in the reservation quantity via bulk insert.
        """
        reservation = await ReservationService.get_reservation(db, reservation_id)
        if not reservation:
            return None

        if reservation.status != ReservationStatus.PENDING:
            return None

        # Update reservation status
        reservation.status = ReservationStatus.CONFIRMED
        reservation.confirmed_at = datetime.utcnow()
        reservation.updated_at = datetime.utcnow()

        # Lazy minting: bulk-create individual tickets
        issued = [
            IssuedTicket(
                id=uuid.uuid4(),
                ticket_category_id=reservation.ticket_category_id,
                reservation_id=reservation.id,
                status=IssuedTicketStatus.VALID,
            )
            for _ in range(reservation.quantity)
        ]
        db.add_all(issued)

        await db.commit()

        # Re-fetch with issued_tickets eagerly loaded
        result = await db.execute(
            select(Reservation)
            .where(Reservation.id == reservation_id)
            .options(selectinload(Reservation.issued_tickets))
        )
        return result.scalar_one_or_none()

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

        # Release stock back with row-level lock
        result = await db.execute(
            select(TicketCategory)
            .where(TicketCategory.id == reservation.ticket_category_id)
            .with_for_update()
        )
        category = result.scalar_one_or_none()
        if category:
            category.available_quantity += reservation.quantity
            if category.available_quantity > 0 and category.status == TicketCategoryStatus.SOLD_OUT:
                category.status = TicketCategoryStatus.AVAILABLE

        reservation.status = ReservationStatus.CANCELLED
        reservation.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(reservation)
        return reservation
