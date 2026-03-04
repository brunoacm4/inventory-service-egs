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

| Concept              | Description                                                                                  |
|----------------------|----------------------------------------------------------------------------------------------|
| **Event**            | A concert, festival, or show with dates and venue                                            |
| **TicketCategory**   | A batch/tier of tickets (e.g., 5000 VIP seats at €149). Defines price, stock, sale window    |
| **Reservation**      | A temporary hold on stock while payment processes. Expires after TTL (default: 15 min)       |
| **IssuedTicket**     | An individual unique ticket, minted lazily only upon reservation confirmation (after payment) |

## Key Components

| Component   | Files                          | Purpose                                               |
|-------------|--------------------------------|-------------------------------------------------------|
| Models      | 4 SQLAlchemy models            | `Event`, `TicketCategory`, `Reservation`, `IssuedTicket` |
| Schemas     | 5 Pydantic schema files        | Request/response validation, OpenAPI docs              |
| Services    | 3 service classes              | Business logic + atomic stock management               |
| API         | 4 endpoint modules             | 17 REST endpoints under `/api/v1/`                     |
| Middleware  | Rate Limiter                   | Redis-backed, per API key                              |

## API Endpoints (17 total)

### Events — Manage event catalog
| Method | Endpoint                                  | Description              |
|--------|-------------------------------------------|--------------------------|
| POST   | `/api/v1/events`                          | Create an event          |
| GET    | `/api/v1/events`                          | List events              |
| GET    | `/api/v1/events/{event_id}`               | Get event details        |
| PUT    | `/api/v1/events/{event_id}`               | Update an event          |
| DELETE | `/api/v1/events/{event_id}`               | Delete an event          |

### Ticket Categories — Manage ticket batches per event
| Method | Endpoint                                                       | Description                    |
|--------|----------------------------------------------------------------|--------------------------------|
| POST   | `/api/v1/events/{event_id}/ticket-categories`                  | Create a ticket category batch |
| GET    | `/api/v1/events/{event_id}/ticket-categories`                  | List categories for an event   |
| GET    | `/api/v1/ticket-categories/{ticket_category_id}`               | Get category details           |
| PUT    | `/api/v1/ticket-categories/{ticket_category_id}`               | Update a category              |
| DELETE | `/api/v1/ticket-categories/{ticket_category_id}`               | Delete a category              |
| GET    | `/api/v1/ticket-categories/{ticket_category_id}/availability`  | Check real-time availability   |

### Reservations — Temporary stock holds (nested under ticket category)
| Method | Endpoint                                                                                  | Description                         |
|--------|-------------------------------------------------------------------------------------------|-------------------------------------|
| POST   | `/api/v1/ticket-categories/{ticket_category_id}/reservations`                             | Create a reservation                |
| GET    | `/api/v1/ticket-categories/{ticket_category_id}/reservations`                             | List reservations                   |
| GET    | `/api/v1/ticket-categories/{ticket_category_id}/reservations/{reservation_id}`            | Get reservation details             |
| POST   | `/api/v1/ticket-categories/{ticket_category_id}/reservations/{reservation_id}/confirm`    | Confirm reservation (lazy minting)  |
| POST   | `/api/v1/ticket-categories/{ticket_category_id}/reservations/{reservation_id}/cancel`     | Cancel reservation (release stock)  |

### Health
| Method | Endpoint   | Description                                        |
|--------|------------|----------------------------------------------------|
| GET    | `/health`  | Health check (PostgreSQL + Redis, 200 or 503)      |

## Authentication

All API endpoints (except health) require an `X-API-Key` header.

## Rate Limiting

API requests are rate-limited per API key. Check the `X-RateLimit-*` response headers for current limits.

## Business Logic Flow

1. **Composer** creates an event and ticket category batches via the Inventory Service
2. Fan browses events and checks **availability** on a ticket category
3. Composer calls `POST /ticket-categories/{id}/reservations` to temporarily hold tickets (stock decremented atomically with `SELECT ... FOR UPDATE`)
4. Payment Service processes the transaction
5. On success: Composer calls `POST /reservations/{id}/confirm` — **lazy minting** kicks in, generating unique `IssuedTicket` records for each unit
6. On failure: Composer calls `POST /reservations/{id}/cancel` — stock is released back to the pool

Reservations expire automatically after the configured TTL (default: 15 minutes).

## Environment Variables

| Variable                  | Default                           | Description                    |
|---------------------------|-----------------------------------|--------------------------------|
| `DATABASE_URL`            | `postgresql+asyncpg://...`        | PostgreSQL connection string   |
| `REDIS_URL`               | `redis://redis:6379/0`            | Redis connection string        |
| `API_KEY`                 | `sk_test_inventory_change_me`     | API authentication key         |
| `RATE_LIMIT_PER_MINUTE`   | `60`                              | Max requests per minute per key|
| `RESERVATION_TTL_MINUTES` | `15`                              | Reservation expiry in minutes  |
