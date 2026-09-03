import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from app.booqable_client import BooqableClient, BooqableError
from app.reservations import (
    add_customer_note,
    find_or_create_customer,
    get_order_contact,
    list_catalog,
    list_customers,
    register_customer,
)


def _customer(id_: str, *, name: str, email: str | None = None, phone: str | None = None) -> dict:
    # Booqable echoes properties back with a lowercased key regardless of the
    # 'name' casing used when writing (verified against a live account).
    attrs = {"name": name}
    if email:
        attrs["email"] = email
    if phone:
        attrs["properties"] = {"phone": phone}
    return {"type": "customers", "id": id_, "attributes": attrs}


def test_matches_existing_customer_by_email():
    client = object.__new__(BooqableClient)
    existing = [_customer("cust_1", name="Jane Doe", email="jane@example.com")]
    client.list_all = AsyncMock(return_value=existing)
    client.post = AsyncMock()

    result = asyncio.run(find_or_create_customer(client, name="Jane Doe", email="JANE@example.com"))

    assert result["id"] == "cust_1"
    client.post.assert_not_called()


def test_matches_existing_customer_by_phone_despite_formatting():
    client = object.__new__(BooqableClient)
    existing = [_customer("cust_1", name="Jane Doe", phone="+1 (555) 123-4567")]
    client.list_all = AsyncMock(return_value=existing)
    client.post = AsyncMock()

    result = asyncio.run(find_or_create_customer(client, name="Jane Doe", phone="555-123-4567"))

    assert result["id"] == "cust_1"
    client.post.assert_not_called()


def test_creates_new_customer_when_no_match():
    client = object.__new__(BooqableClient)
    client.list_all = AsyncMock(return_value=[])
    created = _customer("cust_2", name="John Smith", phone="5559876543")
    client.post = AsyncMock(return_value={"data": created})

    result = asyncio.run(find_or_create_customer(client, name="John Smith", phone="555-987-6543"))

    assert result["id"] == "cust_2"
    client.post.assert_called_once()


def test_creates_customer_with_phone_via_properties_attributes():
    # Booqable v4 rejects a top-level 'phone' attribute (400 unknown_attribute) and
    # attributes.properties is read-only (400 unwritable_attribute) -- phone must be
    # side-posted via the Rails-style properties_attributes array. Verified live.
    client = object.__new__(BooqableClient)
    client.list_all = AsyncMock(return_value=[])
    created = _customer("cust_4", name="Pat Lee", phone="5551112222")
    client.post = AsyncMock(return_value={"data": created})

    asyncio.run(find_or_create_customer(client, name="Pat Lee", phone="555-111-2222"))

    posted_attributes = client.post.call_args.kwargs["json"]["data"]["attributes"]
    assert "phone" not in posted_attributes
    assert "properties" not in posted_attributes
    assert posted_attributes["properties_attributes"] == [
        {"type": "Property::Phone", "name": "Phone", "value": "555-111-2222"}
    ]


def test_does_not_look_up_when_neither_email_nor_phone():
    client = object.__new__(BooqableClient)
    client.list_all = AsyncMock(return_value=[])
    created = _customer("cust_3", name="No Contact")
    client.post = AsyncMock(return_value={"data": created})

    result = asyncio.run(find_or_create_customer(client, name="No Contact"))

    assert result["id"] == "cust_3"
    client.list_all.assert_not_called()


def test_list_customers_maps_fields():
    client = object.__new__(BooqableClient)
    client.list_all = AsyncMock(
        return_value=[
            _customer("cust_1", name="Jane Doe", email="jane@example.com", phone="+15551234567"),
            _customer("cust_2", name="No Contact"),
        ]
    )

    result = asyncio.run(list_customers(client))

    assert result == [
        {"customer_id": "cust_1", "name": "Jane Doe", "email": "jane@example.com", "phone": "+15551234567"},
        {"customer_id": "cust_2", "name": "No Contact", "email": None, "phone": None},
    ]
    client.list_all.assert_called_once_with("customers", params={"filter[archived][eq]": "false"})


def test_add_customer_note_posts_v4_note_shape():
    client = object.__new__(BooqableClient)
    client.post = AsyncMock(return_value={"data": {"type": "notes", "id": "note_1"}})

    asyncio.run(add_customer_note(client, "cust_1", "wants to buy an e-bike"))

    posted = client.post.call_args.kwargs["json"]["data"]
    assert posted["type"] == "notes"
    assert posted["attributes"] == {
        "body": "wants to buy an e-bike",
        "owner_id": "cust_1",
        "owner_type": "customers",
    }


def test_register_customer_records_note():
    client = object.__new__(BooqableClient)
    created = _customer("cust_1", name="Jane Doe", phone="5551234567")
    client.list_all = AsyncMock(return_value=[])
    client.post = AsyncMock(
        side_effect=[
            {"data": created},
            {"data": {"type": "notes", "id": "note_1"}},
        ]
    )

    result = asyncio.run(
        register_customer(client, name="Jane Doe", phone="5551234567", note="wants to buy an e-bike")
    )

    assert result["customer_id"] == "cust_1"
    assert result["note_recorded"] is True
    assert client.post.call_count == 2
    note_payload = client.post.call_args_list[1].kwargs["json"]["data"]
    assert note_payload["attributes"]["owner_id"] == "cust_1"
    assert note_payload["attributes"]["body"] == "wants to buy an e-bike"


