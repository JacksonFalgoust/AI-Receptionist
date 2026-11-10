import pytest

from app import config


@pytest.fixture(autouse=True)
def _no_guide_warmup(monkeypatch):
    # The startup warm-up would hit a real GuideAnts; tests never should.
    monkeypatch.setattr(config, "GUIDE_WARMUP_ON_STARTUP", False)


@pytest.fixture(autouse=True)
def _default_working_sound(monkeypatch):
    # Tests assume the shipped default (chime on), whatever the local .env says.
    monkeypatch.setattr(config, "WORKING_SOUND_ENABLED", True)



@pytest.fixture(autouse=True)
def _time_independent_defaults(monkeypatch):
    # Older tests use fixed dates and fake GuideAnts inputs; the business-hours
    # guard, the per-call "now" note and the bare-greeting skip are switched on
    # explicitly by the tests that cover them (test_hours_email_known_booking.py).
    monkeypatch.setattr(config, "BUSINESS_HOURS_GUARD_ENABLED", False)
    monkeypatch.setattr(config, "NOW_NOTE_ENABLED", False)
    monkeypatch.setattr(config, "IGNORE_FIRST_BARE_GREETING", False)
    monkeypatch.setattr(config, "BOOKING_CONFIRM_GUARD_ENABLED", False)
