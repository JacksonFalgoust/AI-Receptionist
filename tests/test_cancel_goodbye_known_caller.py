"""17:52 test-call fixes: cancel filler, local/spoken reservation times,
goodbye triggers and no double goodbye, known caller note, spoken name."""

import asyncio
from pathlib import Path

from app import call_end, config, fillers, guide_client, reservations
from app.guide_client import Delta, GuideSession
from app.guide_publish import render

TEMPLATE = Path(__file__).resolve().parents[1] / "guide-demo" / "template" / "instructions.template.md"


# --- B: cancel filler ---------------------------------------------------------

def test_cancel_tool_gets_cancel_filler():
    assert fillers.action_for_tools(["cancelReservation"]) == "cancel"
    phrase = fillers.pick_for_tools(["cancelReservation"], ["x"])
    assert phrase in fillers.ACTION_FILLERS["cancel"]
    assert "book" not in phrase.lower()


def test_create_still_booking_filler():
    assert fillers.action_for_tools(["createReservation"]) == "booking"


# --- B: local, speakable times --------------------------------------------------

def test_utc_order_time_spoken_in_local_time(monkeypatch):
    monkeypatch.setattr(config, "BOOQABLE_TIMEZONE", "America/New_York")
    # Order #53: 13:00 UTC on Oct 17 is 9 AM Eastern, not "1 PM".
    when = reservations.spoken_when("2026-10-17T13:00:00.000000+00:00", "2026-10-17T22:00:00Z")
    assert when["date_spoken"] == "Saturday, October 17th"
    assert when["start_time_spoken"] == "9 AM"
    assert when["end_time_spoken"] == "6 PM"
    assert when["starts_local"].startswith("2026-10-17T09:00:00-04:00")


def test_ordinals():
    assert [reservations._ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 31)] == [
        "1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "23rd", "31st"
    ]


def test_spoken_time_minutes_and_bad_input():
    assert reservations.spoken_time("2026-10-14T19:30:00Z") == "3:30 PM"
    assert reservations.spoken_when(None) == {}
    assert reservations.spoken_date("not a date") is None


class _FakeClient:
    def __init__(self):
        self.posted = []

    @staticmethod
    def attrs(r):
        return r.get("attributes", {})

    async def list_all(self, kind, params=None):
        if kind == "customers":
            return [{"id": "c1", "attributes": {"name": "Eric Smith", "phone": "+15550003374"}}]
        return [{"id": "o1", "attributes": {"status": "reserved"}}]

    async def get(self, path, params=None):
        return {"data": {"id": "o1", "attributes": {
            "status": "reserved", "starts_at": "2026-10-17T13:00:00+00:00",
            "stops_at": "2026-10-17T22:00:00+00:00", "grand_total_in_cents": 6900}}, "included": []}

    @staticmethod
    def resource(kind, attrs):
        return {"data": {"type": kind, "attributes": attrs}}

    async def post(self, path, json=None):
        self.posted.append(path)


def test_find_reservations_has_spoken_local_fields(monkeypatch):
    monkeypatch.setattr(reservations, "_customer_phone", lambda a: a.get("phone"))
    out = asyncio.run(reservations.find_reservations(_FakeClient(), phone="+15550003374"))
    r = out["reservations"][0]
    assert r["date_spoken"] == "Saturday, October 17th" and r["start_time_spoken"] == "9 AM"
    assert "UTC" in out["note"]


def test_cancel_result_has_spoken_fields():
    c = _FakeClient()
    out = asyncio.run(reservations.cancel_reservation(c, "o1"))
    assert out["status"] == "canceled" and out["start_time_spoken"] == "9 AM"


# --- C: goodbye triggers --------------------------------------------------------

def test_okay_thank_you_is_done():
    assert call_end.caller_done("Okay. Thank you.")
    assert call_end.caller_done("Alright, thanks.")
    assert not call_end.caller_done("Okay, I want to book.")


