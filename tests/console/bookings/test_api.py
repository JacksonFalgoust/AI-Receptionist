"""FastAPI-level tests for GET /api/bookings."""

import types
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app import config, models
from app.booking import orders
from app.booking.booqable_client import BooqableClient, BooqableError
from app.console.auth import sessions as auth
from app.console.bookings import api as bookings_api
from app.main import app

NOW = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)
client = TestClient(app)


def _order(id, status, starts, stops, **attrs):
    return {
        "id": id,
        "type": "orders",
        "attributes": {
            "status": status,
            "starts_at": starts,
            "stops_at": stops,
            "payment_status": "paid",
            "customer_id": "c1",
            **attrs,
        },
    }


CUSTOMER = {
    "id": "c1",
    "type": "customers",
    "attributes": {"name": "Jane Doe", "email": "jane@example.com", "properties": {"phone": "+15551234567"}},
}

ORDERS = [
    _order("o1", "reserved", "2026-11-10T20:00:00Z", "2026-11-11T20:00:00Z",
           number=101, grand_total_in_cents=5000, item_count=2, payment_status="unpaid"),
    _order("o2", "reserved", "2026-11-12T20:00:00Z", "2026-11-13T20:00:00Z", number=102),
    _order("o3", "started", "2026-11-09T20:00:00Z", "2026-11-10T20:00:00Z", number=103),
    _order("o4", "stopped", "2026-11-01T20:00:00Z", "2026-11-02T20:00:00Z", number=104),
    _order("o5", "canceled", "2026-11-20T20:00:00Z", "2026-11-21T20:00:00Z", number=105),
    _order("o6", "reserved", "2026-10-01T20:00:00Z", "2026-10-02T20:00:00Z", number=106),
    _order("o7", "draft", "2026-11-12T20:00:00Z", "2026-11-13T20:00:00Z", number=107),
]


def _detail(order_id):
    return {
        "data": {"id": order_id},
        "included": [
            {"type": "lines", "attributes": {"line_type": "charge", "item_id": "i1", "title": "Kayak", "quantity": 2}}
        ],
    }


class FakeClient:
    list_calls = 0
    detail_calls: list[str] = []
    list_error: Exception | None = None

    def __init__(self):
        pass

    @staticmethod
    def attrs(resource):
        return resource.get("attributes") or {}

    async def list_all_with_included(self, path, *, page_size=50, params=None):
        type(self).list_calls += 1
        if type(self).list_error:
            raise type(self).list_error
        return ORDERS, [CUSTOMER]

    async def get(self, path, params=None):
        type(self).detail_calls.append(path)
        return _detail(path.split("/")[1])


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    FakeClient.list_calls = 0
    FakeClient.detail_calls = []
    FakeClient.list_error = None
    orders.clear_cache()
    monkeypatch.setattr(bookings_api, "BooqableClient", FakeClient)
    monkeypatch.setattr(bookings_api, "_now", lambda: NOW)
    app.dependency_overrides[auth.require_auth] = lambda: models.AuthSession(
        token="test", user_email="admin@example.com", expires_at=datetime.max
    )
    yield
    app.dependency_overrides.clear()
    orders.clear_cache()


def test_upcoming_view_lists_future_bookings_with_summary():
    body = client.get("/api/bookings").json()
    assert body["summary"] == {"pickupsToday": 1, "returnsToday": 1, "next7Days": 2, "unpaid": 1}
    assert [b["id"] for b in body["items"]] == ["o3", "o1", "o2"]
    o1 = body["items"][1]
    assert o1 == {
        "id": "o1",
        "number": 101,
        "label": None,
        "customerName": "Jane Doe",
        "customerPhone": "+15551234567",
        "customerEmail": "jane@example.com",
        "items": [{"name": "Kayak", "quantity": 2}],
        "itemCount": 2,
        "startsAt": "2026-11-10T20:00:00+00:00",
        "stopsAt": "2026-11-11T20:00:00+00:00",
        "totalCents": 5000,
        "payment": "unpaid",
        "booqableUrl": f"{config.BOOQABLE_COMPANY_URL}/orders/o1",
    }
    assert body["total"] == 3
    assert body["fetchedAt"]


def test_past_view_lists_returned_canceled_and_not_picked_up():
    body = client.get("/api/bookings", params={"view": "past"}).json()
    labels = {b["id"]: b["label"] for b in body["items"]}
    assert labels == {"o5": "canceled", "o4": "returned", "o6": "not_picked_up"}
    assert "o7" not in labels
    assert "o7" not in [b["id"] for b in client.get("/api/bookings").json()["items"]]


