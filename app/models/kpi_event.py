import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Numeric, String, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.utils.database import Base


class KPIEventType:
    EVENT_CREATED = "event_created"
    EVENT_UPDATED = "event_updated"
    EVENT_DELETED = "event_deleted"
    TICKETS_BATCH_CREATED = "tickets_batch_created"
    TICKET_RESERVED = "ticket_reserved"
    TICKET_SOLD = "ticket_sold"
    TICKET_USED = "ticket_used"
    TICKET_CANCELLED = "ticket_cancelled"
    TICKET_EXPIRED = "ticket_expired"


class KPIEvent(Base):
    """Immutable domain events emitted by Inventory for composer-side KPI processing."""

    __tablename__ = "kpi_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    occurred_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
        nullable=False,
        index=True,
    )
    event_type = Column(String(64), nullable=False, index=True)

    event_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    ticket_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    category = Column(String(100), nullable=True)
    price = Column(Numeric(10, 2), nullable=True)
    currency = Column(String(3), nullable=True)

    status_before = Column(String(32), nullable=True)
    status_after = Column(String(32), nullable=True)

    metadata_json = Column(JSON, nullable=True)
