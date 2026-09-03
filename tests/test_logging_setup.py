import logging

import pytest

from app import config, logging_setup


@pytest.fixture(autouse=True)
def clean_root_handlers():
    """logging is global state -- a handler added in one test would leak into
    every other test's log calls (and pytest's own captured output) if not
    removed afterward."""
    root = logging.getLogger()
    before = list(root.handlers)
    yield
    for handler in list(root.handlers):
        if handler not in before:
            handler.close()
            root.removeHandler(handler)


def test_adds_a_rotating_file_handler_when_log_file_is_set(tmp_path, monkeypatch):
    # Nested, not-yet-existing directory: the handler must create it.
    log_path = tmp_path / "nested" / "app.log"
    monkeypatch.setattr(config, "LOG_FILE", str(log_path))
    monkeypatch.setattr(config, "LOG_MAX_BYTES", 1_000_000)
    monkeypatch.setattr(config, "LOG_BACKUP_COUNT", 2)

    logging_setup.configure_file_logging()
    logging.getLogger("voice_receptionist").warning("hello from a test")
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert log_path.exists()
    assert "hello from a test" in log_path.read_text()


def test_does_nothing_when_log_file_is_unset(monkeypatch):
    monkeypatch.setattr(config, "LOG_FILE", "")
    root = logging.getLogger()
    before = len(root.handlers)

    logging_setup.configure_file_logging()

    assert len(root.handlers) == before
