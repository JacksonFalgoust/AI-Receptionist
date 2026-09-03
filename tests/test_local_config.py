from app import config


def test_local_audio_defaults():
    assert config.GUIDEANTS_TRANSCRIPTION_MODEL == "transcription"
    assert config.GUIDEANTS_SPEECH_MODEL == "speech"
    assert config.GUIDEANTS_SPEECH_VOICE == ""
    assert config.LOCAL_RECORD_SILENCE_SECONDS == 3
    assert config.LOCAL_RECORD_MAX_SECONDS == 30
    assert config.LOCAL_TURN_BUDGET_SECONDS == 11.0
    assert config.LOCAL_FALLBACK_TTS_BUDGET_SECONDS == 3.0
    assert config.LOCAL_RECORDING_FETCH_ATTEMPTS == 5
    assert config.LOCAL_RECORDING_FETCH_DELAY_SECONDS == 0.4
    assert config.LOCAL_SESSION_TTL_SECONDS == 1800.0
    assert config.LOCAL_AUDIO_TTL_SECONDS == 300.0


def test_local_fallback_phrases_are_non_empty_sentences():
    for phrase in (
        config.LOCAL_NO_SPEECH_PHRASE,
        config.LOCAL_ERROR_PHRASE,
        config.LOCAL_TIMEOUT_PHRASE,
    ):
        assert phrase.strip()
        assert phrase.strip().endswith(("?", "."))
