# Inventory Service

A production-ready inventory management microservice for the **FlashSale** platform. Manages events, ticket categories, stock control, and temporary reservations with atomic stock operations designed for high-concurrency flash sale scenarios.

## Tech Stack

- **FastAPI** (Python 3.12) + **PostgreSQL** + **Redis**
- **Docker Compose** — single `docker compose up --build -d` to run everything
- **OpenAPI 3.1** with Swagger UI

## Quick Start

1. Copy your API key into `.env` (already created from the template)
2. Run `docker compose up --build -d`
3. Open [localhost:8001/docs](http://localhost:8001/docs) for the interactive Swagger UI

Everything runs in Docker — PostgreSQL, Redis, and the API.

## Key Components

| Component   | Files                          | Purpose                                       |
|-------------|--------------------------------|-----------------------------------------------|
| Models      | 3 SQLAlchemy models            | `Event`, `Ticket`, `Reservation`               |
| Schemas     | 4 Pydantic schema files        | Request/response validation, OpenAPI docs      |
| Services    | 3 service classes              | Business logic + stock management              |
| API         | 4 endpoint modules             | 17 REST endpoints under `/api/v1/`             |
| Middleware  | Rate Limiter                   | Redis-backed, per API key                      |

## API Endpoints (17 total)

### Events — Manage event catalog
| Method | Endpoint                       | Description           |
|--------|--------------------------------|-----------------------|
| POST   | `/api/v1/events`               | Create an event       |
| GET    | `/api/v1/events`               | List events           |
| GET    | `/api/v1/events/{event_id}`    | Get event details     |
| PUT    | `/api/v1/events/{event_id}`    | Update an event       |
| DELETE | `/api/v1/events/{event_id}`    | Delete an event       |

### Tickets — Manage ticket categories per event
| Method | Endpoint                                      | Description                 |
|--------|-----------------------------------------------|-----------------------------|
| POST   | `/api/v1/events/{event_id}/tickets`           | Create a ticket category    |
| GET    | `/api/v1/events/{event_id}/tickets`           | List tickets for an event   |
| GET    | `/api/v1/tickets/{ticket_id}`                 | Get ticket details          |
| PUT    | `/api/v1/tickets/{ticket_id}`                 | Update a ticket category    |
| DELETE | `/api/v1/tickets/{ticket_id}`                 | Delete a ticket category    |
| GET    | `/api/v1/tickets/{ticket_id}/availability`    | Check real-time availability|

### Reservations — Temporary stock holds for payment processing
| Method | Endpoint                                       | Description              |
|--------|------------------------------------------------|--------------------------|
| POST   | `/api/v1/reservations`                         | Create a reservation     |
| GET    | `/api/v1/reservations`                         | List reservations        |
| GET    | `/api/v1/reservations/{reservation_id}`        | Get reservation details  |
| POST   | `/api/v1/reservations/{reservation_id}/confirm`| Confirm reservation      |
| POST   | `/api/v1/reservations/{reservation_id}/cancel` | Cancel reservation       |

### Health
| Method | Endpoint  | Description                          |
|--------|-----------|--------------------------------------|
| GET    | `/health` | Health check                         |
| GET    | `/ready`  | Readiness probe (DB + Redis status)  |

## Authentication

All API endpoints (except health checks) require an `X-API-Key` header.

## Rate Limiting

API requests are rate-limited per API key. Check the `X-RateLimit-*` response headers for current limits.

## Business Logic Flow

1. **Composer** creates an event and ticket categories via the Inventory Service
2. Fan browses events and checks ticket **availability**
3. Composer calls `POST /api/v1/reservations` to temporarily hold tickets (stock decremented atomically)
4. Payment Service processes the transaction
5. On success: Composer calls `POST /reservations/{id}/confirm` — stock deduction is permanent
6. On failure: Composer calls `POST /reservations/{id}/cancel` — stock is released back

Reservations expire automatically after the configured TTL (default: 15 minutes).

## Environment Variables

| Variable                  | Default                           | Description                    |
|---------------------------|-----------------------------------|--------------------------------|
| `DATABASE_URL`            | `postgresql+asyncpg://...`        | PostgreSQL connection string   |
| `REDIS_URL`               | `redis://redis:6379/0`            | Redis connection string        |
| `API_KEY`                 | `sk_test_inventory_change_me`     | API authentication key         |
| `RATE_LIMIT_PER_MINUTE`   | `60`                              | Max requests per minute per key|
| `RESERVATION_TTL_MINUTES` | `15`                              | Reservation expiry in minutes  |
