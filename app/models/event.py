import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Integer, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.utils.database import Base

import enum


class EventStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CANCELLED = "cancelled"
    SOLD_OUT = "sold_out"
    COMPLETED = "completed"


class Event(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    venue = Column(String(255), nullable=True)
    date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(
        SAEnum(EventStatus, name="event_status"),
        nullable=False,
        default=EventStatus.DRAFT,
    )
    max_capacity = Column(Integer, nullable=True)
    image_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    tickets = relationship(
        "Ticket", back_populates="event", cascade="all, delete-orphan"
    )
