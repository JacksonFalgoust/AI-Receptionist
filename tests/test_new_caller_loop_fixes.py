"""22:14 review (new caller loop): calling number for new callers, recap yes
survives a phone/email side question, no text send in the reply that asks,
'the one I'm calling from', and the business-name greeting."""
import asyncio
from pathlib import Path

import pytest

from app import config, guide_client, main
from app.guide_client import Delta, GuideSession, ToolCallStarted
from app.spoken_text import fill_business

ROOT = Path(__file__).resolve().parents[1]
RECAP = ("To recap: one Lake Loop for tomorrow at nine A M, seventy-one dollars. "
         "Booking under Ricky Smith, shall I go ahead?")
PHONE_Q = "Sorry, I do need your phone number. Would you like to use the number you're calling from, ending in 3, 3, 7, 4?"
ARGS = {"customer_name": "Ricky Smith", "starts_at": "2026-10-14T13:00:00Z", "stops_at": "2026-10-14T22:00:00Z",
        "items": [{"product_id": "p", "quantity": 1}]}


def _run(s, args, monkeypatch, seen=None):
    async def fake_create(client, **kw):
        if seen is not None:
            seen.append(kw["customer"])
        return {"order_id": "o"}

    monkeypatch.setattr(config, "BOOKING_CONFIRM_GUARD_ENABLED", True)
    monkeypatch.setattr(guide_client, "BooqableClient", lambda: object())
    monkeypatch.setattr(guide_client.reservations, "create_reservation", fake_create)
    s.location_cache = {"id": "loc"}
    return asyncio.run(guide_client._run_reservation_tool("createReservation", dict(args), s))


def _session(prev, user, phone="+15550003374"):
    s = GuideSession(caller_phone=phone)
    s.prev_round_text, s.turn_user_text = prev, user
    return s


# --- A1: calling number for new callers -----------------------------------------

def test_new_caller_gets_calling_number(monkeypatch):
    seen = []
    s = _session(RECAP, "Yes.")
    assert s.known_customer is None
    assert _run(s, ARGS, monkeypatch, seen) == {"order_id": "o"}
    assert seen[0]["phone"] == "+15550003374"


def test_explicit_other_number_kept(monkeypatch):
    seen = []
    _run(_session(RECAP, "Yes."), {**ARGS, "customer_phone": "+15550001111"}, monkeypatch, seen)
    assert seen[0]["phone"] == "+15550001111"


def test_no_contact_at_all_is_guided_not_raised(monkeypatch):
    out = _run(_session(RECAP, "Yes.", phone=None), ARGS, monkeypatch)
    assert out["booked"] is False and "right after they answer" in out["error"] and "no new recap" in out["error"]


# --- A2: recap yes survives a phone/email side question ---------------------------

def test_recap_yes_carries_over_phone_question(monkeypatch):
    s = _session(RECAP, "Yes.", phone=None)
    assert _run(s, ARGS, monkeypatch)["booked"] is False      # no contact -> asks for it
    s.prev_round_text, s.turn_user_text = PHONE_Q, "Yes."
    s.caller_phone = "+15550003374"
    assert _run(s, ARGS, monkeypatch) == {"order_id": "o"}    # no second recap


def test_recap_yes_carries_over_email_question_with_digits_answer(monkeypatch):
    s = _session(RECAP, "Yes.")
    s.recap_yes_key = guide_client._booking_key(ARGS)
    s.prev_round_text, s.turn_user_text = "What's the best phone number to reach you?", "404 555 0199"
    assert _run(s, {**ARGS, "customer_phone": "4045550199"}, monkeypatch) == {"order_id": "o"}


def test_changed_details_need_new_recap(monkeypatch):
    s = _session(RECAP, "Yes.")
    s.recap_yes_key = guide_client._booking_key(ARGS)
    s.prev_round_text, s.turn_user_text = PHONE_Q, "Yes."
    out = _run(s, {**ARGS, "starts_at": "2026-10-14T15:00:00Z"}, monkeypatch)
    assert out["booked"] is False and "confirm details" in out["error"]


def test_no_carry_over_after_non_contact_question(monkeypatch):
    s = _session(RECAP, "Yes.")
    s.recap_yes_key = guide_client._booking_key(ARGS)
    s.prev_round_text, s.turn_user_text = "What time would you like to pick it up?", "Yes."
    assert _run(s, ARGS, monkeypatch)["booked"] is False


def test_refusal_tells_guide_to_book_after_answer(monkeypatch):
    out = _run(_session("What time?", "10."), ARGS, monkeypatch)
    assert "call createReservation right after they answer" in out["error"]


# --- A3: no text send in the reply that asks about it -----------------------------