def test_other_questions_counts_as_anything_else():
    assert call_end.asked_anything_else(
        "No problem at all, just let me know when you're ready or if you have any other questions."
    )
    assert call_end.asked_anything_else("Is there anything else I can help you with today?")
    assert not call_end.asked_anything_else("Shall I go ahead and book it?")


def _run_rounds(monkeypatch, rounds):
    """rounds: list of (text, [tool names]) per model round."""
    it = iter(rounds)

    async def fake_turn(client, inp, session, outcome):
        text, tools = next(it)
        yield text
        for n, name in enumerate(tools):
            outcome.function_calls.append((f"c{n}", name, "{}"))

    async def outputs(outcome, session):
        return [{"type": "function_call_output"}]

    monkeypatch.setattr(guide_client, "_stream_turn", fake_turn)
    monkeypatch.setattr(guide_client, "_tool_outputs", outputs)

    async def run():
        return [e async for e in guide_client._stream_reply_with_tools(None, "bye", GuideSession())]

    events = asyncio.run(run())
    return "".join(e.text for e in events if isinstance(e, Delta))


def test_no_double_goodbye_after_endcall(monkeypatch):
    spoken = _run_rounds(monkeypatch, [
        ("Declare victory. That's fine, Eric. Thanks for calling, have a great day! Goodbye.", ["endCall"]),
        ("Declare victory. Thanks for calling, have a great day! Goodbye.", []),
    ])
    assert spoken.lower().count("goodbye") == 1


def test_goodbye_after_endcall_still_spoken_when_not_said_before(monkeypatch):
    spoken = _run_rounds(monkeypatch, [
        ("", ["endCall"]),
        ("Declare victory. Thanks for calling! Goodbye.", []),
    ])
    assert spoken.lower().count("goodbye") == 1


# --- C: spoken business name ----------------------------------------------------

def test_spoken_name_alias(monkeypatch):
    monkeypatch.setattr(config, "SPOKEN_NAME_ALIASES", {"Peachtree": "Peach tree"})
    assert render.spoken_name("Peachtree Pedals") == "Peach tree Pedals"


def test_template_uses_spoken_name_slot():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "{{business.spoken_name}}" in text


# --- A: instructions ---------------------------------------------------------------

def test_template_cancel_and_wording_rules():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "DECLINING A PENDING BOOKING" in text
    assert "do not call findReservations or cancelReservation" in text
    assert '"I have you down for"' in text
    assert "date_spoken" in text


# --- D: known caller ---------------------------------------------------------------

def test_known_caller_note_names_customer_without_full_number():
    s = GuideSession(caller_phone="+15550003374")
    s.known_customer = {"id": "c1", "attributes": {"name": "Eric Smith"}}
    note = guide_client.known_caller_note(s)
    assert "Eric Smith" in note and "Never ask for their name" in note
    assert "3, 3, 7, 4" in note and "5550003374" not in note


def test_known_caller_note_prefixed_once(monkeypatch):
    s = GuideSession(caller_phone="+15550003374")
    s.known_customer = {"id": "c1", "attributes": {"name": "Eric Smith"}}
    s.known_customer_checked = True
    first = asyncio.run(guide_client._with_known_caller_note("I'd like a bike.", s))
    second = asyncio.run(guide_client._with_known_caller_note("3 PM.", s))
    assert first.startswith("[Note: this caller is a known customer, Eric Smith") and first.endswith("I'd like a bike.")
    assert second == "3 PM."


def test_unknown_caller_gets_no_note():
    s = GuideSession(caller_phone="+15550009999")
    assert asyncio.run(guide_client._with_known_caller_note("Hi", s)) == "Hi"


def test_setup_lookup_fills_session(monkeypatch):
    async def fake_find(client, phone=None, email=None):
        return {"id": "c1", "attributes": {"name": "Eric Smith"}}

    monkeypatch.setattr(guide_client, "BooqableClient", lambda: object())
    monkeypatch.setattr(guide_client.reservations, "find_customer", fake_find)
    s = GuideSession(caller_phone="+15550003374")
    asyncio.run(guide_client.lookup_known_caller(s))
    assert s.known_customer_checked and s.known_customer["id"] == "c1"
