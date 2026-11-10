"""FastAPI application for the voice receptionist: creates the app, runs
database setup on startup, and registers every router. The call flow lives
in app/calls/ -- twiml.py (POST /twiml) and relay.py (WS /ws, whose module
docstring describes the whole call flow)."""

import asyncio
import contextlib
import logging

from fastapi import FastAPI

from app.booking.api import router as reservations_router
from app.calls.relay import router as relay_router
from app.calls.twiml import router as twiml_router
from app.console.auth.api import router as auth_router
from app.console.concierge.api import router as concierge_router
from app.console.conversations.api import router as conversations_router
from app.console.bookings.api import router as bookings_router
from app.console.dashboard.api import router as dashboard_router
from app.console.knowledge.api import router as knowledge_router
from app.console.workflows.api import router as workflow_router
from app import config
from app.db import init_db
from app.guide.session import GuideSession
from app.guide.streaming import stream_reply

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s:%(name)s:%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("voice_receptionist")


async def _warm_up_guide() -> None:
    """One throwaway GuideAnts turn at startup so the first real call's first
    reply isn't a cold start (4.3s seen on the first call after a reboot).
    Never raises; failures are only logged."""
    try:
        t0 = asyncio.get_event_loop().time()
        async for _ in stream_reply("(system warm-up, no caller) Say OK.", GuideSession()):
            pass
        logger.info("GuideAnts warm-up done in %.2fs", asyncio.get_event_loop().time() - t0)
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("GuideAnts warm-up failed: %s", type(exc).__name__)


@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI):
    # E6 slice 1: creates the SQLite tables (conversations, auth_sessions,
    # ...) on startup if they don't already exist -- see app/db.py's
    # init_db(). FastAPI's docs recommend a lifespan context manager over
    # the deprecated @app.on_event("startup") handler for fastapi>=0.115
    # (confirmed via find-docs against the pinned version).
    init_db()
    warmup = asyncio.create_task(_warm_up_guide()) if config.GUIDE_WARMUP_ON_STARTUP else None
    yield
    if warmup and not warmup.done():
        warmup.cancel()


app = FastAPI(lifespan=_lifespan)
app.include_router(reservations_router)
app.include_router(auth_router)
app.include_router(concierge_router)
app.include_router(conversations_router)
app.include_router(bookings_router)
app.include_router(dashboard_router)
app.include_router(knowledge_router)
app.include_router(workflow_router)
app.include_router(twiml_router)
app.include_router(relay_router)
