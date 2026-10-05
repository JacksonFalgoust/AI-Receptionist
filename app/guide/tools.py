"""Client-side tool calls: GuideAnts hands every tool call declared on the
guide back to this app, and execute_tool answers it in-process."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from app import config
from app.booking import payments, reservations
from app.booking.booqable_client import BooqableClient, BooqableError
from app.booking.postmark_client import PostmarkError
from app.booking.twilio_client import TwilioSmsError

from .session import GuideSession

logger = logging.getLogger("voice_receptionist.guide")


# All of these tools -- get_caller_phone_number plus the Booqable reservation
# operations below -- are declared as GuideAnts "Client Actions" tool sources
# (see guide-demo/caller-phone-client-tool.json and
# guide-demo/reservations-client-tool.json), not attached by this app --
# GuideAnts includes them on the guide's behalf and, being client-handled (a
# client:// server URL), never executes them itself: it always hands the
# function_call back to whichever client is on that conversation. This app
# only needs to answer it when it arrives. The reservation operations used to
# be a Web API tool source that GuideAnts called directly against
# /api/reservations/*; moving them here means there's no HTTP endpoint left
# for anyone but this app (mid-call) to invoke them through -- see
# docs/ARCHITECTURE.md's "Client-side tool calls" section.
_RESERVATION_TOOLS = {
    "listCatalog",
    "checkAvailability",
    "listCustomers",
    "createCustomer",
    "createReservation",
    "findReservations",
    "cancelReservation",
    "sendPaymentLink",
}

# Business-language (action, system) label for each reservation tool's
# ConversationAction row -- mirrors the frontend's routingLabels.ts/
# knowledgeLabels.ts pattern of keeping raw identifiers out of admin-facing
# copy.
_TOOL_ACTION_LABELS: dict[str, tuple[str, str]] = {
    "listCatalog": ("List catalog", "Booqable"),
    "checkAvailability": ("Check availability", "Booqable"),
    "listCustomers": ("Look up customer", "Booqable"),
    "createCustomer": ("Create customer", "Booqable"),
    "createReservation": ("Create reservation", "Booqable"),
    "findReservations": ("Find reservation", "Booqable"),
    "cancelReservation": ("Cancel reservation", "Booqable"),
    "sendPaymentLink": ("Send payment link", "Messaging"),
}


async def _run_reservation_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Execute one Booqable-backed reservation tool -- the same business
    logic the old /api/reservations/* routes wrapped (app/booking/reservations.py,
    app/booking/payments.py), called directly instead of over HTTP. Required
    arguments missing from `args` raise KeyError, caught by the caller."""
    client = BooqableClient()
    if name == "listCatalog":
        return {"products": await reservations.list_catalog(client)}
    if name == "checkAvailability":
        location = await reservations.resolve_location(client, args.get("location_id"))
        result = await reservations.check_product_availability(
            client,
            product_id=args["product_id"],
            location_id=location["id"],
            starts_at=args["starts_at"],
            stops_at=args["stops_at"],
            quantity=args.get("quantity", 1),
        )
        return {**result, "location_id": location["id"]}
    if name == "listCustomers":
        return {"customers": await reservations.list_customers(client)}
    if name == "createCustomer":
        return await reservations.register_customer(
            client,
            name=args["customer_name"],
            email=args.get("customer_email"),
            phone=args.get("customer_phone"),
            note=args.get("note"),
        )
    if name == "createReservation":
        if not args.get("customer_email") and not args.get("customer_phone"):
            raise BooqableError("customer_email or customer_phone is required")
        return await reservations.create_reservation(
            client,
            customer={
                "name": args["customer_name"],
                "email": args.get("customer_email"),
                "phone": args.get("customer_phone"),
            },
            location_id=args.get("location_id"),
            starts_at=args["starts_at"],
            stops_at=args["stops_at"],
            items=args["items"],
            auto_reserve=args.get("auto_reserve", True),
        )
    if name == "findReservations":
        return await reservations.find_reservations(
            client, email=args.get("customer_email"), phone=args.get("customer_phone")
        )
    if name == "cancelReservation":
        return await reservations.cancel_reservation(client, args["order_id"])
    if name == "sendPaymentLink":
        return await payments.send_payment_link(
            client,
            order_id=args["order_id"],
            channel=args.get("channel"),
            phone=args.get("phone"),
            email=args.get("email"),
        )
    raise KeyError(name)


async def execute_tool(name: str, arguments: str, session: GuideSession) -> str:
    """Run one client-side tool call and return its result as the string to
    send back as a function_call_output. Never raises -- an error result is
    still a well-formed reply the model can react to."""
    if name == "get_caller_phone_number":
        if not session.known_customer_checked:
            session.known_customer_checked = True
            if session.caller_phone:
                try:
                    client = BooqableClient()
                    session.known_customer = await asyncio.wait_for(
                        reservations.find_customer(client, phone=session.caller_phone),
                        timeout=config.CALLER_LOOKUP_TIMEOUT_SECONDS,
                    )
                except Exception:
                    session.known_customer = None
        result: dict[str, Any] = {"phone_number": session.caller_phone}
        if session.known_customer:
            attrs = BooqableClient.attrs(session.known_customer)
            if attrs.get("name"):
                result["customer_name"] = attrs["name"]
            if attrs.get("email"):
                result["customer_email"] = attrs["email"]
        return json.dumps(result)
    if name in _RESERVATION_TOOLS:
        try:
            args = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError:
            logger.warning("Guide sent malformed arguments for %r: %r", name, arguments)
            args = {}
            result: dict[str, Any] = {"error": "malformed arguments"}
        else:
            try:
                result = await _run_reservation_tool(name, args)
            except (BooqableError, TwilioSmsError, PostmarkError) as exc:
                logger.warning("Reservation tool %r failed: %s", name, exc)
                result = {"error": str(exc)}
            except KeyError as exc:
                result = {"error": f"missing required argument: {exc}"}
        action_label, system_label = _TOOL_ACTION_LABELS.get(name, (name, "Booqable"))
        # Args can contain nested objects/arrays (e.g. createReservation's
        # `items` list of dicts), but ConversationAction.details is persisted
        # and rendered by the frontend as Record<str, str> -- flatten any
        # non-string value to its JSON representation so it's always
        # frontend-safe while staying informative.
        details = {k: v if isinstance(v, str) else json.dumps(v) for k, v in args.items()}
        session.actions.append(
            {
                "action": action_label,
                "system": system_label,
                "result": result.get("error", "Completed successfully"),
                "status": "error" if "error" in result else "success",
                "details": details,
                "at": datetime.utcnow(),
            }
        )
        return json.dumps(result)
    logger.warning("Guide requested unknown tool %r; returning error result", name)
    return json.dumps({"error": f"unknown tool: {name}"})
