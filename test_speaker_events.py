import speaker_events


def test_info_style_agent_started():
    msg = {"type": "info", "name": "agentSpeaking", "status": "started"}
    assert speaker_events.classify(msg) == "agent-start"


def test_info_style_agent_stopped():
    msg = {"type": "info", "name": "agentSpeaking", "status": "stopped"}
    assert speaker_events.classify(msg) == "agent-stop"


def test_hyphenated_event_name():
    msg = {"type": "speaker-event", "name": "agent-speaking-stopped"}
    assert speaker_events.classify(msg) == "agent-stop"


def test_camel_case_combined_name():
    msg = {"type": "agentSpeakingEnded"}
    assert speaker_events.classify(msg) == "agent-stop"


def test_client_speaking_started():
    msg = {"type": "info", "name": "clientSpeaking", "status": "started"}
    assert speaker_events.classify(msg) == "client-start"


def test_direction_nested_in_data():
    msg = {"type": "info", "data": {"event": "agentSpeaking", "state": "finished"}}
    assert speaker_events.classify(msg) == "agent-stop"


def test_stop_wins_over_incidental_start_mention():
    # A stop notification may reference when the speech started; it must
    # still classify as a stop.
    msg = {"type": "info", "name": "agentSpeaking", "status": "stopped", "startedAt": "then"}
    assert speaker_events.classify(msg) == "agent-stop"


def test_agent_event_without_direction_is_unknown():
    msg = {"type": "info", "name": "agentSpeaking"}
    assert speaker_events.classify(msg) == "agent-unknown"


def test_live_wire_shape_value_on_off():
    # The exact payloads Twilio actually sends on real calls (observed live):
    # direction is a bare on/off "value", not a start/stop word.
    assert speaker_events.classify({"type": "info", "name": "agentSpeaking", "value": "on"}) == "agent-start"
    assert speaker_events.classify({"type": "info", "name": "agentSpeaking", "value": "off"}) == "agent-stop"
    assert speaker_events.classify({"type": "info", "name": "clientSpeaking", "value": "on"}) == "client-start"
    assert speaker_events.classify({"type": "info", "name": "clientSpeaking", "value": "off"}) == "client-stop"


def test_on_matched_exactly_not_as_substring():
    # "conversation" contains "on"; it must not read as a start signal.
    msg = {"type": "info", "name": "agentSpeaking", "source": "conversation"}
    assert speaker_events.classify(msg) == "agent-unknown"


def test_unrelated_message_is_none():
    assert speaker_events.classify({"type": "prompt", "voicePrompt": "hello there"}) is None


def test_setup_message_is_none():
    assert speaker_events.classify({"type": "setup", "callSid": "CA123"}) is None


def test_non_dict_is_none():
    assert speaker_events.classify("agentSpeaking stopped") is None
