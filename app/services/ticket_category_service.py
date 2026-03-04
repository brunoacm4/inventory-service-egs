import uuid
from datetime import datetime, timezone
from typing import Optional, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket_category import TicketCategory, TicketCategoryStatus
from app.schemas.ticket_category import TicketCategoryCreate, TicketCategoryUpdate, TicketCategoryAvailability


class TicketCategoryService:
    """Business logic for ticket category (batch) management."""

    @staticmethod
    async def create_ticket_category(
        db: AsyncSession, event_id: uuid.UUID, data: TicketCategoryCreate
    ) -> TicketCategory:
        category = TicketCategory(
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
            status=TicketCategoryStatus.AVAILABLE,
        )
        db.add(category)
        await db.commit()
        await db.refresh(category)
        return category

    @staticmethod
    async def get_ticket_category(db: AsyncSession, category_id: uuid.UUID) -> Optional[TicketCategory]:
        result = await db.execute(select(TicketCategory).where(TicketCategory.id == category_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_event(
        db: AsyncSession,
        event_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[TicketCategory], int]:
        query = (
            select(TicketCategory)
            .where(TicketCategory.event_id == event_id)
            .order_by(TicketCategory.price.asc())
            .offset(skip)
            .limit(limit)
        )
        count_query = (
            select(func.count())
            .select_from(TicketCategory)
            .where(TicketCategory.event_id == event_id)
        )

        result = await db.execute(query)
        categories = list(result.scalars().all())

        count_result = await db.execute(count_query)
        total = count_result.scalar()

        return categories, total

    @staticmethod
    async def update_ticket_category(
        db: AsyncSession, category_id: uuid.UUID, data: TicketCategoryUpdate
    ) -> Optional[TicketCategory]:
        category = await TicketCategoryService.get_ticket_category(db, category_id)
        if not category:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(category, field, value)

        category.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(category)
        return category

    @staticmethod
    async def delete_ticket_category(db: AsyncSession, category_id: uuid.UUID) -> bool:
        category = await TicketCategoryService.get_ticket_category(db, category_id)
        if not category:
            return False

        await db.delete(category)
        await db.commit()
        return True

    @staticmethod
    async def check_availability(
        db: AsyncSession, category_id: uuid.UUID
    ) -> Optional[TicketCategoryAvailability]:
        category = await TicketCategoryService.get_ticket_category(db, category_id)
        if not category:
            return None

        now = datetime.now(tz=timezone.utc)
        is_on_sale = (
            category.status == TicketCategoryStatus.AVAILABLE
            and category.available_quantity > 0
            and (category.sale_start is None or category.sale_start <= now)
            and (category.sale_end is None or category.sale_end >= now)
        )

        return TicketCategoryAvailability(
            ticket_category_id=category.id,
            event_id=category.event_id,
            name=category.name,
            available_quantity=category.available_quantity,
            total_quantity=category.total_quantity,
            price=category.price,
            currency=category.currency,
            status=category.status.value,
            is_on_sale=is_on_sale,
        )
