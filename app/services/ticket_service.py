import uuid
from datetime import datetime
from typing import Optional, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket import Ticket, TicketStatus
from app.schemas.ticket import TicketCreate, TicketUpdate, TicketAvailability


class TicketService:
    """Business logic for ticket category management."""

    @staticmethod
    async def create_ticket(
        db: AsyncSession, event_id: uuid.UUID, data: TicketCreate
    ) -> Ticket:
        ticket = Ticket(
            id=uuid.uuid4(),
            event_id=event_id,
            name=data.name,
            description=data.description,
            price=data.price,
            currency=data.currency,
            total_quantity=data.total_quantity,
            available_quantity=data.total_quantity,  # starts fully available
            max_per_order=data.max_per_order,
            sale_start=data.sale_start,
            sale_end=data.sale_end,
            status=TicketStatus.AVAILABLE,
        )
        db.add(ticket)
        await db.commit()
        await db.refresh(ticket)
        return ticket

    @staticmethod
    async def get_ticket(db: AsyncSession, ticket_id: uuid.UUID) -> Optional[Ticket]:
        result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_tickets_by_event(
        db: AsyncSession,
        event_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Ticket], int]:
        query = (
            select(Ticket)
            .where(Ticket.event_id == event_id)
            .order_by(Ticket.price.asc())
            .offset(skip)
            .limit(limit)
        )
        count_query = (
            select(func.count())
            .select_from(Ticket)
            .where(Ticket.event_id == event_id)
        )

        result = await db.execute(query)
        tickets = list(result.scalars().all())

        count_result = await db.execute(count_query)
        total = count_result.scalar()

        return tickets, total

    @staticmethod
    async def update_ticket(
        db: AsyncSession, ticket_id: uuid.UUID, data: TicketUpdate
    ) -> Optional[Ticket]:
        ticket = await TicketService.get_ticket(db, ticket_id)
        if not ticket:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(ticket, field, value)

        ticket.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(ticket)
        return ticket

    @staticmethod
    async def delete_ticket(db: AsyncSession, ticket_id: uuid.UUID) -> bool:
        ticket = await TicketService.get_ticket(db, ticket_id)
        if not ticket:
            return False

        await db.delete(ticket)
        await db.commit()
        return True

    @staticmethod
    async def check_availability(
        db: AsyncSession, ticket_id: uuid.UUID
    ) -> Optional[TicketAvailability]:
        ticket = await TicketService.get_ticket(db, ticket_id)
        if not ticket:
            return None

        now = datetime.utcnow()
        is_on_sale = (
            ticket.status == TicketStatus.AVAILABLE
            and ticket.available_quantity > 0
            and (ticket.sale_start is None or ticket.sale_start <= now)
            and (ticket.sale_end is None or ticket.sale_end >= now)
        )

        return TicketAvailability(
            ticket_id=ticket.id,
            event_id=ticket.event_id,
            name=ticket.name,
            available_quantity=ticket.available_quantity,
            total_quantity=ticket.total_quantity,
            price=ticket.price,
            currency=ticket.currency,
            status=ticket.status.value,
            is_on_sale=is_on_sale,
        )
