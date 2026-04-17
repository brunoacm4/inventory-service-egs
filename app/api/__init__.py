from app.api.events import router as events_router
from app.api.tickets import router as tickets_router
from app.api.health import router as health_router
from app.api.kpi import router as kpi_router

__all__ = ["events_router", "tickets_router", "health_router", "kpi_router"]
