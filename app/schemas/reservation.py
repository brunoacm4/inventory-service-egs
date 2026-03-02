from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class ReservationCreate(BaseModel):
    """
    Request body to create a reservation (temporary hold).
    The Composer/Payment Service calls this to reserve tickets
    while the payment is being processed.
    """

    ticket_id: UUID = Field(..., description="Ticket category to reserve")
    quantity: int = Field(..., ge=1, description="Number of tickets to reserve")
    customer_email: Optional[str] = Field(None, description="Customer email for reference")
    external_reference: Optional[str] = Field(
        None, description="External reference ID (e.g., payment_id from Payment Service)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "ticket_id": "550e8400-e29b-41d4-a716-446655440000",
                    "quantity": 2,
                    "customer_email": "fan@example.com",
                    "external_reference": "pay_abc123",
                }
            ]
        }
    }


class ReservationResponse(BaseModel):
    """Reservation response object."""

    id: UUID
    ticket_id: UUID
    quantity: int
    status: str
    customer_email: Optional[str] = None
    external_reference: Optional[str] = None
    expires_at: datetime
    confirmed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReservationListResponse(BaseModel):
    """Paginated list of reservations."""

    data: List[ReservationResponse]
    total: int = Field(..., description="Total number of reservations")
    skip: int
    limit: int
