import asyncio
import json
from unittest.mock import AsyncMock

from app import config
from app.guide import tools
from app.guide.session import GuideSession


def test_execute_tool_returns_caller_phone(monkeypatch):
    monkeypatch.setattr(config, "BOOQABLE_API_KEY", "test-booqable-key")

    async def fake_find_customer(client, *, email=None, phone=None):
        return None

    monkeypatch.setattr(tools.reservations, "find_customer", fake_find_customer)

    session = GuideSession(caller_phone="+15551234567")
    result = asyncio.run(tools.execute_tool("get_caller_phone_number", "{}", session))
    assert json.loads(result) == {"phone_number": "+15551234567"}


def test_execute_tool_returns_null_when_caller_phone_unknown():
    session = GuideSession(caller_phone=None)
    result = asyncio.run(tools.execute_tool("get_caller_phone_number", "{}", session))
    assert json.loads(result) == {"phone_number": None}


def test_execute_tool_caller_phone_includes_known_customer_info(monkeypatch):
    monkeypatch.setattr(config, "BOOQABLE_API_KEY", "test-booqable-key")

    async def fake_find_customer(client, *, email=None, phone=None):
        return {"id": "cust_1", "attributes": {"name": "Jane Doe", "email": "jane@example.com"}}

    monkeypatch.setattr(tools.reservations, "find_customer", fake_find_customer)

    session = GuideSession(caller_phone="+15551234567")
    result = asyncio.run(tools.execute_tool("get_caller_phone_number", "{}", session))
    assert json.loads(result) == {
        "phone_number": "+15551234567",
        "customer_name": "Jane Doe",
        "customer_email": "jane@example.com",
    }


def test_execute_tool_caller_phone_lookup_raises_falls_back_gracefully(monkeypatch):
    monkeypatch.setattr(config, "BOOQABLE_API_KEY", "test-booqable-key")

    async def fake_find_customer(client, *, email=None, phone=None):
        raise RuntimeError("Booqable is down")

    monkeypatch.setattr(tools.reservations, "find_customer", fake_find_customer)

    session = GuideSession(caller_phone="+15551234567")
    result = asyncio.run(tools.execute_tool("get_caller_phone_number", "{}", session))
    assert json.loads(result) == {"phone_number": "+15551234567"}


def test_execute_tool_caller_phone_lookup_timeout_falls_back_gracefully(monkeypatch):
    monkeypatch.setattr(config, "BOOQABLE_API_KEY", "test-booqable-key")
    monkeypatch.setattr(config, "CALLER_LOOKUP_TIMEOUT_SECONDS", 0.01)

    async def fake_find_customer(client, *, email=None, phone=None):
        await asyncio.sleep(0.5)
        return {"id": "cust_1", "attributes": {"name": "Jane Doe"}}

    monkeypatch.setattr(tools.reservations, "find_customer", fake_find_customer)

    session = GuideSession(caller_phone="+15551234567")
    result = asyncio.run(tools.execute_tool("get_caller_phone_number", "{}", session))
    assert json.loads(result) == {"phone_number": "+15551234567"}


def test_execute_tool_caller_phone_caches_lookup_across_calls(monkeypatch):
    monkeypatch.setattr(config, "BOOQABLE_API_KEY", "test-booqable-key")

    find_customer_mock = AsyncMock(
        return_value={"id": "cust_1", "attributes": {"name": "Jane Doe"}}
    )
    monkeypatch.setattr(tools.reservations, "find_customer", find_customer_mock)

    session = GuideSession(caller_phone="+15551234567")
    first = asyncio.run(tools.execute_tool("get_caller_phone_number", "{}", session))
    second = asyncio.run(tools.execute_tool("get_caller_phone_number", "{}", session))

    assert json.loads(first)["customer_name"] == "Jane Doe"
    assert json.loads(second)["customer_name"] == "Jane Doe"
    assert find_customer_mock.call_count == 1


def test_execute_tool_unknown_tool_returns_error():
    result = asyncio.run(tools.execute_tool("mystery_tool", "{}", GuideSession()))
    assert "error" in json.loads(result)


