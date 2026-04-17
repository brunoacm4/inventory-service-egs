from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kpi_event import KPIEvent
from app.models.ticket import Ticket, TicketStatus
from app.schemas.kpi import KPIEventItem, KPICategorySnapshot, KPIEventsResponse, KPISnapshotResponse, KPITicketStatusCounts
from app.utils.config import settings


class KPIService:
    @staticmethod
    async def record_event(
        db: AsyncSession,
        *,
        event_type: str,
        event_id: Optional[UUID] = None,
        ticket_id: Optional[UUID] = None,
        category: Optional[str] = None,
        price: Optional[Any] = None,
        currency: Optional[str] = None,
        status_before: Optional[str] = None,
        status_after: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not settings.enable_kpi_event_logging:
            return

        row = KPIEvent(
            event_type=event_type,
            event_id=event_id,
            ticket_id=ticket_id,
            category=category,
            price=price,
            currency=currency,
            status_before=status_before,
            status_after=status_after,
            metadata_json=metadata,
        )
        db.add(row)

    @staticmethod
    async def build_snapshot(
        db: AsyncSession,
        *,
        event_id: Optional[UUID] = None,
    ) -> KPISnapshotResponse:
        generated_at = datetime.now(tz=timezone.utc)

        if not settings.enable_kpi_endpoints:
            return KPISnapshotResponse(
                enabled=False,
                generated_at=generated_at,
                event_id=event_id,
                counts=KPITicketStatusCounts(),
                by_category=[],
            )

        filters = []
        if event_id is not None:
            filters.append(Ticket.event_id == event_id)

        grouped = await db.execute(
            select(Ticket.category, Ticket.status, func.count(Ticket.id))
            .where(*filters)
            .group_by(Ticket.category, Ticket.status)
        )
        rows = grouped.all()

        per_category: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for category, status, count in rows:
            status_key = status.value if isinstance(status, TicketStatus) else str(status)
            per_category[category][status_key] = int(count)

        by_category: List[KPICategorySnapshot] = []
        total_counts = KPITicketStatusCounts()

        for category, counts in sorted(per_category.items(), key=lambda item: item[0]):
            category_counts = KPITicketStatusCounts(
                total=counts.get("available", 0) + counts.get("reserved", 0) + counts.get("sold", 0) + counts.get("used", 0),
                available=counts.get("available", 0),
                reserved=counts.get("reserved", 0),
                sold=counts.get("sold", 0),
                used=counts.get("used", 0),
            )
            by_category.append(KPICategorySnapshot(category=category, counts=category_counts))
            total_counts.total += category_counts.total
            total_counts.available += category_counts.available
            total_counts.reserved += category_counts.reserved
            total_counts.sold += category_counts.sold
            total_counts.used += category_counts.used

        return KPISnapshotResponse(
            enabled=True,
            generated_at=generated_at,
            event_id=event_id,
            counts=total_counts,
            by_category=by_category,
        )

    @staticmethod
    async def list_events(
        db: AsyncSession,
        *,
        cursor: Optional[datetime] = None,
        event_id: Optional[UUID] = None,
        limit: int = 500,
    ) -> KPIEventsResponse:
        if not settings.enable_kpi_endpoints:
            return KPIEventsResponse(enabled=False, items=[], next_cursor=cursor)

        query = select(KPIEvent)
        if cursor is not None:
            query = query.where(KPIEvent.occurred_at > cursor)
        if event_id is not None:
            query = query.where(KPIEvent.event_id == event_id)

        query = query.order_by(KPIEvent.occurred_at.asc(), KPIEvent.id.asc()).limit(limit)
        result = await db.execute(query)
        rows = list(result.scalars().all())

        items = [
            KPIEventItem(
                id=row.id,
                occurred_at=row.occurred_at,
                event_type=row.event_type,
                event_id=row.event_id,
                ticket_id=row.ticket_id,
                category=row.category,
                price=row.price,
                currency=row.currency,
                status_before=row.status_before,
                status_after=row.status_after,
                metadata=row.metadata_json,
            )
            for row in rows
        ]
        next_cursor = items[-1].occurred_at if items else cursor

        return KPIEventsResponse(enabled=True, items=items, next_cursor=next_cursor)
