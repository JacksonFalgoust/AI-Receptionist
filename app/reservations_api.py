"""Booqable reservation API -- the surface the GuideAnts receptionist guide
calls (via its imported OpenAPI tool definition, see
guide-demo/booqable-reservations-openapi.json) to check availability and book
rentals, instead of talking to Booqable's own JSON:API directly. Kept as a
separate router from the Twilio call-handling in app.py: this is an inbound
HTTP surface for GuideAnts' tool calls, unrelated to the Twilio WS bridge.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, model_validator

from . import config, reservations
from .booqable_client import BooqableClient, BooqableError

router = APIRouter()


class ReservationItem(BaseModel):
    product_id: str = Field(description="Booqable product id, from /api/reservations/catalog")
    quantity: int = Field(gt=0)


class ReservationRequest(BaseModel):
    # Flat rather than a nested "customer" object: the GuideAnts OpenAPI-to-tool-schema
    # converter (OpenApiHelper.cs) only reads top-level requestBody properties/required --
    # a nested object's own properties/required (and anyOf) never reach the LLM's tool
    # definition, so the guide had no way to know email/phone existed as fields at all.
    customer_name: str
    customer_email: str | None = None
    customer_phone: str | None = None
    starts_at: str = Field(description="ISO 8601 date/time, e.g. 2026-08-01T09:00:00")
    stops_at: str = Field(description="ISO 8601 date/time, e.g. 2026-08-02T17:00:00")
    items: list[ReservationItem]
    location_id: str | None = Field(default=None, description="Defaults to the account's existing location")
    auto_reserve: bool = Field(
        default=True,
        description="If true, reserve immediately. If false, leave as a draft order for staff review.",
    )

    @model_validator(mode="after")
    def _require_email_or_phone(self) -> "ReservationRequest":
        if not self.customer_email and not self.customer_phone:
            raise ValueError("customer_email or customer_phone is required")
        return self


class CustomerRequest(BaseModel):
    # Flat, not a nested "customer" object -- same GuideAnts OpenAPI-to-tool-schema
    # converter limitation documented on ReservationRequest above.
    customer_name: str
    customer_email: str | None = None
    customer_phone: str | None = None
    note: str | None = Field(
        default=None,
        description="Why the caller wants follow-up, e.g. 'wants to buy an e-bike' or 'asked to speak to a person'.",
    )


async def require_receptionist_key(x_api_key: str | None = Header(default=None)) -> None:
    """Shared secret for the voice-receptionist agent -- distinct from BOOQABLE_API_KEY,
    which must never be exposed to the calling LLM."""
    if not config.RECEPTIONIST_API_KEY:
        raise HTTPException(status_code=500, detail="RECEPTIONIST_API_KEY is not configured")
    if x_api_key != config.RECEPTIONIST_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Api-Key")


@router.get("/api/booqable/ping")
async def ping_booqable() -> dict[str, Any]:
    """Pre-demo connectivity check: confirms BOOQABLE_API_KEY/BOOQABLE_COMPANY_URL
    are correct before relying on them for a live call."""
    try:
        client = BooqableClient()
        locations = await client.get("locations", params={"page[size]": 1})
        company = await client.get("companies/current")
        attrs = client.attrs(company.get("data") or {})
        return {
            "ok": True,
            "company_url": config.BOOQABLE_COMPANY_URL,
            "sample_location_count": len(locations.get("data") or []),
            "company_timezone": attrs.get("default_timezone"),
            "configured_timezone": config.BOOQABLE_TIMEZONE,
        }
    except BooqableError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/api/reservations/catalog", dependencies=[Depends(require_receptionist_key)])
async def reservations_catalog() -> dict[str, Any]:
    """List rentable products the receptionist can offer to callers."""
    client = BooqableClient()
    return {"products": await reservations.list_catalog(client)}


@router.get("/api/reservations/availability", dependencies=[Depends(require_receptionist_key)])
async def reservations_availability(
    product_id: str,
    starts_at: str,
    stops_at: str,
    quantity: int = 1,
    location_id: str | None = None,
) -> dict[str, Any]:
    """Check whether a product is available for the requested date range and quantity."""
    client = BooqableClient()
    try:
        location = await reservations.resolve_location(client, location_id)
        result = await reservations.check_product_availability(
            client,
            product_id=product_id,
            location_id=location["id"],
            starts_at=starts_at,
            stops_at=stops_at,
            quantity=quantity,
        )
    except BooqableError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from exc
    return {**result, "location_id": location["id"]}


@router.get("/api/reservations/customers", dependencies=[Depends(require_receptionist_key)])
async def list_customers_endpoint() -> dict[str, Any]:
    """List existing customers, for the receptionist to look someone up."""
    client = BooqableClient()
    try:
        return {"customers": await reservations.list_customers(client)}
    except BooqableError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from exc


@router.post("/api/reservations/customers", dependencies=[Depends(require_receptionist_key)])
async def create_customer_endpoint(body: CustomerRequest) -> dict[str, Any]:
    """Register a caller as a customer without booking a reservation. Finds an
    existing match by email/phone rather than duplicating. Optionally records
    an accompanying note (e.g. why they want a callback)."""
    client = BooqableClient()
    try:
        return await reservations.register_customer(
            client,
            name=body.customer_name,
            email=body.customer_email,
            phone=body.customer_phone,
            note=body.note,
        )
    except BooqableError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from exc


@router.post("/api/reservations", dependencies=[Depends(require_receptionist_key)])
async def create_reservation_endpoint(body: ReservationRequest) -> dict[str, Any]:
    """Create (and by default reserve) a rental order for a caller."""
    client = BooqableClient()
    try:
        return await reservations.create_reservation(
            client,
            customer={"name": body.customer_name, "email": body.customer_email, "phone": body.customer_phone},
            location_id=body.location_id,
            starts_at=body.starts_at,
            stops_at=body.stops_at,
            items=[item.model_dump() for item in body.items],
            auto_reserve=body.auto_reserve,
        )
    except BooqableError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from exc


@router.post("/api/reservations/{order_id}/cancel", dependencies=[Depends(require_receptionist_key)])
async def cancel_reservation_endpoint(order_id: str) -> dict[str, Any]:
    """Cancel a reservation made through this API."""
    client = BooqableClient()
    try:
        return await reservations.cancel_reservation(client, order_id)
    except BooqableError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from exc
