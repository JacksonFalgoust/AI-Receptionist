"""FastAPI application for the voice receptionist: creates the app, runs
database setup on startup, and registers every router. The call flow lives
in app/calls/ -- twiml.py (POST /twiml) and relay.py (WS /ws, whose module
docstring describes the whole call flow)."""

import contextlib
import logging

from fastapi import FastAPI

from app.booking.api import router as reservations_router
from app.calls.relay import router as relay_router
from app.calls.twiml import router as twiml_router
from app.console.auth.api import router as auth_router
from app.console.concierge.api import router as concierge_router
from app.console.conversations.api import router as conversations_router
from app.console.dashboard.api import router as dashboard_router
from app.console.knowledge.api import router as knowledge_router
from app.console.workflows.api import router as workflow_router
from app.db import init_db

logging.basicConfig(level=logging.INFO)


@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI):
    # E6 slice 1: creates the SQLite tables (conversations, auth_sessions,
    # ...) on startup if they don't already exist -- see app/db.py's
    # init_db(). FastAPI's docs recommend a lifespan context manager over
    # the deprecated @app.on_event("startup") handler for fastapi>=0.115
    # (confirmed via find-docs against the pinned version).
    init_db()
    yield


app = FastAPI(lifespan=_lifespan)
app.include_router(reservations_router)
app.include_router(auth_router)
app.include_router(concierge_router)
app.include_router(conversations_router)
app.include_router(dashboard_router)
app.include_router(knowledge_router)
app.include_router(workflow_router)
app.include_router(twiml_router)
app.include_router(relay_router)
