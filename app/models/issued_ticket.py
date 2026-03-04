import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.utils.database import Base

import enum


class IssuedTicketStatus(str, enum.Enum):
    VALID = "valid"
    USED = "used"
    CANCELLED = "cancelled"


class IssuedTicket(Base):
    """
    Represents a single physical/digital ticket issued after payment confirmation.
    Created via lazy minting: only generated when a reservation is confirmed,
    avoiding unnecessary DB writes during the high-traffic reservation phase.
    """

    __tablename__ = "issued_tickets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ticket_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reservation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reservations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(
        SAEnum(IssuedTicketStatus, name="issued_ticket_status"),
        nullable=False,
        default=IssuedTicketStatus.VALID,
    )
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    ticket_category = relationship("TicketCategory", back_populates="issued_tickets")
    reservation = relationship("Reservation", back_populates="issued_tickets")
