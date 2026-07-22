import asyncio
from unittest.mock import AsyncMock

from booqable_client import BooqableClient
from reservations import find_or_create_customer


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
