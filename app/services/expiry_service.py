"""
Background service that expires reserved tickets past the configured TTL.

Runs as an asyncio task during the app lifespan. Periodically scans for
tickets in 'reserved' status whose reserved_at + TTL has elapsed, and
transitions them back to 'available', releasing stock on the category.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket import Ticket, TicketStatus
from app.models.ticket_category import TicketCategory, TicketCategoryStatus
from app.utils.config import settings
from app.utils.database import async_session

logger = logging.getLogger(__name__)


async def expire_reserved_tickets() -> int:
    """
    Find all reserved tickets past TTL and release them back to available.
    Returns the number of tickets expired.
    """
    ttl = timedelta(minutes=settings.ticket_reservation_ttl_minutes)
    cutoff = datetime.utcnow() - ttl

    async with async_session() as db:
        # Find expired reserved tickets with row-level lock
        result = await db.execute(
            select(Ticket)
            .where(Ticket.status == TicketStatus.RESERVED)
            .where(Ticket.reserved_at <= cutoff)
            .with_for_update(skip_locked=True)
        )
        expired_tickets = list(result.scalars().all())

        if not expired_tickets:
            return 0

        # Group by category to batch-update stock
        per_category: dict = {}
        for ticket in expired_tickets:
            per_category[ticket.ticket_category_id] = (
                per_category.get(ticket.ticket_category_id, 0) + 1
            )

        # Release stock on each affected category
        for cat_id, count in per_category.items():
            cat_result = await db.execute(
                select(TicketCategory)
                .where(TicketCategory.id == cat_id)
                .with_for_update()
            )
            category = cat_result.scalar_one_or_none()
            if category:
                category.available_quantity += count
                if (
                    category.available_quantity > 0
                    and category.status == TicketCategoryStatus.SOLD_OUT
                ):
                    category.status = TicketCategoryStatus.AVAILABLE

        # Transition tickets back to available
        now = datetime.utcnow()
        for ticket in expired_tickets:
            ticket.status = TicketStatus.AVAILABLE
            ticket.external_reference = None
            ticket.reserved_at = None
            ticket.updated_at = now

        await db.commit()

        return len(expired_tickets)


async def reservation_expiry_loop() -> None:
    """
    Infinite loop that runs expire_reserved_tickets at a fixed interval.
    Intended to be launched as a background asyncio task during app lifespan.
    """
    interval = settings.expiry_check_interval_seconds
    logger.info(
        "Reservation expiry loop started (TTL=%d min, interval=%d sec)",
        settings.ticket_reservation_ttl_minutes,
        interval,
    )

    while True:
        try:
            count = await expire_reserved_tickets()
            if count > 0:
                logger.info("Expired %d reserved ticket(s)", count)
        except Exception:
            logger.exception("Error in reservation expiry loop")

        await asyncio.sleep(interval)