def test_register_customer_without_note_skips_note_call():
    client = object.__new__(BooqableClient)
    created = _customer("cust_2", name="No Note")
    client.list_all = AsyncMock(return_value=[])
    client.post = AsyncMock(return_value={"data": created})

    result = asyncio.run(register_customer(client, name="No Note"))

    assert result["note_recorded"] is False
    assert "note_error" not in result
    client.post.assert_called_once()


def test_register_customer_note_failure_is_non_fatal():
    client = object.__new__(BooqableClient)
    created = _customer("cust_3", name="Pat Lee", phone="5559876543")
    client.list_all = AsyncMock(return_value=[])
    client.post = AsyncMock(
        side_effect=[
            {"data": created},
            BooqableError("Booqable POST notes failed (422): bad note"),
        ]
    )

    result = asyncio.run(
        register_customer(client, name="Pat Lee", phone="5559876543", note="asked to speak to a person")
    )

    assert result["customer_id"] == "cust_3"
    assert result["note_recorded"] is False
    assert "note_error" in result


def test_get_order_contact_returns_phone_and_total():
    client = object.__new__(BooqableClient)
    order = {
        "type": "orders",
        "id": "order_1",
        "attributes": {"customer_id": "cust_1", "grand_total_in_cents": 12345},
    }
    customer = _customer("cust_1", name="Jane Doe", email="jane@example.com", phone="+15551234567")
    client.get = AsyncMock(side_effect=[{"data": order}, {"data": customer}])

    result = asyncio.run(get_order_contact(client, "order_1"))

    assert result == {
        "order_id": "order_1",
        "customer_id": "cust_1",
        "name": "Jane Doe",
        "phone": "+15551234567",
        "email": "jane@example.com",
        "grand_total_usd": 123.45,
    }
    client.get.assert_any_call("orders/order_1")
    client.get.assert_any_call("customers/cust_1")


def test_get_order_contact_raises_when_no_linked_customer():
    client = object.__new__(BooqableClient)
    order = {"type": "orders", "id": "order_2", "attributes": {"grand_total_in_cents": 0}}
    client.get = AsyncMock(return_value={"data": order})

    with pytest.raises(BooqableError):
        asyncio.run(get_order_contact(client, "order_2"))


def _group(id_: str, *, name: str, sku: str = "") -> dict:
    return {
        "type": "product_groups",
        "id": id_,
        "attributes": {
            "name": name,
            "sku": sku,
            "trackable": True,
            "price_period": "day",
            "flat_fee_price_in_cents": 1000,
            "deposit_in_cents": 5000,
        },
    }


def _group_detail_response(group_id: str, product_id: str) -> dict:
    # Shape of a GET product_groups/{id}?include=products response:
    # relationships points at the product, included carries its resource.
    return {
        "data": {
            "type": "product_groups",
            "id": group_id,
            "relationships": {"products": {"data": {"type": "products", "id": product_id}}},
        },
        "included": [{"type": "products", "id": product_id}],
    }


def test_list_catalog_maps_group_and_product_fields():
    client = object.__new__(BooqableClient)
    client.list_all = AsyncMock(return_value=[_group("g1", name="Cruiser Bike", sku="CRZ-1")])
    client.get = AsyncMock(return_value=_group_detail_response("g1", "p1"))

    catalog = asyncio.run(list_catalog(client))

    assert catalog == [
        {
            "product_group_id": "g1",
            "product_id": "p1",
            "name": "Cruiser Bike",
            "sku": "CRZ-1",
            "trackable": True,
            "price_period": "day",
            "flat_fee_price_usd": 10.0,
            "deposit_usd": 50.0,
        }
    ]


def test_list_catalog_fetches_each_group_concurrently():
    """BooqableClient.list_all discards the bulk list's `included` array (it
    only returns `data`), so each group needs its own re-fetch for its
    product -- but doing those sequentially is what actually blew the local
    demo's whole turn budget on a ~14-group catalog (5-9s; see
    logs/app.log). They must run concurrently instead."""
    client = object.__new__(BooqableClient)
    groups = [_group(f"g{i}", name=f"Bike {i}") for i in range(5)]
    client.list_all = AsyncMock(return_value=groups)

    async def slow_get(path, **kwargs):
        await asyncio.sleep(0.05)
        group_id = path.split("/")[1]
        return _group_detail_response(group_id, f"p-{group_id}")

    client.get = slow_get

    start = time.monotonic()
    catalog = asyncio.run(list_catalog(client))
    elapsed = time.monotonic() - start

    assert len(catalog) == 5
    # Sequential would take ~5 * 0.05s = 0.25s; concurrent is close to one
    # slot's worth. Generous ceiling to avoid flaking on a slow box.
    assert elapsed < 0.2