def test_pagination_and_out_of_range_page():
    p2 = client.get("/api/bookings", params={"pageSize": 2, "page": 2}).json()
    assert [b["id"] for b in p2["items"]] == ["o2"]
    assert p2["total"] == 3
    p9 = client.get("/api/bookings", params={"pageSize": 2, "page": 9}).json()
    assert p9["items"] == []
    assert p9["total"] == 3


def test_line_items_fetched_only_for_returned_page():
    client.get("/api/bookings", params={"pageSize": 2, "page": 1})
    assert sorted(FakeClient.detail_calls) == ["orders/o1", "orders/o3"]


def test_refresh_param_bypasses_cache():
    client.get("/api/bookings")
    client.get("/api/bookings")
    assert FakeClient.list_calls == 1
    client.get("/api/bookings", params={"refresh": "true"})
    assert FakeClient.list_calls == 2


def test_booqable_auth_failure_is_502_not_401():
    FakeClient.list_error = BooqableError("unauthorized", status_code=401)
    assert client.get("/api/bookings").status_code == 502


def test_missing_api_key_is_502(monkeypatch):
    class NoKey:
        def __init__(self):
            raise BooqableError("BOOQABLE_API_KEY is not configured")

    monkeypatch.setattr(bookings_api, "BooqableClient", NoKey)
    response = client.get("/api/bookings")
    assert response.status_code == 502
    assert "BOOQABLE_API_KEY" in response.json()["detail"]


@pytest.mark.parametrize("params", [{"page": 0}, {"pageSize": 1000}])
def test_invalid_page_params_are_422(params):
    assert client.get("/api/bookings", params=params).status_code == 422


def test_requires_auth():
    app.dependency_overrides.clear()
    assert client.get("/api/bookings").status_code == 401


def test_customers_from_earlier_pages_are_named(monkeypatch):
    """Runs the REAL paging loop: c1 appears only in page 1's `included`."""
    page1 = [
        _order(f"p{i}", "reserved", "2026-11-12T20:00:00Z", "2026-11-13T20:00:00Z", number=i)
        for i in range(50)
    ]
    page2 = [
        _order("q1", "reserved", "2026-11-14T20:00:00Z", "2026-11-15T20:00:00Z",
               number=900, customer_id="c2")
    ]
    c2 = {"id": "c2", "type": "customers", "attributes": {"name": "Bob Two"}}
    pages = {1: {"data": page1, "included": [CUSTOMER]}, 2: {"data": page2, "included": [c2]}}

    class PagedClient:
        def __init__(self):
            self.list_all_with_included = types.MethodType(
                BooqableClient.list_all_with_included, self
            )

        attrs = staticmethod(FakeClient.attrs)

        async def get(self, path, params=None):
            if path.startswith("orders/"):
                return _detail(path.split("/")[1])
            return pages[params["page[number]"]]

    monkeypatch.setattr(bookings_api, "BooqableClient", PagedClient)
    body = client.get("/api/bookings", params={"pageSize": 100}).json()
    assert body["total"] == 51
    names = {b["id"]: b["customerName"] for b in body["items"]}
    assert names["p0"] == "Jane Doe"
    assert names["q1"] == "Bob Two"


def test_failed_line_fetch_yields_null_items_not_an_error(monkeypatch):
    async def get(self, path, params=None):
        if path == "orders/o1":
            raise BooqableError("boom", status_code=500)
        return _detail(path.split("/")[1])

    monkeypatch.setattr(FakeClient, "get", get)
    response = client.get("/api/bookings")
    assert response.status_code == 200
    by_id = {b["id"]: b for b in response.json()["items"]}
    assert by_id["o1"]["items"] is None
    assert by_id["o1"]["itemCount"] == 2
    assert by_id["o3"]["items"] == [{"name": "Kayak", "quantity": 2}]
    assert by_id["o2"]["items"] == [{"name": "Kayak", "quantity": 2}]


def test_summary_uses_configured_business_timezone(monkeypatch):
    default = client.get("/api/bookings").json()["summary"]
    assert default["pickupsToday"] == 1
    orders.clear_cache()
    # In Singapore (UTC+8) it is still Nov 10 at 15:00 UTC, but the 20:00 UTC
    # pickup/return instants fall on Nov 11, so they are no longer "today".
    monkeypatch.setattr(config, "BOOQABLE_TIMEZONE", "Asia/Singapore")
    shifted = client.get("/api/bookings").json()["summary"]
    assert shifted != default
    assert shifted["returnsToday"] == 0
