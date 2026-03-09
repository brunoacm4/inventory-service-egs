from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class TicketBatchCreate(BaseModel):
    """
    Request body to batch-create tickets for an event.
    Internally creates a TicketCategory and N individual Ticket records
    with status 'available'.
    """

    name: str = Field(
        ..., min_length=1, max_length=255,
        description="Ticket category name (e.g. VIP, General Admission)",
    )
    description: Optional[str] = Field(None, description="Ticket category description")
    price: Decimal = Field(..., ge=0, decimal_places=2, description="Price per ticket")
    currency: str = Field("EUR", max_length=3, description="ISO 4217 currency code")
    total_quantity: int = Field(..., ge=1, description="Number of tickets to create")
    max_per_order: Optional[int] = Field(
        10, ge=1, description="Maximum tickets per single reservation",
    )
    sale_start: Optional[datetime] = Field(None, description="When ticket sales open (ISO 8601)")
    sale_end: Optional[datetime] = Field(None, description="When ticket sales close (ISO 8601)")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "General Admission",
                    "description": "Standard entry ticket",
                    "price": 49.99,
                    "currency": "EUR",
                    "total_quantity": 5000,
                    "max_per_order": 4,
                    "sale_start": "2026-03-01T10:00:00Z",
                    "sale_end": "2026-06-20T17:00:00Z",
                }
            ]
        }
    }


class TicketReserveRequest(BaseModel):
    """
    Request body to reserve tickets for an event.
    The service picks N available tickets from the specified event
    and transitions them to 'reserved' status.
    """

    quantity: int = Field(..., ge=1, description="Number of tickets to reserve")
    external_reference: Optional[str] = Field(
        None, description="External reference / correlation ID set by the Composer Service",
    )
    ticket_category_id: Optional[UUID] = Field(
        None, description="Optional: reserve from a specific ticket category",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "quantity": 2,
                    "external_reference": "order_abc123",
                }
            ]
        }
    }


class TicketResponse(BaseModel):
    """Response object for a single ticket."""

    id: UUID
    event_id: UUID
    ticket_category_id: UUID
    status: str
    external_reference: Optional[str] = None
    reserved_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Denormalized from TicketCategory
    category_name: Optional[str] = Field(None, description="Ticket category name")
    price: Optional[Decimal] = Field(None, description="Ticket price")
    currency: Optional[str] = Field(None, description="Currency code")

    model_config = {"from_attributes": True}


class TicketListResponse(BaseModel):
    """Paginated list of tickets."""

    data: List[TicketResponse]
    total: int = Field(..., description="Total number of tickets matching the query")
    skip: int
    limit: int


class TicketReserveResponse(BaseModel):
    """Response for a reserve tickets operation."""

    reserved_count: int = Field(..., description="Number of tickets successfully reserved")
    tickets: List[TicketResponse]
