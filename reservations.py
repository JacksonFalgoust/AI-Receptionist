from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import config
from booqable_client import BooqableClient, BooqableError

RECEPTIONIST_TAG = "ai-receptionist"

CANCELABLE_STATUSES = {"new", "draft", "reserved", "started", "stopped"}


def _parse_datetime(value: str) -> datetime:
    """Parse a caller-supplied ISO 8601 date/time into a UTC datetime.
    Naive values are treated as being in config.BOOQABLE_TIMEZONE."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(config.BOOQABLE_TIMEZONE))
    return dt.astimezone(ZoneInfo("UTC"))


def _order_timestamp(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _availability_filter_timestamp(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


async def resolve_existing_location(client: BooqableClient) -> dict[str, Any]:
    """Use the single active Booqable location. Never creates locations."""
    existing = await client.list_all("locations", params={"filter[archived][eq]": "false"})
    if not existing:
        raise BooqableError("No active locations found in Booqable. Create one in Booqable first.")
    if len(existing) > 1:
        # Prefer rental/pickup-enabled locations when more than one exists.
        preferred = [
            item
            for item in existing
            if client.attrs(item).get("location_type") == "rental"
            or client.attrs(item).get("pickup_enabled") is True
        ]
        return preferred[0] if preferred else existing[0]
    return existing[0]


async def _load_product_groups(client: BooqableClient) -> list[dict[str, Any]]:
    return await client.list_all(
        "product_groups",
        params={"filter[archived][eq]": "false", "include": "products"},
    )


async def _product_for_group(client: BooqableClient, group: dict[str, Any]) -> dict[str, Any] | None:
    included_products = []
    # Prefer re-fetch with include
    detail = await client.get(
        f"product_groups/{group['id']}",
        params={"include": "products"},
    )
    included = detail.get("included") or []
    for item in included:
        if item.get("type") == "products":
            included_products.append(item)

    relationships = (detail.get("data") or {}).get("relationships") or {}
    product_rel = (relationships.get("products") or {}).get("data") or []
    if isinstance(product_rel, dict):
        product_rel = [product_rel]

    if product_rel:
        product_id = product_rel[0].get("id")
        for item in included_products:
            if item.get("id") == product_id:
                return item
        product = await client.get(f"products/{product_id}")
        return product.get("data")

    if included_products:
        return included_products[0]

    # Fallback: search products by name/sku
    products = await client.list_all(
        "products",
        params={"filter[archived][eq]": "false"},
    )
    group_name = client.attrs(group).get("name")
    group_sku = client.attrs(group).get("sku")
    for product in products:
        attrs = client.attrs(product)
        if attrs.get("product_group_id") == group["id"]:
            return product
        if attrs.get("name") == group_name or attrs.get("sku") == group_sku:
            return product
    return None


async def resolve_location(client: BooqableClient, location_id: str | None) -> dict[str, Any]:
    if location_id:
        return (await client.get(f"locations/{location_id}"))["data"]
    return await resolve_existing_location(client)


async def list_catalog(client: BooqableClient) -> list[dict[str, Any]]:
    """Live rentable product catalog, for the receptionist to browse/search."""
    groups = await _load_product_groups(client)
    catalog: list[dict[str, Any]] = []
    for group in groups:
        attrs = client.attrs(group)
        product = await _product_for_group(client, group)
        if not product:
            continue
        catalog.append(
            {
                "product_group_id": group["id"],
                "product_id": product["id"],
                "name": attrs.get("name"),
                "sku": attrs.get("sku"),
                "trackable": attrs.get("trackable"),
                "price_period": attrs.get("price_period"),
                "flat_fee_price_usd": (attrs.get("flat_fee_price_in_cents") or 0) / 100,
                "deposit_usd": (attrs.get("deposit_in_cents") or 0) / 100,
            }
        )
    return catalog


async def find_or_create_customer(
    client: BooqableClient, *, name: str, email: str | None = None, phone: str | None = None
) -> dict[str, Any]:
    if email:
        existing = await client.list_all("customers", params={"filter[archived][eq]": "false"})
        for candidate in existing:
            if (client.attrs(candidate).get("email") or "").lower() == email.lower():
                return candidate

    attributes: dict[str, Any] = {"name": name, "legal_type": "person", "tag_list": [RECEPTIONIST_TAG]}
    if email:
        attributes["email"] = email
    if phone:
        attributes["phone"] = phone
    response = await client.post("customers", json=client.resource("customers", attributes))
    return response["data"]


async def check_product_availability(
    client: BooqableClient,
    *,
    product_id: str,
    location_id: str,
    starts_at: str,
    stops_at: str,
    quantity: int,
) -> dict[str, Any]:
    starts_dt = _parse_datetime(starts_at)
    stops_dt = _parse_datetime(stops_at)
    payload = await client.get(
        "inventory_availabilities",
        params={
            "filter[from]": _availability_filter_timestamp(starts_dt),
            "filter[till]": _availability_filter_timestamp(stops_dt),
            "filter[item_id]": product_id,
            "filter[location_id]": location_id,
        },
    )
    data = payload.get("data") or []
    record = data[0] if data else {}
    attrs = client.attrs(record) if record else {}
    available = attrs.get("available")
    if available is None:
        status = "unknown"
    elif available <= 0:
        status = "unavailable"
    elif available < quantity:
        status = "partial"
    else:
        status = "available"
    return {"status": status, "available": available, "requested": quantity}


async def create_reservation(
    client: BooqableClient,
    *,
    customer: dict[str, Any],
    location_id: str | None,
    starts_at: str,
    stops_at: str,
    items: list[dict[str, Any]],
    auto_reserve: bool = True,
) -> dict[str, Any]:
    if not items:
        raise BooqableError("At least one item is required to create a reservation")

    location = await resolve_location(client, location_id)
    starts_dt = _parse_datetime(starts_at)
    stops_dt = _parse_datetime(stops_at)
    starts_api = _order_timestamp(starts_dt)
    stops_api = _order_timestamp(stops_dt)

    customer_record = await find_or_create_customer(
        client, name=customer["name"], email=customer.get("email"), phone=customer.get("phone")
    )

    order_payload = client.resource(
        "orders",
        {
            "status": "draft",
            "customer_id": customer_record["id"],
            "starts_at": starts_api,
            "stops_at": stops_api,
            "start_location_id": location["id"],
            "stop_location_id": location["id"],
            "fulfillment_type": "pickup",
            "tag_list": [RECEPTIONIST_TAG],
        },
    )
    order = (await client.post("orders", json=order_payload))["data"]

    actions = [
        {
            "action": "book_product",
            "mode": "create_new",
            "product_id": item["product_id"],
            "quantity": item["quantity"],
        }
        for item in items
    ]
    booking_error: str | None = None
    try:
        await client.post(
            "order_fulfillments",
            json=client.resource("order_fulfillments", {"order_id": order["id"], "actions": actions}),
        )
    except BooqableError as exc:
        booking_error = str(exc)

    reserved = False
    reserve_error: str | None = None
    if auto_reserve and not booking_error:
        try:
            await client.post(
                "order_status_transitions",
                json=client.resource(
                    "order_status_transitions",
                    {"order_id": order["id"], "transition_from": "draft", "transition_to": "reserved"},
                ),
            )
            reserved = True
        except BooqableError as exc:
            reserve_error = str(exc)

    final_order = (await client.get(f"orders/{order['id']}"))["data"]
    attrs = client.attrs(final_order)
    return {
        "order_id": order["id"],
        "status": attrs.get("status"),
        "customer_id": customer_record["id"],
        "customer_name": client.attrs(customer_record).get("name"),
        "starts_at": starts_api,
        "stops_at": stops_api,
        "location_id": location["id"],
        "price_usd": (attrs.get("price_in_cents") or 0) / 100,
        "grand_total_usd": (attrs.get("grand_total_in_cents") or 0) / 100,
        "deposit_usd": (attrs.get("deposit_in_cents") or 0) / 100,
        "reserved": reserved,
        "booking_error": booking_error,
        "reserve_error": reserve_error,
    }


async def cancel_reservation(client: BooqableClient, order_id: str) -> dict[str, Any]:
    order = (await client.get(f"orders/{order_id}"))["data"]
    status = client.attrs(order).get("status")
    if status in {"canceled", "archived"}:
        return {"order_id": order_id, "status": status, "already_canceled": True}
    if status not in CANCELABLE_STATUSES:
        raise BooqableError(f"Order {order_id} in status '{status}' cannot be canceled")

    await client.post(
        "order_status_transitions",
        json=client.resource(
            "order_status_transitions",
            {"order_id": order_id, "transition_from": status, "transition_to": "canceled"},
        ),
    )
    return {"order_id": order_id, "previous_status": status, "status": "canceled"}
