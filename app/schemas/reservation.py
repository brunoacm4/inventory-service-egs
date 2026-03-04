from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.issued_ticket import IssuedTicketResponse


class ReservationCreate(BaseModel):
    """
    Request body to create a reservation (temporary hold).
    The Composer calls this to reserve tickets while the Payment Service
    processes the transaction. The ticket_category_id is extracted from the URL path.
    """

    quantity: int = Field(..., ge=1, description="Number of tickets to reserve")
    customer_email: Optional[str] = Field(None, description="Customer email for reference")
    external_reference: Optional[str] = Field(
        None, description="External reference ID (e.g., payment_id from Payment Service)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "quantity": 2,
                    "customer_email": "fan@example.com",
                    "external_reference": "pay_abc123",
                }
            ]
        }
    }


class ReservationResponse(BaseModel):
    """Reservation response object, includes issued tickets after confirmation."""

    id: UUID
    ticket_category_id: UUID
    quantity: int
    status: str
    customer_email: Optional[str] = None
    external_reference: Optional[str] = None
    expires_at: datetime
    confirmed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    issued_tickets: List[IssuedTicketResponse] = Field(
        default_factory=list,
        description="Issued tickets (populated only after confirmation via lazy minting)",
    )

    model_config = {"from_attributes": True}


class ReservationListResponse(BaseModel):
    """Paginated list of reservations."""

    data: List[ReservationResponse]
    total: int = Field(..., description="Total number of reservations")
    skip: int
    limit: int
