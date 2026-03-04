import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.utils.database import Base

import enum


class ReservationStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Reservation(Base):
    """
    Temporary hold on ticket category stock while payment is being processed.
    Expires automatically after a configurable TTL (default 15 min).
    Upon confirmation, IssuedTickets are minted via lazy minting.
    """

    __tablename__ = "reservations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ticket_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity = Column(Integer, nullable=False)
    status = Column(
        SAEnum(ReservationStatus, name="reservation_status"),
        nullable=False,
        default=ReservationStatus.PENDING,
    )
    customer_email = Column(String(255), nullable=True)
    external_reference = Column(String(255), nullable=True)  # e.g. payment_id from Payment Service
    expires_at = Column(DateTime(timezone=True), nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    ticket_category = relationship("TicketCategory", back_populates="reservations")
    issued_tickets = relationship(
        "IssuedTicket", back_populates="reservation", cascade="all, delete-orphan"
    )