def _turns(monkeypatch, first, second):
    calls = []

    async def fake_turn(client, inp, session, outcome):
        if isinstance(inp, str):
            yield first
            outcome.function_calls.append(("c1", "sendPaymentLink", "{}"))
        else:
            yield second

    async def outputs(outcome, session):
        calls.append([n for _, n, _ in outcome.function_calls])
        return [{"type": "function_call_output", "call_id": "c1", "output": "NOT SENT"}]

    monkeypatch.setattr(guide_client, "_stream_turn", fake_turn)
    monkeypatch.setattr(guide_client, "_tool_outputs", outputs)
    s = GuideSession()

    async def run():
        return [e async for e in guide_client._stream_reply_with_tools(None, "Yes.", s)]

    return asyncio.run(run()), calls


def test_text_offer_question_round_mutes_follow_up(monkeypatch):
    events, calls = _turns(
        monkeypatch,
        "Declare victory. You're booked. Would you like me to text you a booking confirmation?",
        "Declare victory. Would you like me to text it to the number ending in 3374?",
    )
    spoken = "".join(e.text for e in events if isinstance(e, Delta))
    assert "Would you like me to text you" in spoken
    assert "ending in 3374" not in spoken                        # not asked twice
    assert not any(isinstance(e, ToolCallStarted) for e in events)  # no filler after the question
    assert calls == [["sendPaymentLink"]]                        # guard result still fed back


def test_send_without_question_still_runs_normally(monkeypatch):
    events, _ = _turns(monkeypatch, "Declare victory. Sending that.", "Declare victory. Done, it's sent.")
    spoken = "".join(e.text for e in events if isinstance(e, Delta))
    assert "Done, it's sent." in spoken
    assert any(isinstance(e, ToolCallStarted) for e in events)


# --- A4 + instructions / OpenAPI -------------------------------------------------

def test_instructions_calling_from_and_text_offer():
    t = (ROOT / "guide-demo/template/instructions.template.md").read_text(encoding="utf-8")
    assert "\"the one I'm calling from\"" in t and "means yes to the calling number" in t
    assert "book right after they answer (no new recap)" in t
    assert "only call sendPaymentLink in your next reply" in t


def test_openapi_documents_new_caller_number_and_carry_over():
    a = (ROOT / "guide-demo/template/OpenAPI/voice-receptionist.json").read_text(encoding="utf-8")
    b = (ROOT / "guide-demo/tools/reservations-client-tool.json").read_text(encoding="utf-8")
    assert a == b
    assert "known or new caller" in a and "no new recap" in a
    assert "Never call this in the same reply that asks" in a


# --- B: greeting with the business name -------------------------------------------

def test_default_greeting_names_business():
    src = (ROOT / "app/config.py").read_text(encoding="utf-8")  # code default (.env may override)
    assert '"WELCOME_GREETING", "Thanks for calling, {business}! How can I help you today?"' in src
    tpl = "Thanks for calling, {business}! How can I help you today?"
    assert fill_business(tpl, name="Atlanta Bikes") == \
        "Thanks for calling, Atlanta Bikes! How can I help you today?"
    assert fill_business(tpl, name="") == "Thanks for calling! How can I help you today?"
    assert fill_business("Hello there!", name="Atlanta Bikes") == "Hello there!"


def test_published_greeting_template_filled(monkeypatch):
    monkeypatch.setattr(guide_client, "BooqableClient", lambda: object())
    from app import business_hours
    monkeypatch.setattr(business_hours, "business_name", lambda: "Atlanta Bikes")
    monkeypatch.setattr(config, "WELCOME_GREETING", "Thanks for calling, {business}! How can I help you today?")
    import app.guide_publish.publisher as pub
    monkeypatch.setattr(pub, "latest_succeeded", lambda s: None)
    assert main._published_greeting() == "Thanks for calling, Atlanta Bikes! How can I help you today?"


# --- 22:35 review: no "closed for today" for a named future day; pause in the greeting ---

def test_fill_business_drops_comma_without_name():
    assert fill_business("Thanks for calling, {business}! How can I help you today?", name="") == \
        "Thanks for calling! How can I help you today?"


def test_now_note_after_hours_limits_closed_mention():
    from datetime import datetime
    from app import business_hours
    tz = business_hours._tz()
    hours = [{"day": d, "open": "09:00", "close": "18:00", "closed": False} for d in range(7)]
    note = business_hours.now_note(datetime(2026, 10, 13, 22, 36, tzinfo=tz), hours)
    assert "closed for today" in note
    assert "Only mention this if the caller wants today or right now, or names no day" in note
    assert "go straight to that day" in note
    open_note = business_hours.now_note(datetime(2026, 10, 13, 12, 0, tzinfo=tz), hours)
    assert "Only mention" not in open_note


def test_instructions_named_day_goes_straight_to_it():
    t = (ROOT / "guide-demo/template/instructions.template.md").read_text(encoding="utf-8")
    assert "Mention that the shop is closed only when the caller asks for today or right now, or names no day" in t
    assert "don't mention today at all - go straight to that day" in t
