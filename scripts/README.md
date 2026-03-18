# Smoke Test Script

This folder contains a simple end-to-end smoke test for the Inventory Service.

## File

- `smoke_test.py`: Calls every main API action and prints PASS/FAIL per step.

## What it tests

1. `GET /health`
2. `POST /api/v1/events`
3. `GET /api/v1/events`
4. `GET /api/v1/events/{event_id}`
5. `PUT /api/v1/events/{event_id}`
6. `POST /api/v1/events/{event_id}/tickets`
7. `GET /api/v1/events/{event_id}/tickets`
8. `GET /api/v1/tickets/{ticket_id}`
9. `PUT /api/v1/tickets/{ticket_id}/reserve`
10. `PUT /api/v1/tickets/{ticket_id}/sell`
11. `PUT /api/v1/tickets/{ticket_id}/use`
12. Reserve another ticket and `DELETE /api/v1/tickets/{ticket_id}`
13. `DELETE /api/v1/events/{event_id}`

## Usage

```bash
python scripts/smoke_test.py --base-url http://localhost:8001
```

Optional args:

- `--api-key` (default: env `API_KEY` or `sk_test_inventory_change_me`)
- `--timeout` (default: `20` seconds)

## Exit code

- `0` all steps passed
- `1` at least one step failed
