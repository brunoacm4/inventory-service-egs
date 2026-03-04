from app.api.events import router as events_router
from app.api.tickets import router as ticket_categories_router
from app.api.reservations import router as reservations_router
from app.api.health import router as health_router

__all__ = ["events_router", "ticket_categories_router", "reservations_router", "health_router"]
