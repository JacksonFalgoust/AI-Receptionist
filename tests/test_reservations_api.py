from fastapi.testclient import TestClient

from app import reservations_api
from app.booqable_client import BooqableError
from app.main import app

client = TestClient(app)


def test_booqable_ping_happy_path(monkeypatch):
    class FakeBooqableClient:
        def attrs(self, resource):
            return resource.get("attributes") or {}

        async def get(self, path, params=None):
            if path == "locations":
                return {"data": [{"id": "loc_1"}]}
            if path == "companies/current":
                return {"data": {"attributes": {"default_timezone": "America/New_York"}}}
            raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(reservations_api, "BooqableClient", FakeBooqableClient)

    response = client.get("/api/booqable/ping")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["sample_location_count"] == 1
    assert body["company_timezone"] == "America/New_York"


def test_booqable_ping_reports_upstream_failure(monkeypatch):
    class FailingClient:
        def __init__(self):
            raise BooqableError("BOOQABLE_API_KEY is not configured")

    monkeypatch.setattr(reservations_api, "BooqableClient", FailingClient)

    response = client.get("/api/booqable/ping")

    # No X-Api-Key sent, no auth of any kind on this route -- it's a plain
    # connectivity check, and the 502 (not 401/500) proves the failure comes
    # from Booqable, not from a missing auth header.
    assert response.status_code == 502
