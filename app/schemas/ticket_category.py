from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class TicketCategoryCreate(BaseModel):
    """Request body to create a ticket category (batch) for an event."""

    name: str = Field(..., min_length=1, max_length=255, description="Ticket category name (e.g. VIP, General Admission)")
    description: Optional[str] = Field(None, description="Ticket category description")
    price: Decimal = Field(..., ge=0, decimal_places=2, description="Price per ticket")
    currency: str = Field("EUR", max_length=3, description="ISO 4217 currency code")
    total_quantity: int = Field(..., ge=1, description="Total number of tickets in this batch")
    max_per_order: Optional[int] = Field(10, ge=1, description="Maximum tickets per single order")
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


class TicketCategoryUpdate(BaseModel):
    """Request body to update a ticket category. All fields optional."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    currency: Optional[str] = Field(None, max_length=3)
    total_quantity: Optional[int] = Field(None, ge=1)
    max_per_order: Optional[int] = Field(None, ge=1)
    sale_start: Optional[datetime] = None
    sale_end: Optional[datetime] = None
    status: Optional[str] = Field(None, description="Status: available, sold_out, inactive")


class TicketCategoryResponse(BaseModel):
    """Ticket category response object."""

    id: UUID
    event_id: UUID
    name: str
    description: Optional[str] = None
    price: Decimal
    currency: str
    total_quantity: int
    available_quantity: int
    max_per_order: Optional[int] = None
    sale_start: Optional[datetime] = None
    sale_end: Optional[datetime] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TicketCategoryListResponse(BaseModel):
    """Paginated list of ticket categories."""

    data: List[TicketCategoryResponse]
    total: int = Field(..., description="Total number of ticket categories")
    skip: int
    limit: int


class TicketCategoryAvailability(BaseModel):
    """Real-time availability check for a ticket category."""

    ticket_category_id: UUID
    event_id: UUID
    name: str
    available_quantity: int
    total_quantity: int
    price: Decimal
    currency: str
    status: str
    is_on_sale: bool = Field(..., description="Whether tickets are currently on sale")
