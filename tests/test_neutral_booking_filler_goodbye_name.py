"""21:20 review: neutral booking filler, no separate time-confirm, business name in the goodbye."""
from pathlib import Path

from app import business_hours, config, fillers
from app.spoken_text import PhraseJoiner, canned_goodbye_text

ROOT = Path(__file__).resolve().parents[1]


def test_booking_filler_never_claims_booking():
    for phrase in fillers.ACTION_FILLERS["booking"]:
        low = phrase.lower()
        assert "book" not in low and "reserv" not in low, phrase


def test_booking_and_message_pools_are_neutral():
    assert set(fillers.ACTION_FILLERS["booking"]) == {"One moment.", "Just a moment.", "Bear with me one second."}


def test_goodbye_default_names_business_spoken_form():
    text = canned_goodbye_text(name="Atlanta Bikes")
    assert text == "You're welcome! Thanks for calling Atlanta Bikes, and have a great day. Goodbye!"


def test_goodbye_without_name_drops_placeholder():
    assert canned_goodbye_text(name="") == "You're welcome! Thanks for calling, and have a great day. Goodbye!"


def test_goodbye_custom_template_without_placeholder_unchanged():
    assert canned_goodbye_text(template="Bye now!", name="Atlanta Bikes") == "Bye now!"


def test_goodbye_uses_published_or_default_name(monkeypatch):
    monkeypatch.setattr(business_hours, "business_name", lambda: "Atlanta Bikes")
    assert "Atlanta Bikes" in canned_goodbye_text()


def test_business_name_falls_back_to_default(monkeypatch):
    monkeypatch.setattr(business_hours, "_published_name", lambda: None)
    business_hours._NAME_CACHE.update({"at": 0.0, "name": None})
    assert business_hours.business_name() == config.DEFAULT_BUSINESS_PROFILE["name"]
    business_hours._NAME_CACHE.update({"at": 0.0, "name": None})


def test_goodbye_name_stays_whole_through_joiner():
    j = PhraseJoiner(config.SPOKEN_JOIN_PHRASES)
    text = canned_goodbye_text(name="Atlanta Bikes")
    assert j.feed(text) + j.flush() == text


def test_instructions_skip_separate_time_confirm():
    s = (ROOT / "guide-demo/template/instructions.template.md").read_text(encoding="utf-8")
    assert 'do NOT ask a separate "just to confirm the time" question' in s
    assert "only when something is actually ambiguous" in s
    assert "Booking under" in s and "shall I go ahead?" in s


def test_demo_business_is_atlanta_bikes():
    assert config.DEFAULT_BUSINESS_PROFILE["name"] == "Atlanta Bikes"
    assert config.DEFAULT_IDENTITY["name"] == "Atlanta Bikes Receptionist"
    assert config.SPOKEN_NAME_ALIASES == {}
    assert "Atlanta Bikes" in config.SPOKEN_JOIN_PHRASES
    blob = repr(config.DEFAULT_BUSINESS_PROFILE) + repr(config.DEFAULT_IDENTITY) + repr(config.DEFAULT_KNOWLEDGE_ITEMS)
    assert "peachtree" not in blob.lower() and "pedals" not in blob.lower()
    assert "Atlanta Bikes is located" in blob


def test_sms_names_business():
    from app import payments

    assert "your reservation with Atlanta Bikes is confirmed" in payments.confirmation_sms("Eric", 57, "https://x/pay", "Atlanta Bikes")


def test_template_has_no_hardcoded_business_name():
    s = (ROOT / "guide-demo/template/instructions.template.md").read_text(encoding="utf-8")
    assert "Peachtree" not in s and "Atlanta Bikes" not in s
