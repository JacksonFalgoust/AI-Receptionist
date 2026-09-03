"""Runs before any test module is collected (pytest loads conftest.py first).

Several test modules import `app.main` (directly, or via TestClient), which
runs `logging_setup.configure_file_logging()` at import time -- same as the
real server. Without this override, a test run's fake tracebacks and
placeholder ids (see tests/test_local_call.py's "recording gone", etc.) land
in the same logs/app.log a real incident is diagnosed from. Set before
app.config's own `load_dotenv()` runs so it wins regardless of what a local
.env sets: dotenv's load_dotenv() does not override an already-set env var.
"""

import os

os.environ["LOG_FILE"] = ""
