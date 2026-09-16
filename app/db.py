"""SQLite persistence for conversation history (E6 slice 1). This app was
previously stateless apart from a GuideAnts-side conversation id per call
(see CLAUDE.md); this module is its first durable store.

`init_db()` (called at startup, see app/main.py) creates every table via
`Base.metadata.create_all()` -- this, not Alembic, is the actual runtime
schema-creation path, so a fresh checkout works with zero setup, the same as
every other part of this demo. `create_all()` never stamps `alembic_version`,
so a database created by the running app cannot be cleanly upgraded later via
`alembic upgrade head` (it will fail with "table already exists"). alembic/
(see alembic/versions/0001_initial.py) exists only to give *future* schema
changes a real migration history to build on -- it does not currently
describe a working create_all-to-alembic upgrade path, and nothing in this
app stamps the version table to bridge the two.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from . import config


class Base(DeclarativeBase):
    pass


def _ensure_sqlite_directory(url: str) -> None:
    """sqlite creates the database file itself but not its parent
    directory -- without this, a fresh checkout's default `./data/...`
    path fails on first run."""
    prefix = "sqlite:///"
    if url.startswith(prefix):
        Path(url.removeprefix(prefix)).parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_directory(config.DATABASE_URL)
engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Creates every table declared in app/models.py if it doesn't already
    exist. Safe to call on every startup."""
    from . import models  # noqa: F401 -- import needed to register tables on Base

    Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """One unit of work for non-request callers (e.g. app/call_recording.py).
    Commits on success, rolls back and re-raises on any exception, always
    closes."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency version of session_scope() -- yields without
    committing, so a read-only route never pays for a commit it doesn't
    need; a route that writes calls db.commit() itself."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
