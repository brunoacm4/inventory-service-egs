from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class TicketBatchCreate(BaseModel):
    """Request to batch-create tickets for an event."""

    category: str = Field(..., min_length=1, max_length=100, description="Category name (e.g. VIP, General)")
    price: Decimal = Field(..., ge=0, decimal_places=2, description="Price per ticket")
    currency: str = Field("EUR", min_length=3, max_length=3, description="ISO 4217 currency code")
    quantity: int = Field(..., ge=1, le=50000, description="Number of tickets to create")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "category": "VIP",
                    "price": 149.99,
                    "currency": "EUR",
                    "quantity": 100,
                }
            ]
        }
    }


class TicketResponse(BaseModel):
    """Individual ticket response with embedded category info."""

    id: UUID
    event_id: UUID
    category: str
    price: Decimal
    currency: str
    status: str
    customer_email: Optional[str] = None
    external_reference: Optional[str] = None
    reserved_at: Optional[datetime] = None
    sold_at: Optional[datetime] = None
    used_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TicketListResponse(BaseModel):
    """Paginated list of tickets."""

    data: List[TicketResponse]
    total: int = Field(..., description="Total matching tickets")
    skip: int
    limit: int


class BatchCreateResponse(BaseModel):
    """Response after batch-creating tickets."""

    created_count: int = Field(..., description="Number of tickets created")
    category: str
    event_id: UUID


class ReserveRequest(BaseModel):
    """Request body to reserve N tickets."""

    quantity: int = Field(..., ge=1, description="Number of tickets to reserve")
    customer_email: Optional[str] = Field(None, max_length=255, description="Customer email")
    external_reference: Optional[str] = Field(
        None, max_length=255, description="External reference (e.g. order or payment ID)"
    )
    category: Optional[str] = Field(None, max_length=100, description="Filter by category when reserving")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "quantity": 2,
                    "customer_email": "fan@example.com",
                    "external_reference": "ORDER-12345",
                    "category": "VIP",
                }
            ]
        }
    }


class ReserveResponse(BaseModel):
    """Response after reserving tickets — returns the reserved ticket list."""

    reserved_count: int = Field(..., description="Number of tickets successfully reserved")
    tickets: List[TicketResponse]
