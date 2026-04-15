import uuid
from datetime import datetime, timezone
from typing import Optional, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket import Ticket, TicketStatus
from app.models.event import Event, EventStatus
from app.schemas.ticket import TicketBatchCreate


class TicketService:
    """Business logic for ticket operations — simplified, no separate category entity."""

    # ── Batch create ──────────────────────────────────────────────────────────

    @staticmethod
    async def batch_create(
        db: AsyncSession,
        event_id: uuid.UUID,
        data: TicketBatchCreate,
    ) -> List[Ticket]:
        """Create N tickets for an event with embedded category info. Returns created tickets."""
        tickets = [
            Ticket(
                id=uuid.uuid4(),
                event_id=event_id,
                category=data.category,
                price=data.price,
                currency=data.currency,
                status=TicketStatus.AVAILABLE,
            )
            for _ in range(data.quantity)
        ]
        db.add_all(tickets)
        await db.commit()
        for ticket in tickets:
            await db.refresh(ticket)
        return tickets

    # ── Read ──────────────────────────────────────────────────────────────────

    @staticmethod
    async def get_ticket(db: AsyncSession, ticket_id: uuid.UUID) -> Optional[Ticket]:
        result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_tickets(
        db: AsyncSession,
        event_id: uuid.UUID,
        category: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Ticket], int]:
        filters = [Ticket.event_id == event_id]
        if category:
            filters.append(Ticket.category == category)
        if status:
            filters.append(Ticket.status == TicketStatus(status))

        query = (
            select(Ticket)
            .where(*filters)
            .order_by(Ticket.created_at.asc())
            .offset(skip)
            .limit(limit)
        )
        count_query = select(func.count()).select_from(Ticket).where(*filters)

        result = await db.execute(query)
        tickets = list(result.scalars().all())

        count_result = await db.execute(count_query)
        total = count_result.scalar()

        return tickets, total

    # ── Reserve (atomic) ──────────────────────────────────────────────────────

    @staticmethod
    async def reserve_ticket(db: AsyncSession, ticket_id: uuid.UUID) -> Optional[Ticket]:
        """Reserve one specific ticket only when event is published and ticket is AVAILABLE."""
        result = await db.execute(
            select(Ticket)
            .join(Event, Event.id == Ticket.event_id)
            .where(
                Ticket.id == ticket_id,
                Ticket.status == TicketStatus.AVAILABLE,
                Event.status == EventStatus.PUBLISHED,
            )
            .with_for_update()
        )
        ticket = result.scalar_one_or_none()
        if not ticket:
            await db.rollback()
            return None

        now = datetime.now(tz=timezone.utc)
        ticket.status = TicketStatus.RESERVED
        ticket.reserved_at = now
        ticket.updated_at = now

        await db.commit()
        await db.refresh(ticket)
        return ticket

    @staticmethod
    async def reserve_tickets(
        db: AsyncSession,
        event_id: uuid.UUID,
        quantity: int,
        customer_email: Optional[str] = None,
        external_reference: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Optional[List[Ticket]]:
        """
        Atomically reserve N available tickets for an event.
        Uses SELECT ... FOR UPDATE to prevent race conditions.
        Returns the reserved tickets, or None if insufficient stock.
        """
        filters = [
            Ticket.event_id == event_id,
            Ticket.status == TicketStatus.AVAILABLE,
            Event.status == EventStatus.PUBLISHED,
        ]
        if category:
            filters.append(Ticket.category == category)

        pick_query = (
            select(Ticket)
            .join(Event, Event.id == Ticket.event_id)
            .where(*filters)
            .order_by(Ticket.created_at.asc())
            .limit(quantity)
            .with_for_update()
        )
        result = await db.execute(pick_query)
        tickets = list(result.scalars().all())

        if len(tickets) < quantity:
            await db.rollback()
            return None

        now = datetime.now(tz=timezone.utc)
        for ticket in tickets:
            ticket.status = TicketStatus.RESERVED
            ticket.customer_email = customer_email
            ticket.external_reference = external_reference
            ticket.reserved_at = now
            ticket.updated_at = now

        await db.commit()
        for ticket in tickets:
            await db.refresh(ticket)
        return tickets

    # ── Lifecycle transitions ─────────────────────────────────────────────────

    @staticmethod
    async def sell_ticket(db: AsyncSession, ticket_id: uuid.UUID) -> Optional[Ticket]:
        """Mark a RESERVED ticket as SOLD (payment confirmed)."""
        ticket = await TicketService.get_ticket(db, ticket_id)
        if not ticket or ticket.status != TicketStatus.RESERVED:
            return None

        now = datetime.now(tz=timezone.utc)
        ticket.status = TicketStatus.SOLD
        ticket.sold_at = now
        ticket.updated_at = now

        await db.commit()
        await db.refresh(ticket)
        return ticket

    @staticmethod
    async def use_ticket(db: AsyncSession, ticket_id: uuid.UUID) -> Optional[Ticket]:
        """Mark a SOLD ticket as USED (validated at gate)."""
        ticket = await TicketService.get_ticket(db, ticket_id)
        if not ticket or ticket.status != TicketStatus.SOLD:
            return None

        now = datetime.now(tz=timezone.utc)
        ticket.status = TicketStatus.USED
        ticket.used_at = now
        ticket.updated_at = now

        await db.commit()
        await db.refresh(ticket)
        return ticket

    @staticmethod
    async def cancel_ticket(db: AsyncSession, ticket_id: uuid.UUID) -> Optional[Ticket]:
        """Cancel a RESERVED ticket — release it back to AVAILABLE."""
        ticket = await TicketService.get_ticket(db, ticket_id)
        if not ticket or ticket.status != TicketStatus.RESERVED:
            return None

        now = datetime.now(tz=timezone.utc)
        ticket.status = TicketStatus.AVAILABLE
        ticket.customer_email = None
        ticket.external_reference = None
        ticket.reserved_at = None
        ticket.updated_at = now

        await db.commit()
        await db.refresh(ticket)
        return ticket
