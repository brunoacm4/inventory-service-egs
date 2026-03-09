"""
API-key authentication dependency for service-to-service calls.

The Inventory Service is an internal service — only the Composer Service
calls it. Authentication is via the X-API-Key header.
JWT validation is the Composer's responsibility (user-facing gateway).
"""

from typing import Optional

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.utils.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_auth(
    api_key: Optional[str] = Security(api_key_header),
) -> dict:
    """
    Validate the X-API-Key header for service-to-service authentication.
    Returns a dict with auth metadata.
    """
    if api_key and api_key == settings.api_key:
        return {"type": "api_key"}

    raise HTTPException(
        status_code=401,
        detail="Missing or invalid API key",
    )
