"""FastAPI-level tests for GET /api/customers."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import config, models
from app.booking import orders as orders_mod
from app.console.auth import sessions as auth
from app.console.customers import api as customers_api
from app.main import app

client = TestClient(app)


def _c(id, name, email=None, phone=None):
    props = {"phone": phone} if phone else {}
    return {
        "id": id,
        "type": "customers",
        "attributes": {"name": name, "email": email, "properties": props, "created_at": "2026-01-01T00:00:00Z"},
    }


CUSTOMERS = [
    _c("c2", "Zed Zimmer", "zed@example.com"),
    _c("c1", "Amy Adams", "amy@example.com", "+15551234567"),
    _c("c3", "Bob Brown", None, "+15559876543"),
]


def _order(id, customer_id, starts):
    return {
        "id": id,
        "type": "orders",
        "attributes": {
            "status": "stopped",
            "starts_at": starts,
            "stops_at": starts,
            "payment_status": "paid",
            "customer_id": customer_id,
            "number": 1,
        },
    }


ORDERS = [
    _order("o1", "c1", "2026-03-01T10:00:00Z"),
    _order("o2", "c1", "2026-05-01T10:00:00Z"),
]


class FakeClient:
    calls = 0
    error: Exception | None = None
    orders_error: Exception | None = None

    async def list_all(self, path, *, page_size=50, params=None):
        assert path == "customers"
        type(self).calls += 1
        if type(self).error:
            raise type(self).error
        return CUSTOMERS

    async def list_all_with_included(self, path, *, page_size=50, params=None):
        if type(self).orders_error:
            raise type(self).orders_error
        return ORDERS, CUSTOMERS


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    FakeClient.calls = 0
    FakeClient.error = None
    FakeClient.orders_error = None
    orders_mod.clear_cache()
    customers_api.clear_cache()
    monkeypatch.setattr(customers_api, "BooqableClient", FakeClient)
    app.dependency_overrides[auth.require_auth] = lambda: models.AuthSession(
        token="test", user_email="admin@example.com", expires_at=datetime.max
    )
    yield
    app.dependency_overrides.clear()
    customers_api.clear_cache()


def test_lists_customers_sorted_by_name():
    body = client.get("/api/customers").json()
    assert [c["id"] for c in body["items"]] == ["c1", "c3", "c2"]
    assert body["items"][0] == {
        "id": "c1",
        "name": "Amy Adams",
        "email": "amy@example.com",
        "phone": "+15551234567",
        "createdAt": "2026-01-01T00:00:00Z",
        "booqableUrl": f"{config.BOOQABLE_COMPANY_URL}/customers/c1",
        "bookingCount": 2,
        "lastBookingAt": "2026-05-01T10:00:00+00:00",
    }
    assert body["items"][1]["bookingCount"] == 0 and body["items"][1]["lastBookingAt"] is None
    assert body["total"] == 3 and body["fetchedAt"]


def test_search_matches_name_email_and_phone():
    ids = lambda q: [c["id"] for c in client.get("/api/customers", params={"q": q}).json()["items"]]
    assert ids("brown") == ["c3"]
    assert ids("ZED@") == ["c2"]
    assert ids("5551234") == ["c1"]


def test_pagination_and_caching_and_refresh():
    p2 = client.get("/api/customers", params={"pageSize": 2, "page": 2}).json()
    assert [c["id"] for c in p2["items"]] == ["c2"] and p2["total"] == 3
    assert FakeClient.calls == 1
    client.get("/api/customers", params={"refresh": True})
    assert FakeClient.calls == 2


def test_upstream_failure_is_502():
    FakeClient.error = RuntimeError("boom")
    assert client.get("/api/customers").status_code == 502


def test_requires_auth():
    app.dependency_overrides.clear()
    assert client.get("/api/customers").status_code in (401, 403)


def test_list_survives_orders_failure():
    FakeClient.orders_error = RuntimeError("orders down")
    body = client.get("/api/customers").json()
    assert len(body["items"]) == 3
    assert body["items"][0]["bookingCount"] is None


def test_detail_returns_customer_with_bookings_newest_first():
    body = client.get("/api/customers/c1").json()
    assert body["customer"]["name"] == "Amy Adams"
    assert body["customer"]["bookingCount"] == 2
    assert [b["id"] for b in body["bookings"]] == ["o2", "o1"]


def test_detail_unknown_customer_is_404():
    assert client.get("/api/customers/nope").status_code == 404