def test_execute_tool_list_catalog(monkeypatch):
    monkeypatch.setattr(tools, "BooqableClient", lambda: object())
    fake_catalog = [{"product_id": "prod_1", "name": "E-Bike"}]
    monkeypatch.setattr(tools.reservations, "list_catalog", AsyncMock(return_value=fake_catalog))

    result = asyncio.run(tools.execute_tool("listCatalog", "{}", GuideSession()))

    assert json.loads(result) == {"products": fake_catalog}


def test_execute_tool_check_availability(monkeypatch):
    monkeypatch.setattr(tools, "BooqableClient", lambda: object())
    monkeypatch.setattr(
        tools.reservations, "resolve_location", AsyncMock(return_value={"id": "loc_1"})
    )
    monkeypatch.setattr(
        tools.reservations,
        "check_product_availability",
        AsyncMock(return_value={"status": "available", "available": 3, "requested": 1}),
    )

    result = asyncio.run(
        tools.execute_tool(
            "checkAvailability",
            json.dumps(
                {"product_id": "prod_1", "starts_at": "2026-08-01T09:00:00", "stops_at": "2026-08-02T17:00:00"}
            ),
            GuideSession(),
        )
    )

    body = json.loads(result)
    assert body["status"] == "available"
    assert body["location_id"] == "loc_1"


def test_execute_tool_create_reservation_requires_email_or_phone(monkeypatch):
    monkeypatch.setattr(tools, "BooqableClient", lambda: object())
    create_mock = AsyncMock()
    monkeypatch.setattr(tools.reservations, "create_reservation", create_mock)

    result = asyncio.run(
        tools.execute_tool(
            "createReservation",
            json.dumps(
                {
                    "customer_name": "Jane Doe",
                    "starts_at": "2026-08-01T09:00:00",
                    "stops_at": "2026-08-02T17:00:00",
                    "items": [{"product_id": "prod_1", "quantity": 1}],
                }
            ),
            GuideSession(),
        )
    )

    assert "error" in json.loads(result)
    create_mock.assert_not_called()


def test_execute_tool_create_reservation_happy_path(monkeypatch):
    monkeypatch.setattr(tools, "BooqableClient", lambda: object())
    fake_result = {"order_id": "order_1", "status": "reserved", "reserved": True}
    create_mock = AsyncMock(return_value=fake_result)
    monkeypatch.setattr(tools.reservations, "create_reservation", create_mock)

    result = asyncio.run(
        tools.execute_tool(
            "createReservation",
            json.dumps(
                {
                    "customer_name": "Jane Doe",
                    "customer_phone": "+15551234567",
                    "starts_at": "2026-08-01T09:00:00",
                    "stops_at": "2026-08-02T17:00:00",
                    "items": [{"product_id": "prod_1", "quantity": 1}],
                }
            ),
            GuideSession(),
        )
    )

    assert json.loads(result) == fake_result
    assert create_mock.call_args.kwargs["customer"] == {
        "name": "Jane Doe",
        "email": None,
        "phone": "+15551234567",
    }


def test_execute_tool_list_customers(monkeypatch):
    monkeypatch.setattr(tools, "BooqableClient", lambda: object())
    fake_customers = [{"customer_id": "cust_1", "name": "Jane Doe", "email": None, "phone": "+15551234567"}]
    monkeypatch.setattr(tools.reservations, "list_customers", AsyncMock(return_value=fake_customers))

    result = asyncio.run(tools.execute_tool("listCustomers", "{}", GuideSession()))

    assert json.loads(result) == {"customers": fake_customers}


def test_execute_tool_create_customer(monkeypatch):
    monkeypatch.setattr(tools, "BooqableClient", lambda: object())
    fake_result = {
        "customer_id": "cust_1",
        "name": "Jane Doe",
        "email": None,
        "phone": "+15551234567",
        "note_recorded": True,
    }
    register_mock = AsyncMock(return_value=fake_result)
    monkeypatch.setattr(tools.reservations, "register_customer", register_mock)

    result = asyncio.run(
        tools.execute_tool(
            "createCustomer",
            json.dumps(
                {"customer_name": "Jane Doe", "customer_phone": "+15551234567", "note": "wants to buy an e-bike"}
            ),
            GuideSession(),
        )
    )

    assert json.loads(result) == fake_result
    assert register_mock.call_args.kwargs["note"] == "wants to buy an e-bike"


