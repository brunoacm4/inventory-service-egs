from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.kpi import KPIEventsResponse, KPISnapshotResponse
from app.services.kpi_service import KPIService
from app.utils.auth import verify_auth
from app.utils.database import get_db

router = APIRouter(prefix="/internal/kpi", tags=["KPI"])


@router.get(
    "/snapshot",
    response_model=KPISnapshotResponse,
    summary="KPI snapshot",
    description=(
        "Returns a current inventory snapshot for composer-side KPI processing. "
        "Optional event_id narrows the snapshot to a single event."
    ),
)
async def get_kpi_snapshot(
    event_id: Optional[UUID] = Query(None, description="Filter snapshot by event id"),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_auth),
):
    return await KPIService.build_snapshot(db, event_id=event_id)


@router.get(
    "/events",
    response_model=KPIEventsResponse,
    summary="Incremental KPI event feed",
    description=(
        "Returns immutable domain events ordered by occurred_at/id. "
        "Use cursor to fetch incremental updates without duplicates."
    ),
)
async def get_kpi_events(
    cursor: Optional[datetime] = Query(
        None,
        description="ISO-8601 cursor. Returns events strictly newer than cursor.",
    ),
    event_id: Optional[UUID] = Query(None, description="Filter feed by event id"),
    limit: int = Query(500, ge=1, le=1000, description="Max events to return"),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_auth),
):
    return await KPIService.list_events(db, cursor=cursor, event_id=event_id, limit=limit)
