from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

import config
import reservations_api
from app import app

client = TestClient(app)


def test_catalog_rejects_missing_api_key(monkeypatch):
    monkeypatch.setattr(config, "RECEPTIONIST_API_KEY", "secret")
    response = client.get("/api/reservations/catalog")
    assert response.status_code == 401


def test_catalog_rejects_wrong_api_key(monkeypatch):
    monkeypatch.setattr(config, "RECEPTIONIST_API_KEY", "secret")
    response = client.get("/api/reservations/catalog", headers={"X-Api-Key": "wrong"})
    assert response.status_code == 401


def test_catalog_fails_clearly_when_key_unconfigured(monkeypatch):
    monkeypatch.setattr(config, "RECEPTIONIST_API_KEY", "")
    response = client.get("/api/reservations/catalog", headers={"X-Api-Key": "anything"})
    assert response.status_code == 500


def test_catalog_happy_path(monkeypatch):
    monkeypatch.setattr(config, "RECEPTIONIST_API_KEY", "secret")
    monkeypatch.setattr(reservations_api, "BooqableClient", lambda: object())
    fake_catalog = [{"product_id": "prod_1", "name": "E-Bike"}]
    monkeypatch.setattr(reservations_api.reservations, "list_catalog", AsyncMock(return_value=fake_catalog))

    response = client.get("/api/reservations/catalog", headers={"X-Api-Key": "secret"})

    assert response.status_code == 200
    assert response.json() == {"products": fake_catalog}


def test_availability_happy_path(monkeypatch):
    monkeypatch.setattr(config, "RECEPTIONIST_API_KEY", "secret")
    monkeypatch.setattr(reservations_api, "BooqableClient", lambda: object())
    monkeypatch.setattr(
        reservations_api.reservations,
        "resolve_location",
        AsyncMock(return_value={"id": "loc_1"}),
    )
    monkeypatch.setattr(
        reservations_api.reservations,
        "check_product_availability",
        AsyncMock(return_value={"status": "available", "available": 3, "requested": 1}),
    )

    response = client.get(
        "/api/reservations/availability",
        headers={"X-Api-Key": "secret"},
        params={
            "product_id": "prod_1",
            "starts_at": "2026-08-01T09:00:00",
            "stops_at": "2026-08-02T17:00:00",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "available"
    assert body["location_id"] == "loc_1"


def test_create_reservation_happy_path(monkeypatch):
    monkeypatch.setattr(config, "RECEPTIONIST_API_KEY", "secret")
    monkeypatch.setattr(reservations_api, "BooqableClient", lambda: object())
    fake_result = {"order_id": "order_1", "status": "reserved", "reserved": True}
    monkeypatch.setattr(
        reservations_api.reservations,
        "create_reservation",
        AsyncMock(return_value=fake_result),
    )

    response = client.post(
        "/api/reservations",
        headers={"X-Api-Key": "secret"},
        json={
            "customer_name": "Jane Doe",
            "customer_phone": "+15551234567",
            "starts_at": "2026-08-01T09:00:00",
            "stops_at": "2026-08-02T17:00:00",
            "items": [{"product_id": "prod_1", "quantity": 1}],
        },
    )

    assert response.status_code == 200
    assert response.json() == fake_result


def test_create_reservation_rejects_customer_without_email_or_phone(monkeypatch):
    monkeypatch.setattr(config, "RECEPTIONIST_API_KEY", "secret")
    monkeypatch.setattr(reservations_api, "BooqableClient", lambda: object())
    monkeypatch.setattr(
        reservations_api.reservations,
        "create_reservation",
        AsyncMock(return_value={}),
    )

    response = client.post(
        "/api/reservations",
        headers={"X-Api-Key": "secret"},
        json={
            "customer_name": "Jane Doe",
            "starts_at": "2026-08-01T09:00:00",
            "stops_at": "2026-08-02T17:00:00",
            "items": [{"product_id": "prod_1", "quantity": 1}],
        },
    )

    assert response.status_code == 422


def test_cancel_reservation_happy_path(monkeypatch):
    monkeypatch.setattr(config, "RECEPTIONIST_API_KEY", "secret")
    monkeypatch.setattr(reservations_api, "BooqableClient", lambda: object())
    fake_result = {"order_id": "order_1", "previous_status": "reserved", "status": "canceled"}
    monkeypatch.setattr(
        reservations_api.reservations,
        "cancel_reservation",
        AsyncMock(return_value=fake_result),
    )

    response = client.post("/api/reservations/order_1/cancel", headers={"X-Api-Key": "secret"})

    assert response.status_code == 200
    assert response.json() == fake_result


def test_booqable_ping_is_not_gated_by_receptionist_key(monkeypatch):
    from booqable_client import BooqableError

    class FailingClient:
        def __init__(self):
            raise BooqableError("BOOQABLE_API_KEY is not configured")

    monkeypatch.setattr(reservations_api, "BooqableClient", FailingClient)

    response = client.get("/api/booqable/ping")

    # No X-Api-Key sent at all; a 502 (not 401/500) proves this route isn't
    # gated by require_receptionist_key and instead reports the Booqable-side
    # failure directly.
    assert response.status_code == 502
