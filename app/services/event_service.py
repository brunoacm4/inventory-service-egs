import uuid
from datetime import datetime
from typing import Optional, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event, EventStatus
from app.models.kpi_event import KPIEventType
from app.schemas.event import EventCreate, EventUpdate
from app.services.kpi_service import KPIService


class EventService:
    """Business logic for event management."""

    @staticmethod
    def _status_text(value) -> str:
        return value.value if isinstance(value, EventStatus) else str(value)

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
        await KPIService.record_event(
            db,
            event_type=KPIEventType.EVENT_CREATED,
            event_id=event.id,
            status_after=EventService._status_text(event.status),
            metadata={"name": event.name},
        )
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

        before_status = EventService._status_text(event.status)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "status" and isinstance(value, str):
                value = EventStatus(value)
            setattr(event, field, value)

        event.updated_at = datetime.utcnow()
        await KPIService.record_event(
            db,
            event_type=KPIEventType.EVENT_UPDATED,
            event_id=event.id,
            status_before=before_status,
            status_after=EventService._status_text(event.status),
            metadata={"updated_fields": sorted(list(update_data.keys()))},
        )
        await db.commit()
        await db.refresh(event)
        return event

    @staticmethod
    async def delete_event(db: AsyncSession, event_id: uuid.UUID) -> bool:
        event = await EventService.get_event(db, event_id)
        if not event:
            return False

        await KPIService.record_event(
            db,
            event_type=KPIEventType.EVENT_DELETED,
            event_id=event.id,
            status_before=EventService._status_text(event.status),
        )
        await db.delete(event)
        await db.commit()
        return True
