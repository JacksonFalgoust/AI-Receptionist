import speech_timing


def test_estimate_seconds_counts_words_at_given_rate():
    assert speech_timing.estimate_seconds("one two three four", words_per_second=2.0) == 2.0


def test_estimate_seconds_empty_text_is_zero():
    assert speech_timing.estimate_seconds("", words_per_second=2.5) == 0.0


def test_estimate_seconds_whitespace_only_is_zero():
    assert speech_timing.estimate_seconds("   ", words_per_second=2.5) == 0.0
