"""Per-action filler phrases (booking / message / lookup), no back-to-back repeats."""
from app import config, fillers


def test_action_classification():
    assert fillers.action_for_tools(["createReservation"]) == "booking"
    assert fillers.action_for_tools(["sendPaymentLink"]) == "message"
    assert fillers.action_for_tools(["listCatalog"]) == "lookup"
    assert fillers.action_for_tools(["checkAvailability"]) == "lookup"
    assert fillers.action_for_tools(["get_caller_phone_number"]) is None  # cached lookup, no filler
    assert fillers.action_for_tools(["getOrder"]) == "lookup"
    assert fillers.action_for_tools(["lookupCustomerByEmail"]) == "lookup"
    assert fillers.action_for_tools(["endCall"]) is None
    assert fillers.action_for_tools(["createReservation", "sendPaymentLink"]) == "message"


def test_booking_and_sms_never_say_look_up():
    for _ in range(50):
        for name in ("createReservation", "sendPaymentLink"):
            p = fillers.pick_for_tools([name], config.FILLER_PHRASES)
            assert "look" not in p.lower() and "pull" not in p.lower()
            assert p in fillers.ACTION_FILLERS[fillers.action_for_tools([name])]


def test_end_call_gets_no_filler():
    assert fillers.pick_for_tools(["endCall"], config.FILLER_PHRASES) is None
    assert fillers.pick_for_tools(["endCall"], ["X"], use_action_pools=False) is None


def test_no_back_to_back_repeat():
    last = None
    for _ in range(200):
        p = fillers.pick_for_tools(["listCatalog"], config.FILLER_PHRASES, last)
        assert p != last
        last = p


def test_custom_override_pool_is_honoured():
    assert fillers.pick_for_tools(["createReservation"], ["Hm."], use_action_pools=False) == "Hm."


def test_single_phrase_pool_still_returns_it():
    assert fillers.pick(["Hm."], avoid="Hm.") == "Hm."


def test_fallback_when_no_tool_names():
    assert fillers.pick_for_tools((), ["X", "Y"], "X") == "Y"


def test_default_pool_has_no_look_that_up():
    assert not any(
        "look that up" in p.lower() or "pull that up" in p.lower()
        for p in config._DEFAULT_FILLER_PHRASES
    )
