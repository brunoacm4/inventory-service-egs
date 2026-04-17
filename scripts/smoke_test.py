#!/usr/bin/env python3
"""End-to-end smoke test for the Inventory Service API.

This script exercises all current features exposed by the service:
- Health check
- Event CRUD
- Event ticket batch-create/list
- Ticket get/reserve/sell/use/cancel lifecycle

Exit code:
- 0 when all steps pass
- 1 if any step fails
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import httpx


class SmokeTestError(Exception):
    """Raised when a smoke-test assertion fails."""


class SmokeTester:
    def __init__(self, base_url: str, api_key: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.client = httpx.Client(base_url=self.base_url, timeout=self.timeout)

        self.total_steps = 15
        self.passed_steps = 0
        self.failed_steps = 0

        self.event_id: Optional[str] = None
        self.ticket_ids: List[str] = []
        self.kpi_enabled: Optional[bool] = None
        self.kpi_cursor: Optional[str] = None

    def close(self) -> None:
        self.client.close()

    def _assert(self, condition: bool, message: str) -> None:
        if not condition:
            raise SmokeTestError(message)

    def _request(
        self,
        method: str,
        path: str,
        expected_status: int,
        json_body: Optional[Dict[str, Any]] = None,
        auth: bool = True,
    ) -> Tuple[httpx.Response, Optional[Dict[str, Any]]]:
        headers: Dict[str, str] = {}
        if auth:
            headers["X-API-Key"] = self.api_key

        response = self.client.request(method=method, url=path, json=json_body, headers=headers)

        if response.status_code != expected_status:
            body_preview = response.text[:600]
            raise SmokeTestError(
                f"{method} {path} expected {expected_status}, got {response.status_code}. "
                f"Response: {body_preview}"
            )

        if expected_status == 204:
            return response, None

        try:
            return response, response.json()
        except ValueError as exc:
            raise SmokeTestError(f"{method} {path} returned a non-JSON response.") from exc

    def _run_step(self, number: int, name: str, action: Callable[[], None]) -> None:
        try:
            action()
            self.passed_steps += 1
            print(f"[PASS] Step {number}: {name}")
        except Exception as exc:
            self.failed_steps += 1
            print(f"[FAIL] Step {number}: {name}")
            print(f"       Reason: {exc}")
            raise

    def run(self) -> bool:
        print("Starting Inventory Service smoke test")
        print(f"Base URL: {self.base_url}")
        print(f"Timeout: {self.timeout}s")
        print("")

        now = datetime.now(timezone.utc)
        event_start = now + timedelta(days=30)
        event_end = event_start + timedelta(hours=4)

        created_event_name = f"Smoke Test Event {int(now.timestamp())}"
        updated_event_name = f"{created_event_name} Updated"

        try:
            self._run_step(1, "GET /health", self._step_health)
            self._run_step(
                2,
                "POST /api/v1/events",
                lambda: self._step_create_event(created_event_name, event_start, event_end),
            )
            self._run_step(3, "GET /api/v1/events", self._step_list_events)
            self._run_step(
                4,
                "GET /api/v1/events/{event_id}",
                lambda: self._step_get_event(created_event_name),
            )
            self._run_step(
                5,
                "PUT /api/v1/events/{event_id}",
                lambda: self._step_update_event(updated_event_name),
            )
            self._run_step(6, "POST /api/v1/events/{event_id}/tickets", self._step_create_tickets)
            self._run_step(7, "GET /internal/kpi/snapshot?event_id=...", self._step_kpi_snapshot)
            self._run_step(8, "GET /api/v1/events/{event_id}/tickets", self._step_list_tickets)
            self._run_step(9, "GET /api/v1/tickets/{ticket_id}", self._step_get_ticket)
            self._run_step(10, "PUT /api/v1/tickets/{ticket_id}/reserve", self._step_reserve_ticket_primary)
            self._run_step(11, "PUT /api/v1/tickets/{ticket_id}/sell", self._step_sell_ticket_primary)
            self._run_step(12, "PUT /api/v1/tickets/{ticket_id}/use", self._step_use_ticket_primary)
            self._run_step(
                13,
                "Reserve another ticket and DELETE /api/v1/tickets/{ticket_id}",
                self._step_cancel_flow,
            )
            self._run_step(14, "GET /internal/kpi/events?event_id=...", self._step_kpi_events)
            self._run_step(15, "DELETE /api/v1/events/{event_id}", self._step_delete_event)

        except Exception:
            pass
        finally:
            print("")
            print("Smoke test summary")
            print(f"Passed: {self.passed_steps}/{self.total_steps}")
            print(f"Failed: {self.failed_steps}/{self.total_steps}")

            # Best-effort cleanup when a failure leaves the test event behind.
            if self.event_id is not None and self.failed_steps > 0:
                try:
                    self._request("DELETE", f"/api/v1/events/{self.event_id}", expected_status=204, auth=True)
                    print("Cleanup: deleted test event")
                except Exception:
                    print("Cleanup: could not delete test event")

        return self.passed_steps == self.total_steps and self.failed_steps == 0

    def _step_health(self) -> None:
        response, data = self._request("GET", "/health", expected_status=200, auth=False)
        self._assert(response.status_code == 200, "Health endpoint did not return 200.")
        self._assert(data is not None, "Health response body is missing.")
        self._assert(data.get("status") == "healthy", "Health status is not 'healthy'.")

    def _step_create_event(self, event_name: str, start: datetime, end: datetime) -> None:
        payload = {
            "name": event_name,
            "description": "Smoke test event for end-to-end API validation",
            "venue": "Smoke Arena",
            "date": start.isoformat(),
            "end_date": end.isoformat(),
            "max_capacity": 1000,
            "image_url": "https://example.com/smoke-event.png",
        }
        _, data = self._request("POST", "/api/v1/events", expected_status=201, json_body=payload, auth=True)
        self._assert(data is not None, "Create event response body is missing.")
        self._assert("id" in data, "Create event response missing 'id'.")
        self._assert(data.get("name") == event_name, "Created event name mismatch.")
        self.event_id = data["id"]

    def _step_list_events(self) -> None:
        self._assert(self.event_id is not None, "event_id not set before listing events.")
        _, data = self._request("GET", "/api/v1/events", expected_status=200, auth=True)
        self._assert(data is not None, "List events response body is missing.")
        items = data.get("data", [])
        self._assert(isinstance(items, list), "List events 'data' is not a list.")
        self._assert(any(item.get("id") == self.event_id for item in items), "Created event not found in list.")

    def _step_get_event(self, expected_name: str) -> None:
        self._assert(self.event_id is not None, "event_id not set before get event.")
        _, data = self._request("GET", f"/api/v1/events/{self.event_id}", expected_status=200, auth=True)
        self._assert(data is not None, "Get event response body is missing.")
        self._assert(data.get("id") == self.event_id, "Get event returned incorrect id.")
        self._assert(data.get("name") == expected_name, "Get event returned unexpected name.")

    def _step_update_event(self, updated_name: str) -> None:
        self._assert(self.event_id is not None, "event_id not set before update event.")
        payload = {
            "name": updated_name,
            "status": "published",
        }
        _, data = self._request(
            "PUT",
            f"/api/v1/events/{self.event_id}",
            expected_status=200,
            json_body=payload,
            auth=True,
        )
        self._assert(data is not None, "Update event response body is missing.")
        self._assert(data.get("name") == updated_name, "Updated event name mismatch.")
        self._assert(data.get("status") == "published", "Updated event status mismatch.")

    def _step_create_tickets(self) -> None:
        self._assert(self.event_id is not None, "event_id not set before creating tickets.")
        payload = {
            "category": "General",
            "price": "49.99",
            "currency": "EUR",
            "quantity": 4,
        }
        _, data = self._request(
            "POST",
            f"/api/v1/events/{self.event_id}/tickets",
            expected_status=201,
            json_body=payload,
            auth=True,
        )
        self._assert(data is not None, "Create tickets response body is missing.")
        items = data.get("data", [])
        self._assert(isinstance(items, list), "Create tickets 'data' is not a list.")
        self._assert(len(items) >= 3, "Expected at least 3 created tickets.")
        self.ticket_ids = [item["id"] for item in items]

    def _step_list_tickets(self) -> None:
        self._assert(self.event_id is not None, "event_id not set before listing tickets.")
        _, data = self._request("GET", f"/api/v1/events/{self.event_id}/tickets", expected_status=200, auth=True)
        self._assert(data is not None, "List tickets response body is missing.")
        items = data.get("data", [])
        self._assert(isinstance(items, list), "List tickets 'data' is not a list.")
        self._assert(len(items) >= 3, "Expected at least 3 tickets in list.")

    def _step_kpi_snapshot(self) -> None:
        self._assert(self.event_id is not None, "event_id not set before KPI snapshot.")
        query = urlencode({"event_id": self.event_id})
        _, data = self._request("GET", f"/internal/kpi/snapshot?{query}", expected_status=200, auth=True)

        self._assert(data is not None, "KPI snapshot response body is missing.")
        self._assert("enabled" in data, "KPI snapshot missing 'enabled' field.")

        self.kpi_enabled = bool(data.get("enabled"))
        if not self.kpi_enabled:
            return

        counts = data.get("counts")
        self._assert(isinstance(counts, dict), "KPI snapshot 'counts' is not an object.")
        self._assert(counts.get("total", 0) >= len(self.ticket_ids), "KPI snapshot total count is lower than created tickets.")
        self._assert(counts.get("available", 0) >= len(self.ticket_ids), "KPI snapshot available count is lower than expected.")

        by_category = data.get("by_category", [])
        self._assert(isinstance(by_category, list), "KPI snapshot 'by_category' is not a list.")

    def _step_get_ticket(self) -> None:
        self._assert(len(self.ticket_ids) >= 1, "No ticket ids available for get ticket.")
        ticket_id = self.ticket_ids[0]
        _, data = self._request("GET", f"/api/v1/tickets/{ticket_id}", expected_status=200, auth=True)
        self._assert(data is not None, "Get ticket response body is missing.")
        self._assert(data.get("id") == ticket_id, "Get ticket returned incorrect id.")
        self._assert(data.get("status") == "available", "Ticket should start as 'available'.")

    def _step_reserve_ticket_primary(self) -> None:
        self._assert(len(self.ticket_ids) >= 1, "No ticket ids available for reserve.")
        ticket_id = self.ticket_ids[0]
        _, data = self._request("PUT", f"/api/v1/tickets/{ticket_id}/reserve", expected_status=200, auth=True)
        self._assert(data is not None, "Reserve ticket response body is missing.")
        self._assert(data.get("status") == "reserved", "Ticket status should be 'reserved' after reserve.")

    def _step_sell_ticket_primary(self) -> None:
        self._assert(len(self.ticket_ids) >= 1, "No ticket ids available for sell.")
        ticket_id = self.ticket_ids[0]
        _, data = self._request("PUT", f"/api/v1/tickets/{ticket_id}/sell", expected_status=200, auth=True)
        self._assert(data is not None, "Sell ticket response body is missing.")
        self._assert(data.get("status") == "sold", "Ticket status should be 'sold' after sell.")

    def _step_use_ticket_primary(self) -> None:
        self._assert(len(self.ticket_ids) >= 1, "No ticket ids available for use.")
        ticket_id = self.ticket_ids[0]
        _, data = self._request("PUT", f"/api/v1/tickets/{ticket_id}/use", expected_status=200, auth=True)
        self._assert(data is not None, "Use ticket response body is missing.")
        self._assert(data.get("status") == "used", "Ticket status should be 'used' after use.")

    def _step_cancel_flow(self) -> None:
        self._assert(len(self.ticket_ids) >= 2, "Need a second ticket id for cancel flow.")
        ticket_id = self.ticket_ids[1]

        _, reserved = self._request("PUT", f"/api/v1/tickets/{ticket_id}/reserve", expected_status=200, auth=True)
        self._assert(reserved is not None, "Reserve in cancel flow returned empty body.")
        self._assert(reserved.get("status") == "reserved", "Reserve in cancel flow did not set status to 'reserved'.")

        _, cancelled = self._request("DELETE", f"/api/v1/tickets/{ticket_id}", expected_status=200, auth=True)
        self._assert(cancelled is not None, "Cancel ticket response body is missing.")
        self._assert(cancelled.get("status") == "available", "Cancelled ticket should return to 'available'.")

    def _step_kpi_events(self) -> None:
        self._assert(self.event_id is not None, "event_id not set before KPI events feed.")
        query = urlencode({"event_id": self.event_id, "limit": 200})
        _, data = self._request("GET", f"/internal/kpi/events?{query}", expected_status=200, auth=True)

        self._assert(data is not None, "KPI events response body is missing.")
        self._assert("enabled" in data, "KPI events response missing 'enabled' field.")

        enabled = bool(data.get("enabled"))
        self.kpi_enabled = enabled if self.kpi_enabled is None else self.kpi_enabled
        if not enabled:
            return

        items = data.get("items", [])
        self._assert(isinstance(items, list), "KPI events 'items' is not a list.")
        self._assert(len(items) > 0, "KPI events feed returned empty list with KPI enabled.")

        event_types = {item.get("event_type") for item in items if isinstance(item, dict)}
        required_types = {
            "event_created",
            "event_updated",
            "tickets_batch_created",
            "ticket_reserved",
            "ticket_sold",
            "ticket_used",
            "ticket_cancelled",
        }
        missing = required_types - event_types
        self._assert(len(missing) == 0, f"KPI events feed missing expected event types: {sorted(missing)}")

        next_cursor = data.get("next_cursor")
        self._assert(next_cursor is not None, "KPI events feed missing next_cursor.")
        self.kpi_cursor = str(next_cursor)

        query_with_cursor = urlencode({"event_id": self.event_id, "limit": 200, "cursor": self.kpi_cursor})
        _, data_with_cursor = self._request(
            "GET",
            f"/internal/kpi/events?{query_with_cursor}",
            expected_status=200,
            auth=True,
        )
        self._assert(data_with_cursor is not None, "KPI events cursor follow-up response is missing.")
        self._assert(data_with_cursor.get("enabled") is True, "KPI events cursor follow-up unexpectedly disabled.")

    def _step_delete_event(self) -> None:
        self._assert(self.event_id is not None, "event_id not set before delete event.")
        self._request("DELETE", f"/api/v1/events/{self.event_id}", expected_status=204, auth=True)
        self.event_id = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test for the Inventory Service API.")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8001",
        help="Base URL of the Inventory Service.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("API_KEY", "sk_test_inventory_change_me"),
        help="API key for the X-API-Key header.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP timeout in seconds.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tester = SmokeTester(base_url=args.base_url, api_key=args.api_key, timeout=args.timeout)
    try:
        success = tester.run()
        return 0 if success else 1
    finally:
        tester.close()


if __name__ == "__main__":
    sys.exit(main())
