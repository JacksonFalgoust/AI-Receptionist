"""Adds a rotating log file alongside this app's console logging.

Without this, an incident is diagnosable only from whatever terminal happens
to be running uvicorn at the time -- gone the moment that scrolls away or the
process restarts. Every module already logs through the standard `logging`
module (see main.py's `logging.basicConfig`), so attaching one more handler
to the root logger here is enough to persist all of it, with no changes
anywhere else.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import config


def configure_file_logging() -> None:
    """Add a RotatingFileHandler for config.LOG_FILE to the root logger.

    A no-op when LOG_FILE is empty -- console logging from
    logging.basicConfig (called separately, before this) is unaffected
    either way. Safe to call more than once only if the caller doesn't mind
    duplicate log lines; main.py calls it exactly once at startup.
    """
    if not config.LOG_FILE:
        return

    path = Path(config.LOG_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        path, maxBytes=config.LOG_MAX_BYTES, backupCount=config.LOG_BACKUP_COUNT
    )
    # Timestamps earn their place here (unlike the console): correlating a
    # local incident against GuideAnts' own server-side logs by wall-clock
    # time is exactly how the last few of these got diagnosed.
    handler.setFormatter(logging.Formatter("%(asctime)s " + logging.BASIC_FORMAT))
    logging.getLogger().addHandler(handler)
