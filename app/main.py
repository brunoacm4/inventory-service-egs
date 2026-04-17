import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import events_router, tickets_router, health_router, kpi_router
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.idempotency import IdempotencyMiddleware
from app.services.expiry_service import reservation_expiry_loop
from app.utils.config import settings
from app.utils.database import init_db

# Import all models so Base.metadata.create_all() picks them up
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup: create tables
    await init_db()

    # Launch background task to expire stale reservations
    expiry_task = asyncio.create_task(reservation_expiry_loop())

    yield

    # Shutdown: cancel background tasks
    expiry_task.cancel()
    try:
        await expiry_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Inventory management microservice for the FlashSale platform. "
        "Manages events, ticket stock control, and ticket lifecycle (reserve, sell, use, cancel). "
        "Designed to handle high-concurrency flash sale scenarios with atomic stock operations."
    ),
    openapi_version="3.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Idempotency (applied before rate limiter so cached responses skip it)
app.add_middleware(IdempotencyMiddleware)

# Rate Limiter
app.add_middleware(RateLimiterMiddleware)

# Routers
app.include_router(health_router)
app.include_router(events_router)
app.include_router(tickets_router)
app.include_router(kpi_router)
