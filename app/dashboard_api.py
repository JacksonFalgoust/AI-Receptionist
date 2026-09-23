"""GET /api/dashboard/overview, GET /api/dashboard/activity, GET
/api/dashboard/escalations, GET /api/dashboard/escalations/count --
frontend/src/services/dashboardService.ts's httpDashboardService, made
real (E6 dashboard slice).

Two deliberate placeholders, not bugs: Escalation `status` is always
"new" and `assignedTo` is always null -- there is no persisted escalation
lifecycle yet, and no UI action anywhere ever changes either value.
ActivityEvent `status` only ever takes the values a real
ConversationAction row can have (success/error/pending) -- the mock's
`info`/`escalated` activity statuses have no real event to derive from
today. See docs/superpowers/specs/2026-09-22-e6-dashboard-design.md.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import auth, config, dashboard_store, models
from .db import get_db

router = APIRouter()

DateRangePreset = Literal["today", "7d", "30d", "custom"]


class KpiOut(BaseModel):
    id: str
    label: str
    value: int


class OverviewOut(BaseModel):
    kpis: list[KpiOut]


def _to_iso(value: datetime) -> str:
    return value.isoformat() + "Z"


def _parse_dt(value: str | None, param_name: str) -> datetime | None:
    """Parses a `from`/`to` query param, raising a 422 (not FastAPI's
    default unhandled-500) on a malformed value. Duplicated from
    app/conversations_api.py rather than imported -- this codebase's
    convention (see _to_iso in conversations_api.py/knowledge_api.py/
    workflow_api.py) is each *_api.py module owns its own small request
    helpers rather than cross-importing another module's private ones."""
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.rstrip("Z"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid {param_name}: {value!r}") from exc


def _resolve_range(
    preset: DateRangePreset | None, from_: str | None, to: str | None
) -> tuple[datetime | None, datetime | None]:
    parsed_from = _parse_dt(from_, "from")
    parsed_to = _parse_dt(to, "to")
    return dashboard_store.range_bounds(preset, parsed_from, parsed_to)


@router.get("/api/dashboard/overview", response_model=OverviewOut)
def get_overview(
    preset: DateRangePreset | None = None,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    db: Session = Depends(get_db),
    _auth: models.AuthSession = Depends(auth.require_auth),
) -> OverviewOut:
    range_from, range_to = _resolve_range(preset, from_, to)
    kpis = dashboard_store.get_overview_kpis(db, range_from, range_to)
    return OverviewOut(kpis=[KpiOut(**kpi) for kpi in kpis])


class ActivityEventOut(BaseModel):
    # ActivityEvent extends TenantScoped (frontend/src/types/common.ts) --
    # organizationId is required, locationId is optional but included
    # explicitly (None), matching ConversationOut's own TenantScoped fields
    # in app/conversations_api.py.
    id: str
    organizationId: str
    locationId: str | None = None
    at: str
    title: str
    customerRef: str | None = None
    channel: str | None = None
    system: str | None = None
    status: str
    conversationId: str | None = None


def _activity_out(action: models.ConversationAction) -> ActivityEventOut:
    conversation = action.conversation
    return ActivityEventOut(
        id=action.id,
        organizationId=conversation.organization_id if conversation else config.DEFAULT_ORGANIZATION_ID,
        locationId=None,
        at=_to_iso(action.at),
        title=action.action,
        customerRef=conversation.customer_name if conversation else None,
        channel=conversation.channel if conversation else None,
        system=action.system,
        status=action.status,
        conversationId=action.conversation_id,
    )


@router.get("/api/dashboard/activity", response_model=list[ActivityEventOut])
def get_activity(
    preset: DateRangePreset | None = None,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    limit: int = Query(default=8, ge=1, le=100),
    db: Session = Depends(get_db),
    _auth: models.AuthSession = Depends(auth.require_auth),
) -> list[ActivityEventOut]:
    range_from, range_to = _resolve_range(preset, from_, to)
    rows = dashboard_store.list_recent_activity(db, range_from, range_to, limit)
    return [_activity_out(row) for row in rows]


class EscalationOut(BaseModel):
    # Escalation extends TenantScoped (frontend/src/types/common.ts) --
    # same organizationId/locationId convention as ActivityEventOut above.
    id: str
    organizationId: str
    locationId: str | None = None
    conversationId: str | None = None
    customerName: str
    reason: str
    assignedTo: str | None = None
    status: str
    createdAt: str


def _escalation_out(conversation: models.Conversation) -> EscalationOut:
    return EscalationOut(
        id=conversation.id,
        organizationId=conversation.organization_id,
        locationId=None,
        conversationId=conversation.id,
        customerName=conversation.customer_name or "Unknown caller",
        reason=conversation.intent or "Escalated during the call",
        assignedTo=None,
        status="new",
        createdAt=_to_iso(conversation.started_at),
    )


@router.get("/api/dashboard/escalations", response_model=list[EscalationOut])
def get_escalations(
    preset: DateRangePreset | None = None,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    limit: int = Query(default=8, ge=1, le=100),
    db: Session = Depends(get_db),
    _auth: models.AuthSession = Depends(auth.require_auth),
) -> list[EscalationOut]:
    range_from, range_to = _resolve_range(preset, from_, to)
    rows = dashboard_store.list_recent_escalations(db, range_from, range_to, limit)
    return [_escalation_out(row) for row in rows]


@router.get("/api/dashboard/escalations/count", response_model=int)
def get_escalations_count(
    preset: DateRangePreset | None = None,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    db: Session = Depends(get_db),
    _auth: models.AuthSession = Depends(auth.require_auth),
) -> int:
    range_from, range_to = _resolve_range(preset, from_, to)
    return dashboard_store.count_escalations(db, range_from, range_to)