def test_execute_tool_find_reservations(monkeypatch):
    monkeypatch.setattr(tools, "BooqableClient", lambda: object())
    fake_result = {
        "customer_found": True,
        "customer_name": "Jane Doe",
        "reservations": [{"order_id": "order_1", "status": "reserved", "items": [{"name": "Cruiser", "quantity": 1}]}],
    }
    find_mock = AsyncMock(return_value=fake_result)
    monkeypatch.setattr(tools.reservations, "find_reservations", find_mock)

    result = asyncio.run(
        tools.execute_tool("findReservations", json.dumps({"customer_phone": "+15551234567"}), GuideSession())
    )

    assert json.loads(result) == fake_result
    assert find_mock.call_args.kwargs["phone"] == "+15551234567"


def test_execute_tool_cancel_reservation(monkeypatch):
    monkeypatch.setattr(tools, "BooqableClient", lambda: object())
    fake_result = {"order_id": "order_1", "previous_status": "reserved", "status": "canceled"}
    monkeypatch.setattr(tools.reservations, "cancel_reservation", AsyncMock(return_value=fake_result))

    result = asyncio.run(
        tools.execute_tool("cancelReservation", json.dumps({"order_id": "order_1"}), GuideSession())
    )

    assert json.loads(result) == fake_result


def test_execute_tool_send_payment_link(monkeypatch):
    monkeypatch.setattr(tools, "BooqableClient", lambda: object())
    fake_result = {
        "order_id": "order_1",
        "channel": "email",
        "sent_to": "jane@example.com",
        "payment_link": "https://example.com/pay/order_1",
    }
    monkeypatch.setattr(tools.payments, "send_payment_link", AsyncMock(return_value=fake_result))

    result = asyncio.run(
        tools.execute_tool("sendPaymentLink", json.dumps({"order_id": "order_1"}), GuideSession())
    )

    assert json.loads(result) == fake_result


def test_execute_tool_send_payment_link_passes_phone_override(monkeypatch):
    monkeypatch.setattr(tools, "BooqableClient", lambda: object())
    send_mock = AsyncMock(return_value={"order_id": "order_1", "sent_to": "+15559998888", "payment_link": "x"})
    monkeypatch.setattr(tools.payments, "send_payment_link", send_mock)

    asyncio.run(
        tools.execute_tool(
            "sendPaymentLink", json.dumps({"order_id": "order_1", "phone": "+15559998888"}), GuideSession()
        )
    )

    assert send_mock.call_args.kwargs["phone"] == "+15559998888"


def test_execute_tool_send_payment_link_passes_channel_and_email(monkeypatch):
    monkeypatch.setattr(tools, "BooqableClient", lambda: object())
    send_mock = AsyncMock(return_value={"order_id": "order_1", "sent_to": "jane@example.com", "payment_link": "x"})
    monkeypatch.setattr(tools.payments, "send_payment_link", send_mock)

    asyncio.run(
        tools.execute_tool(
            "sendPaymentLink",
            json.dumps({"order_id": "order_1", "channel": "email", "email": "jane@example.com"}),
            GuideSession(),
        )
    )

    assert send_mock.call_args.kwargs["channel"] == "email"
    assert send_mock.call_args.kwargs["email"] == "jane@example.com"


def test_execute_tool_booqable_error_returns_error_json(monkeypatch):
    def raise_error():
        raise tools.BooqableError("BOOQABLE_API_KEY is not configured")

    monkeypatch.setattr(tools, "BooqableClient", raise_error)

    result = asyncio.run(tools.execute_tool("listCatalog", "{}", GuideSession()))

    assert "error" in json.loads(result)


def test_execute_tool_twilio_error_returns_error_json(monkeypatch):
    monkeypatch.setattr(tools, "BooqableClient", lambda: object())
    monkeypatch.setattr(
        tools.payments,
        "send_payment_link",
        AsyncMock(side_effect=tools.TwilioSmsError("Invalid 'To' Phone Number", status_code=400)),
    )

    result = asyncio.run(
        tools.execute_tool("sendPaymentLink", json.dumps({"order_id": "order_1"}), GuideSession())
    )

    assert "error" in json.loads(result)


