from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class KPITicketStatusCounts(BaseModel):
    total: int = 0
    available: int = 0
    reserved: int = 0
    sold: int = 0
    used: int = 0


class KPICategorySnapshot(BaseModel):
    category: str
    counts: KPITicketStatusCounts


class KPISnapshotResponse(BaseModel):
    enabled: bool = True
    generated_at: datetime
    event_id: Optional[UUID] = None
    counts: KPITicketStatusCounts
    by_category: List[KPICategorySnapshot] = Field(default_factory=list)


class KPIEventItem(BaseModel):
    id: UUID
    occurred_at: datetime
    event_type: str
    event_id: Optional[UUID] = None
    ticket_id: Optional[UUID] = None
    category: Optional[str] = None
    price: Optional[Decimal] = None
    currency: Optional[str] = None
    status_before: Optional[str] = None
    status_after: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class KPIEventsResponse(BaseModel):
    enabled: bool = True
    items: List[KPIEventItem]
    next_cursor: Optional[datetime] = None
