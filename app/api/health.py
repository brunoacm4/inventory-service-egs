from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as aioredis

from app.utils.database import get_db
from app.utils.config import settings

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Health check",
    description=(
        "Verifies that the service is running and can connect to PostgreSQL and Redis. "
        "Returns 200 if all dependencies are healthy, 503 otherwise."
    ),
)
async def health_check(db: AsyncSession = Depends(get_db)):
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

    all_ok = all(v == "connected" for v in checks.values())

    if all_ok:
        return {"status": "healthy"}

    return JSONResponse(
        status_code=503,
        content={"status": "unhealthy", "checks": checks},
    )
