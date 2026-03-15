# Inventory Service

A production-ready inventory management microservice for the **FlashSale** platform. Built with Domain-Driven Design principles — manages events, ticket category batches, temporary reservations with atomic stock operations, and lazy-minted individual tickets for high-concurrency flash sale scenarios.

## Tech Stack

- **FastAPI** (Python 3.12) + **PostgreSQL** + **Redis**
- **Docker Compose** — single `docker compose up --build -d` to run everything
- **OpenAPI 3.1** with Swagger UI

## Quick Start

1. Copy your API key into `.env` (already created from the template)
2. Run `docker compose up --build -d`
3. Open [localhost:8001/docs](http://localhost:8001/docs) for the interactive Swagger UI

Everything runs in Docker — PostgreSQL, Redis, and the API.

## Domain Concepts

- **Event**: A concert, festival, or show with dates and venue.
- **Ticket**: An individual ticket linked to an event, with category and price info.
- **Reservation state**: A temporary hold represented by ticket status `reserved`.
- **Ticket lifecycle**: `available -> reserved -> sold -> used`.

## Key Components

- **Models**: SQLAlchemy models for `Event` and `Ticket` lifecycle/state transitions.
- **Schemas**: Pydantic request/response contracts for events and tickets.
- **Services**: Business logic for event management, ticket inventory, and expiry jobs.
- **API**: FastAPI routers under `/api/v1` for Events and Tickets domains.
- **Middleware**: API-key auth support with Redis-backed rate limiting and idempotency.

## API Endpoints

### Events — Manage event catalog

| Method | Endpoint                                  | Description              |
|--------|-------------------------------------------|--------------------------|
| POST   | `/api/v1/events`                          | Create an event          |
| GET    | `/api/v1/events`                          | List events              |
| GET    | `/api/v1/events/{event_id}`               | Get event details        |
| PUT    | `/api/v1/events/{event_id}`               | Update an event          |
| DELETE | `/api/v1/events/{event_id}`               | Delete an event          |
| POST   | `/api/v1/events/{event_id}/tickets`       | Batch-create tickets     |
| GET    | `/api/v1/events/{event_id}/tickets`       | List tickets for event   |

### Tickets — Manage ticket lifecycle

| Method | Endpoint                                  | Description                    |
|--------|-------------------------------------------|--------------------------------|
| GET    | `/api/v1/tickets/{ticket_id}`             | Get ticket details             |
| PUT    | `/api/v1/tickets/{ticket_id}/reserve`     | Reserve available ticket       |
| PUT    | `/api/v1/tickets/{ticket_id}/sell`        | Sell reserved ticket           |
| PUT    | `/api/v1/tickets/{ticket_id}/use`         | Use sold ticket                |
| DELETE | `/api/v1/tickets/{ticket_id}`             | Cancel reserved ticket         |

### Health

| Method | Endpoint   | Description                                        |
|--------|------------|----------------------------------------------------|
| GET    | `/health`  | Health check (PostgreSQL + Redis, 200 or 503)      |

## Authentication

All API endpoints (except health) require an `X-API-Key` header.

## Rate Limiting

API requests are rate-limited per API key. Check the `X-RateLimit-*` response headers for current limits.

## Business Logic Flow

1. **Composer** creates an event
2. **Composer** batch-creates tickets for the event
3. Fan browses events and retrieves ticket inventory for that event
4. Checkout reserves a specific available ticket with `PUT /api/v1/tickets/{ticket_id}/reserve`
5. On payment success, call `PUT /api/v1/tickets/{ticket_id}/sell`
6. At venue entry, call `PUT /api/v1/tickets/{ticket_id}/use`
7. On payment failure/abandonment, call `DELETE /api/v1/tickets/{ticket_id}` to release stock

## Environment Variables

| Variable                  | Default                           | Description                    |
|---------------------------|-----------------------------------|--------------------------------|
| `DATABASE_URL`            | `postgresql+asyncpg://...`        | PostgreSQL connection string   |
| `REDIS_URL`               | `redis://redis:6379/0`            | Redis connection string        |
| `API_KEY`                 | `sk_test_inventory_change_me`     | API authentication key         |
| `RATE_LIMIT_PER_MINUTE`   | `60`                              | Max requests per minute per key|
| `RESERVATION_TTL_MINUTES` | `15`                              | Reservation expiry in minutes  |
