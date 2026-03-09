import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Column, String, Text, DateTime, Integer, Numeric, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.utils.database import Base

import enum


class TicketCategoryStatus(str, enum.Enum):
    AVAILABLE = "available"
    SOLD_OUT = "sold_out"
    INACTIVE = "inactive"


class TicketCategory(Base):
    """
    Represents a ticket batch/category for an event (e.g. 'VIP', 'General Admission').
    Each category defines a price tier with its own stock pool and sale window.
    Individual tickets (IssuedTicket) are only minted upon reservation confirmation.
    """

    __tablename__ = "ticket_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="EUR")
    total_quantity = Column(Integer, nullable=False)
    available_quantity = Column(Integer, nullable=False)
    max_per_order = Column(Integer, nullable=True, default=10)
    sale_start = Column(DateTime(timezone=True), nullable=True)
    sale_end = Column(DateTime(timezone=True), nullable=True)
    status = Column(
        SAEnum(TicketCategoryStatus, name="ticket_category_status"),
        nullable=False,
        default=TicketCategoryStatus.AVAILABLE,
    )
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    event = relationship("Event", back_populates="ticket_categories")
    tickets = relationship("Ticket", back_populates="ticket_category", cascade="all, delete-orphan")
