"""FastAPI-level tests for /api/products (Booqable product groups)."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import models
from app.booking.booqable_client import BooqableError
from app.console.auth import sessions as auth
from app.console.products import api as products_api
from app.main import app

client = TestClient(app)


def _g(id, name, **attrs):
    base = {
        "name": name,
        "sku": None,
        "description": None,
        "product_type": "rental",
        "tracking_type": "bulk",
        "price_type": "simple",
        "price_period": "day",
        "flat_fee_price_in_cents": 2500,
        "deposit_in_cents": 1000,
        "show_in_store": True,
        "archived": False,
    }
    base.update(attrs)
    return {"id": id, "type": "product_groups", "attributes": base}


GROUPS = [_g("g2", "Tent"), _g("g1", "Canoe", sku="CAN-1", description="Two seater")]


class FakeClient:
    calls: list = []
    error: Exception | None = None

    async def list_all(self, path, *, page_size=50, params=None):
        assert path == "product_groups"
        assert params == {"filter[archived][eq]": "false"}
        if type(self).error:
            raise type(self).error
        return GROUPS

    async def request(self, method, path, *, params=None, json=None):
        type(self).calls.append((method, path, json))
        if type(self).error:
            raise type(self).error
        if method == "DELETE":
            return {"data": _g(path.split("/")[1], "Tent", archived=True)}
        attrs = (json or {})["data"]["attributes"]
        return {"data": _g(path.split("/")[1] if "/" in path else "new", **attrs)}

    async def post(self, path, **kw):
        return await self.request("POST", path, **kw)

    async def put(self, path, **kw):
        return await self.request("PUT", path, **kw)

    async def delete(self, path, **kw):
        return await self.request("DELETE", path, **kw)

    @staticmethod
    def resource(type_name, attributes, id=None):
        from app.booking.booqable_client import BooqableClient

        return BooqableClient.resource(type_name, attributes, id)


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    FakeClient.calls = []
    FakeClient.error = None
    monkeypatch.setattr(products_api, "BooqableClient", FakeClient)
    app.dependency_overrides[auth.require_auth] = lambda: models.AuthSession(
        token="test", user_email="admin@example.com", expires_at=datetime.max
    )
    yield
    app.dependency_overrides.clear()


def test_lists_products_sorted_by_name_with_dollar_prices():
    body = client.get("/api/products").json()
    assert [p["id"] for p in body["items"]] == ["g1", "g2"]
    assert body["items"][0] == {
        "id": "g1",
        "name": "Canoe",
        "sku": "CAN-1",
        "description": "Two seater",
        "productType": "rental",
        "trackingType": "bulk",
        "pricePeriod": "day",
        "price": 25.0,
        "deposit": 10.0,
        "showInStore": True,
        "booqableUrl": body["items"][0]["booqableUrl"],
    }
    assert body["total"] == 2


def test_search_matches_name_and_sku():
    ids = lambda q: [p["id"] for p in client.get("/api/products", params={"q": q}).json()["items"]]
    assert ids("tent") == ["g2"]
    assert ids("can-1") == ["g1"]


def test_create_sends_cents_and_creation_only_fields():
    res = client.post(
        "/api/products",
        json={"name": "Kayak", "price": 30.5, "deposit": 5, "productType": "rental", "trackingType": "bulk"},
    )
    assert res.status_code == 201
    method, path, body = FakeClient.calls[0]
    assert (method, path) == ("POST", "product_groups")
    attrs = body["data"]["attributes"]
    assert body["data"]["type"] == "product_groups"
    assert attrs["name"] == "Kayak"
    assert attrs["flat_fee_price_in_cents"] == 3050
    assert attrs["deposit_in_cents"] == 500
    assert attrs["price_type"] == "simple" and attrs["price_period"] == "day"
    assert attrs["product_type"] == "rental" and attrs["tracking_type"] == "bulk"


def test_create_requires_a_name():
    assert client.post("/api/products", json={"name": "  "}).status_code == 422


def test_update_never_sends_creation_only_fields():
    res = client.put("/api/products/g1", json={"name": "Big Canoe", "price": 40})
    assert res.status_code == 200
    method, path, body = FakeClient.calls[0]
    assert (method, path) == ("PUT", "product_groups/g1")
    attrs = body["data"]["attributes"]
    assert attrs["name"] == "Big Canoe" and attrs["flat_fee_price_in_cents"] == 4000
    assert "product_type" not in attrs and "tracking_type" not in attrs
    assert body["data"]["id"] == "g1"


def test_delete_archives_the_product_group():
    res = client.delete("/api/products/g2")
    assert res.status_code == 204
    assert FakeClient.calls[0][:2] == ("DELETE", "product_groups/g2")


def test_booqable_404_is_404_and_other_failures_are_502():
    FakeClient.error = BooqableError("nope", status_code=404)
    assert client.delete("/api/products/x").status_code == 404
    FakeClient.error = BooqableError("bad", status_code=401)
    assert client.get("/api/products").status_code == 502
    FakeClient.error = BooqableError("invalid", status_code=422, payload={"errors": ["x"]})
    assert client.post("/api/products", json={"name": "A"}).status_code == 422


def test_requires_auth():
    app.dependency_overrides.clear()
    assert client.get("/api/products").status_code in (401, 403)
    assert client.delete("/api/products/g1").status_code in (401, 403)