def test_execute_tool_postmark_error_returns_error_json(monkeypatch):
    monkeypatch.setattr(tools, "BooqableClient", lambda: object())
    monkeypatch.setattr(
        tools.payments,
        "send_payment_link",
        AsyncMock(side_effect=tools.PostmarkError("Inactive recipient", status_code=200, error_code=406)),
    )

    result = asyncio.run(
        tools.execute_tool("sendPaymentLink", json.dumps({"order_id": "order_1"}), GuideSession())
    )

    assert "error" in json.loads(result)


def test_execute_tool_malformed_arguments_returns_error(monkeypatch):
    monkeypatch.setattr(tools, "BooqableClient", lambda: object())

    result = asyncio.run(tools.execute_tool("listCatalog", "not json", GuideSession()))

    assert "error" in json.loads(result)


def test_execute_tool_missing_required_argument_returns_error(monkeypatch):
    monkeypatch.setattr(tools, "BooqableClient", lambda: object())

    result = asyncio.run(tools.execute_tool("cancelReservation", "{}", GuideSession()))

    assert "error" in json.loads(result)


def test_execute_tool_list_catalog_logs_action(monkeypatch):
    monkeypatch.setattr(tools, "BooqableClient", lambda: object())
    monkeypatch.setattr(tools.reservations, "list_catalog", AsyncMock(return_value=[]))
    session = GuideSession()

    asyncio.run(tools.execute_tool("listCatalog", "{}", session))

    assert len(session.actions) == 1
    action = session.actions[0]
    assert action["action"] == "List catalog"
    assert action["system"] == "Booqable"
    assert action["result"] == "Completed successfully"
    assert action["status"] == "success"
    assert action["details"] == {}
    assert isinstance(action["at"], tools.datetime)


def test_execute_tool_reservation_error_logs_action_as_error(monkeypatch):
    monkeypatch.setattr(tools, "BooqableClient", lambda: object())
    session = GuideSession()

    asyncio.run(
        tools.execute_tool(
            "createReservation",
            json.dumps(
                {
                    "customer_name": "Jane Doe",
                    "starts_at": "2026-08-01T09:00:00",
                    "stops_at": "2026-08-02T17:00:00",
                    "items": [{"product_id": "prod_1", "quantity": 1}],
                }
            ),
            session,
        )
    )

    assert session.actions[0]["status"] == "error"
    assert session.actions[0]["action"] == "Create reservation"


def test_execute_tool_flattens_nested_details_to_strings(monkeypatch):
    # createReservation's `items` argument is a list of dicts -- details is
    # persisted and rendered by the frontend as Record<str, str>, so any
    # non-string value must be flattened (via json.dumps) rather than stored
    # as a nested object/array. See finding #2 of the E6 final review.
    monkeypatch.setattr(tools, "BooqableClient", lambda: object())
    fake_result = {"order_id": "order_1", "status": "reserved", "reserved": True}
    monkeypatch.setattr(
        tools.reservations, "create_reservation", AsyncMock(return_value=fake_result)
    )
    session = GuideSession()

    asyncio.run(
        tools.execute_tool(
            "createReservation",
            json.dumps(
                {
                    "customer_name": "Jane Doe",
                    "customer_phone": "+15551234567",
                    "starts_at": "2026-08-01T09:00:00",
                    "stops_at": "2026-08-02T17:00:00",
                    "items": [{"product_id": "prod_1", "quantity": 1}],
                }
            ),
            session,
        )
    )

    details = session.actions[0]["details"]
    for value in details.values():
        assert isinstance(value, str)
    assert details["items"] == json.dumps([{"product_id": "prod_1", "quantity": 1}])
    assert details["customer_name"] == "Jane Doe"  # already a string -- left as-is


def test_execute_tool_malformed_arguments_logs_action_as_error(monkeypatch):
    monkeypatch.setattr(tools, "BooqableClient", lambda: object())
    session = GuideSession()

    result = asyncio.run(tools.execute_tool("createReservation", "{not json", session))

    assert "error" in json.loads(result)
    assert session.actions[0]["status"] == "error"
    assert session.actions[0]["details"] == {}


def test_execute_tool_get_caller_phone_number_does_not_log_an_action():
    session = GuideSession(caller_phone="+15551234567")

    asyncio.run(tools.execute_tool("get_caller_phone_number", "{}", session))

    assert session.actions == []
