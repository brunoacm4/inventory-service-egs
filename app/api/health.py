from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as aioredis

from app.utils.database import get_db
from app.utils.config import settings

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Health check",
    description="Basic health check to verify the service is running.",
    response_model=dict,
)
async def health_check():
    return {"status": "healthy"}


@router.get(
    "/ready",
    summary="Readiness probe",
    description="Verifies that the service can connect to PostgreSQL and Redis.",
    response_model=dict,
)
async def readiness_check(db: AsyncSession = Depends(get_db)):
    checks = {}

    # Check PostgreSQL
    try:
        await db.execute(text("SELECT 1"))
        checks["postgresql"] = "connected"
    except Exception as e:
        checks["postgresql"] = f"error: {str(e)}"

    # Check Redis
    try:
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        checks["redis"] = "connected"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"

    all_ok = all("connected" in v for v in checks.values())
    return {"status": "ready" if all_ok else "degraded", "checks": checks}
