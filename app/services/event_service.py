import uuid
from datetime import datetime
from typing import Optional, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event, EventStatus
from app.schemas.event import EventCreate, EventUpdate


class EventService:
    """Business logic for event management."""

    @staticmethod
    async def create_event(db: AsyncSession, data: EventCreate) -> Event:
        event = Event(
            id=uuid.uuid4(),
            name=data.name,
            description=data.description,
            venue=data.venue,
            date=data.date,
            end_date=data.end_date,
            status=EventStatus.DRAFT,
            max_capacity=data.max_capacity,
            image_url=data.image_url,
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event

    @staticmethod
    async def get_event(db: AsyncSession, event_id: uuid.UUID) -> Optional[Event]:
        result = await db.execute(select(Event).where(Event.id == event_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_events(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> Tuple[List[Event], int]:
        query = select(Event)
        count_query = select(func.count()).select_from(Event)

        if status:
            query = query.where(Event.status == status)
            count_query = count_query.where(Event.status == status)

        query = query.order_by(Event.date.asc()).offset(skip).limit(limit)

        result = await db.execute(query)
        events = list(result.scalars().all())

        count_result = await db.execute(count_query)
        total = count_result.scalar()

        return events, total

    @staticmethod
    async def update_event(
        db: AsyncSession, event_id: uuid.UUID, data: EventUpdate
    ) -> Optional[Event]:
        event = await EventService.get_event(db, event_id)
        if not event:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(event, field, value)

        event.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(event)
        return event

    @staticmethod
    async def delete_event(db: AsyncSession, event_id: uuid.UUID) -> bool:
        event = await EventService.get_event(db, event_id)
        if not event:
            return False

        await db.delete(event)
        await db.commit()
        return True
