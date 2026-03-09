import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.utils.database import Base

import enum


class TicketStatus(str, enum.Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class Ticket(Base):
    """
    Represents a single ticket for an event.
    Tickets are batch-created up front and transition through states:
      available → reserved → confirmed (permanent sale)
      reserved → cancelled (releases back to available pool)
    Reserved tickets expire automatically after the configured TTL.
    """

    __tablename__ = "tickets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticket_category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ticket_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(
        SAEnum(TicketStatus, name="ticket_status"),
        nullable=False,
        default=TicketStatus.AVAILABLE,
    )
    external_reference = Column(String(255), nullable=True, index=True)
    reserved_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    event = relationship("Event", back_populates="tickets")
    ticket_category = relationship("TicketCategory", back_populates="tickets")
