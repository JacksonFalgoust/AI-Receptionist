from app import speech_timing


def test_estimate_seconds_counts_words_at_given_rate():
    assert speech_timing.estimate_seconds("one two three four", words_per_second=2.0) == 2.0


def test_estimate_seconds_empty_text_is_zero():
    assert speech_timing.estimate_seconds("", words_per_second=2.5) == 0.0


def test_estimate_seconds_whitespace_only_is_zero():
    assert speech_timing.estimate_seconds("   ", words_per_second=2.5) == 0.0


def test_estimate_spoken_prefix_partial():
    text = "one two three four five six"
    # 2 seconds at 2 words/second -> 4 words heard
    assert speech_timing.estimate_spoken_prefix(text, 2.0, 2.0) == "one two three four"


def test_estimate_spoken_prefix_nothing_heard_yet():
    text = "one two three"
    assert speech_timing.estimate_spoken_prefix(text, 0.0, 2.5) == ""
    assert speech_timing.estimate_spoken_prefix(text, -1.0, 2.5) == ""
    # 0.1s at 2.5 wps -> int(0.25) == 0 words
    assert speech_timing.estimate_spoken_prefix(text, 0.1, 2.5) == ""


def test_estimate_spoken_prefix_elapsed_covers_everything():
    text = "one two three"
    assert speech_timing.estimate_spoken_prefix(text, 60.0, 2.5) == text


def test_estimate_spoken_prefix_empty_text():
    assert speech_timing.estimate_spoken_prefix("", 5.0, 2.5) == ""
    assert speech_timing.estimate_spoken_prefix("   ", 5.0, 2.5) == ""
