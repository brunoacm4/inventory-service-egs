from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    """Request body to create an event."""

    name: str = Field(..., min_length=1, max_length=255, description="Event name")
    description: Optional[str] = Field(None, description="Detailed event description")
    venue: Optional[str] = Field(None, max_length=255, description="Event venue/location")
    date: datetime = Field(..., description="Event start date and time (ISO 8601)")
    end_date: Optional[datetime] = Field(None, description="Event end date and time (ISO 8601)")
    max_capacity: Optional[int] = Field(None, ge=1, description="Maximum total capacity")
    image_url: Optional[str] = Field(None, max_length=500, description="Event image/banner URL")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Rock in Rio Lisboa 2026",
                    "description": "O maior festival de música do mundo regressa a Lisboa.",
                    "venue": "Parque da Bela Vista, Lisboa",
                    "date": "2026-06-20T18:00:00Z",
                    "end_date": "2026-06-21T04:00:00Z",
                    "max_capacity": 80000,
                    "image_url": "https://example.com/rockinrio.jpg",
                }
            ]
        }
    }


class EventUpdate(BaseModel):
    """Request body to update an event. All fields optional."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    venue: Optional[str] = Field(None, max_length=255)
    date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[str] = Field(
        None, description="Event status: draft, published, cancelled, sold_out, completed"
    )
    max_capacity: Optional[int] = Field(None, ge=1)
    image_url: Optional[str] = Field(None, max_length=500)


class EventResponse(BaseModel):
    """Event response object."""

    id: UUID
    name: str
    description: Optional[str] = None
    venue: Optional[str] = None
    date: datetime
    end_date: Optional[datetime] = None
    status: str
    max_capacity: Optional[int] = None
    image_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EventListResponse(BaseModel):
    """Paginated list of events."""

    data: List[EventResponse]
    total: int = Field(..., description="Total number of events matching the query")
    skip: int
    limit: int
