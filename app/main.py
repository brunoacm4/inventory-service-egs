from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import events_router, tickets_router, reservations_router, health_router
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.utils.config import settings
from app.utils.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup: create tables
    await init_db()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Inventory management microservice for the FlashSale platform. "
        "Manages events, ticket categories, stock control, and temporary reservations. "
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

# Rate Limiter
app.add_middleware(RateLimiterMiddleware)

# Routers
app.include_router(health_router)
app.include_router(events_router)
app.include_router(tickets_router)
app.include_router(reservations_router)
