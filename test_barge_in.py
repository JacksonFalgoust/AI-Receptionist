import barge_in


def test_is_stop_command_matches_bare_phrase():
    assert barge_in.is_stop_command("stop") is True


def test_is_stop_command_strips_punctuation_and_case():
    assert barge_in.is_stop_command("Stop.") is True


def test_is_stop_command_strips_leading_fillers():
    assert barge_in.is_stop_command("okay stop") is True


def test_is_stop_command_matches_multiword_phrase_prefix():
    assert barge_in.is_stop_command("hold on a second") is True


def test_is_stop_command_matches_phrase_followed_by_more_words():
    assert barge_in.is_stop_command("wait a second") is True


def test_is_stop_command_false_for_unrelated_text():
    assert barge_in.is_stop_command("what time do you close") is False


def test_is_stop_command_false_for_empty_text():
    assert barge_in.is_stop_command("") is False


def test_is_stop_command_checks_extra_phrases():
    assert barge_in.is_stop_command("cancel please", extra_phrases=["cancel"]) is True
    assert barge_in.is_stop_command("cancel please") is False
