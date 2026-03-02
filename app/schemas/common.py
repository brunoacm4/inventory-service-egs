from pydantic import BaseModel, Field
from typing import Optional


class ErrorResponse(BaseModel):
    """Standard error response following RFC 7807."""

    type: str = Field(..., description="Error type URI")
    title: str = Field(..., description="Short human-readable summary")
    status: int = Field(..., description="HTTP status code")
    detail: str = Field(..., description="Human-readable explanation")
    instance: Optional[str] = Field(None, description="URI of the request that caused the error")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "type": "https://errors.flashsale.com/not-found",
                    "title": "Resource Not Found",
                    "status": 404,
                    "detail": "The requested event was not found.",
                    "instance": "/api/v1/events/123",
                }
            ]
        }
    }


class PaginationParams(BaseModel):
    """Common pagination parameters."""

    skip: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of records to return")
