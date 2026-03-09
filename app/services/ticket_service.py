import uuid
from datetime import datetime
from typing import Optional, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ticket import Ticket, TicketStatus
from app.models.ticket_category import TicketCategory, TicketCategoryStatus
from app.schemas.ticket import (
    TicketBatchCreate,
    TicketReserveRequest,
    TicketResponse,
)
from app.services.ticket_category_service import TicketCategoryService
from app.schemas.ticket_category import TicketCategoryCreate


class TicketService:
    """
    Business logic for ticket management.
    Handles batch creation, stock holds (reserve/cancel), and confirmation.
    Focused on catalog & inventory — does NOT handle payment or entry validation.
    """

    # ------------------------------------------------------------------ #
    #  helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _to_response(ticket: Ticket) -> TicketResponse:
        """Convert a Ticket ORM object to a TicketResponse, denormalizing category fields."""
        category = ticket.ticket_category
        return TicketResponse(
            id=ticket.id,
            event_id=ticket.event_id,
            ticket_category_id=ticket.ticket_category_id,
            status=ticket.status.value if isinstance(ticket.status, TicketStatus) else ticket.status,
            external_reference=ticket.external_reference,
            reserved_at=ticket.reserved_at,
            confirmed_at=ticket.confirmed_at,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            category_name=category.name if category else None,
            price=category.price if category else None,
            currency=category.currency if category else None,
        )

    # ------------------------------------------------------------------ #
    #  batch create
    # ------------------------------------------------------------------ #

    @staticmethod
    async def batch_create_tickets(
        db: AsyncSession,
        event_id: uuid.UUID,
        data: TicketBatchCreate,
    ) -> List[TicketResponse]:
        """
        Create a TicketCategory and N individual Ticket rows (status=available).
        Returns the list of created tickets with denormalized category info.
        """
        # 1. Create the ticket category internally
        cat_data = TicketCategoryCreate(
            name=data.name,
            description=data.description,
            price=data.price,
            currency=data.currency,
            total_quantity=data.total_quantity,
            max_per_order=data.max_per_order,
            sale_start=data.sale_start,
            sale_end=data.sale_end,
        )
        category = await TicketCategoryService.create_ticket_category(db, event_id, cat_data)

        # 2. Bulk-create individual tickets
        tickets: List[Ticket] = []
        for _ in range(data.total_quantity):
            t = Ticket(
                id=uuid.uuid4(),
                event_id=event_id,
                ticket_category_id=category.id,
                status=TicketStatus.AVAILABLE,
            )
            tickets.append(t)

        db.add_all(tickets)
        await db.commit()

        # Refresh category for denormalization
        await db.refresh(category)

        return [
            TicketResponse(
                id=t.id,
                event_id=t.event_id,
                ticket_category_id=t.ticket_category_id,
                status=t.status.value if isinstance(t.status, TicketStatus) else t.status,
                external_reference=None,
                reserved_at=None,
                confirmed_at=None,
                created_at=t.created_at,
                updated_at=t.updated_at,
                category_name=category.name,
                price=category.price,
                currency=category.currency,
            )
            for t in tickets
        ]

    # ------------------------------------------------------------------ #
    #  queries
    # ------------------------------------------------------------------ #

    @staticmethod
    async def list_tickets(
        db: AsyncSession,
        event_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> Tuple[List[TicketResponse], int]:
        query = (
            select(Ticket)
            .where(Ticket.event_id == event_id)
            .options(selectinload(Ticket.ticket_category))
        )
        count_query = (
            select(func.count())
            .select_from(Ticket)
            .where(Ticket.event_id == event_id)
        )

        if status:
            query = query.where(Ticket.status == status)
            count_query = count_query.where(Ticket.status == status)

        query = query.order_by(Ticket.created_at.asc()).offset(skip).limit(limit)

        result = await db.execute(query)
        tickets = list(result.scalars().all())

        count_result = await db.execute(count_query)
        total = count_result.scalar()

        return [TicketService._to_response(t) for t in tickets], total

    @staticmethod
    async def get_ticket(
        db: AsyncSession, ticket_id: uuid.UUID
    ) -> Optional[TicketResponse]:
        result = await db.execute(
            select(Ticket)
            .where(Ticket.id == ticket_id)
            .options(selectinload(Ticket.ticket_category))
        )
        ticket = result.scalar_one_or_none()
        if not ticket:
            return None
        return TicketService._to_response(ticket)

    # ------------------------------------------------------------------ #
    #  reserve
    # ------------------------------------------------------------------ #

    @staticmethod
    async def reserve_tickets(
        db: AsyncSession,
        event_id: uuid.UUID,
        data: TicketReserveRequest,
    ) -> Optional[List[TicketResponse]]:
        """
        Reserve N available tickets for an event.
        If ticket_category_id is provided, reserve only from that category.
        Uses SELECT ... FOR UPDATE SKIP LOCKED for concurrency safety.
        Wrapped in a SAVEPOINT so partial failures roll back atomically.
        Returns None if insufficient stock.
        """
        async with db.begin_nested():
            # Build query to pick available tickets with row-level lock
            ticket_query = (
                select(Ticket)
                .where(Ticket.event_id == event_id)
                .where(Ticket.status == TicketStatus.AVAILABLE)
            )

            if data.ticket_category_id:
                ticket_query = ticket_query.where(
                    Ticket.ticket_category_id == data.ticket_category_id
                )

            ticket_query = (
                ticket_query
                .order_by(Ticket.created_at.asc())
                .limit(data.quantity)
                .with_for_update(skip_locked=True)
            )

            result = await db.execute(ticket_query)
            tickets = list(result.scalars().all())

            if len(tickets) < data.quantity:
                # Not enough tickets — savepoint will roll back
                return None

            # Count tickets per category in this reservation
            per_category: dict = {}
            for t in tickets:
                per_category[t.ticket_category_id] = per_category.get(t.ticket_category_id, 0) + 1

            now = datetime.utcnow()

            for cat_id, count in per_category.items():
                # Lock the category row
                cat_result = await db.execute(
                    select(TicketCategory)
                    .where(TicketCategory.id == cat_id)
                    .with_for_update()
                )
                category = cat_result.scalar_one_or_none()
                if not category:
                    return None

                # Validate max_per_order
                if category.max_per_order and count > category.max_per_order:
                    return None

                # Validate category status
                if category.status != TicketCategoryStatus.AVAILABLE:
                    return None

                # Decrement available stock
                category.available_quantity -= count
                if category.available_quantity <= 0:
                    category.status = TicketCategoryStatus.SOLD_OUT

            # Transition tickets to reserved
            for t in tickets:
                t.status = TicketStatus.RESERVED
                t.external_reference = data.external_reference
                t.reserved_at = now
                t.updated_at = now

        # Savepoint committed — now commit the outer transaction
        await db.commit()

        # Re-fetch with category eagerly loaded for response
        ticket_ids = [t.id for t in tickets]
        refetch = await db.execute(
            select(Ticket)
            .where(Ticket.id.in_(ticket_ids))
            .options(selectinload(Ticket.ticket_category))
        )
        reserved = list(refetch.scalars().all())

        return [TicketService._to_response(t) for t in reserved]

    # ------------------------------------------------------------------ #
    #  confirm
    # ------------------------------------------------------------------ #

    @staticmethod
    async def confirm_ticket(
        db: AsyncSession, ticket_id: uuid.UUID
    ) -> Optional[TicketResponse]:
        """
        Confirm a reserved ticket after successful payment.
        Transitions reserved → confirmed. Stock remains permanently decremented.
        Called by the Composer Service after the Payment Service confirms.
        Returns None if ticket not found or not in reserved status.
        """
        result = await db.execute(
            select(Ticket)
            .where(Ticket.id == ticket_id)
            .options(selectinload(Ticket.ticket_category))
            .with_for_update()
        )
        ticket = result.scalar_one_or_none()
        if not ticket:
            return None
        if ticket.status != TicketStatus.RESERVED:
            return None

        ticket.status = TicketStatus.CONFIRMED
        ticket.confirmed_at = datetime.utcnow()
        ticket.updated_at = datetime.utcnow()

        await db.commit()

        # Re-fetch with category loaded
        result = await db.execute(
            select(Ticket)
            .where(Ticket.id == ticket_id)
            .options(selectinload(Ticket.ticket_category))
        )
        ticket = result.scalar_one_or_none()
        return TicketService._to_response(ticket)

    # ------------------------------------------------------------------ #
    #  cancel
    # ------------------------------------------------------------------ #

    @staticmethod
    async def cancel_ticket(
        db: AsyncSession, ticket_id: uuid.UUID
    ) -> Optional[TicketResponse]:
        """
        Cancel a reserved ticket: transition back to available,
        clear customer data, release stock on the category.
        Returns None if ticket not found or not in reserved status.
        """
        result = await db.execute(
            select(Ticket)
            .where(Ticket.id == ticket_id)
            .with_for_update()
        )
        ticket = result.scalar_one_or_none()
        if not ticket:
            return None
        if ticket.status != TicketStatus.RESERVED:
            return None

        # Release stock back to category
        cat_result = await db.execute(
            select(TicketCategory)
            .where(TicketCategory.id == ticket.ticket_category_id)
            .with_for_update()
        )
        category = cat_result.scalar_one_or_none()
        if category:
            category.available_quantity += 1
            if category.available_quantity > 0 and category.status == TicketCategoryStatus.SOLD_OUT:
                category.status = TicketCategoryStatus.AVAILABLE

        # Transition ticket back to available
        ticket.status = TicketStatus.AVAILABLE
        ticket.external_reference = None
        ticket.reserved_at = None
        ticket.updated_at = datetime.utcnow()

        await db.commit()

        # Re-fetch with category
        result = await db.execute(
            select(Ticket)
            .where(Ticket.id == ticket_id)
            .options(selectinload(Ticket.ticket_category))
        )
        ticket = result.scalar_one_or_none()
        return TicketService._to_response(ticket)
