from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class IssuedTicketResponse(BaseModel):
    """
    Response object for an issued ticket.
    Issued tickets are created via lazy minting only after a reservation is confirmed.
    Each one represents a unique, individually identifiable ticket.
    """

    id: UUID
    ticket_category_id: UUID
    reservation_id: UUID
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
