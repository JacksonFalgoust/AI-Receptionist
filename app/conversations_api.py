"""GET /api/conversations, GET /api/conversations/{id}, GET
/api/conversations/filter-options -- frontend/src/services/
conversationService.ts's httpConversationService, made real for the first
time. See docs/superpowers/specs/2026-09-14-e6-conversation-history-design.md,
section 4.

/api/conversations/filter-options must stay declared before
/api/conversations/{conversation_id} below -- FastAPI matches routes in
declaration order, and the parameterized route would otherwise swallow
"filter-options" as a conversation id.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import auth, conversation_store, models
from .db import get_db

router = APIRouter()


class ConversationOut(BaseModel):
    id: str
    organizationId: str
    locationId: str | None = None
    customerName: str | None = None
    customerPhone: str | None = None
    channel: str
    startedAt: str
    endedAt: str | None = None
    durationSeconds: int | None = None
    intent: str | None = None
    outcome: str
    escalated: bool
    summary: str | None = None
    assignedEmployee: str | None = None
    escalationStatus: str | None = None


class MessageOut(BaseModel):
    id: str
    conversationId: str
    speaker: str
    text: str
    at: str


class ActionOut(BaseModel):
    id: str
    conversationId: str
    action: str
    system: str
    at: str
    result: str
    status: str
    details: dict | None = None


class ConversationDetailOut(BaseModel):
    conversation: ConversationOut
    messages: list[MessageOut]
    actions: list[ActionOut]


class PaginatedConversations(BaseModel):
    items: list[ConversationOut]
    page: int
    pageSize: int
    total: int


class FilterOptionsOut(BaseModel):
    intents: list[str]
    locations: list[dict]
    employees: list[str]


def _to_iso(value: datetime | None) -> str | None:
    return value.isoformat() + "Z" if value else None


def _conversation_out(conversation: models.Conversation) -> ConversationOut:
    return ConversationOut(
        id=conversation.id,
        organizationId=conversation.organization_id,
        locationId=None,
        customerName=conversation.customer_name,
        customerPhone=conversation.customer_phone,
        channel=conversation.channel,
        startedAt=_to_iso(conversation.started_at),
        endedAt=_to_iso(conversation.ended_at),
        durationSeconds=conversation.duration_seconds,
        intent=conversation.intent,
        outcome=conversation.outcome,
        escalated=conversation.escalated,
        summary=conversation.summary,
        assignedEmployee=conversation.assigned_employee,
        # The Escalations feed is a separate, still-mocked E6 slice -- see
        # the design spec's scope cuts.
        escalationStatus=None,
    )


@router.get("/api/conversations", response_model=PaginatedConversations)
def list_conversations(
    search: str | None = None,
    channel: str | None = None,
    intent: str | None = None,
    outcome: str | None = None,
    escalated: bool | None = None,
    locationId: str | None = None,
    assignedEmployee: str | None = None,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    page: int = 1,
    pageSize: int = 20,
    db: Session = Depends(get_db),
    _auth: models.AuthSession = Depends(auth.require_auth),
) -> PaginatedConversations:
    rows, total = conversation_store.list_conversations(
        db,
        search=search,
        channel=channel,
        intent=intent,
        outcome=outcome,
        escalated=escalated,
        location_id=locationId,
        assigned_employee=assignedEmployee,
        date_from=datetime.fromisoformat(from_) if from_ else None,
        date_to=datetime.fromisoformat(to) if to else None,
        page=page,
        page_size=pageSize,
    )
    return PaginatedConversations(
        items=[_conversation_out(row) for row in rows],
        page=page,
        pageSize=pageSize,
        total=total,
    )


@router.get("/api/conversations/filter-options", response_model=FilterOptionsOut)
def filter_options(
    db: Session = Depends(get_db), _auth: models.AuthSession = Depends(auth.require_auth)
) -> FilterOptionsOut:
    return FilterOptionsOut(
        intents=conversation_store.list_distinct_intents(db),
        # No multi-location model or live transfer to a human yet -- see
        # the design spec's scope cuts.
        locations=[],
        employees=[],
    )


@router.get("/api/conversations/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    _auth: models.AuthSession = Depends(auth.require_auth),
) -> ConversationDetailOut:
    conversation = conversation_store.get_conversation(db, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return ConversationDetailOut(
        conversation=_conversation_out(conversation),
        messages=[
            MessageOut(
                id=m.id,
                conversationId=m.conversation_id,
                speaker=m.speaker,
                text=m.text,
                at=_to_iso(m.at),
            )
            for m in conversation.messages
        ],
        actions=[
            ActionOut(
                id=a.id,
                conversationId=a.conversation_id,
                action=a.action,
                system=a.system,
                at=_to_iso(a.at),
                result=a.result,
                status=a.status,
                details=a.details,
            )
            for a in conversation.actions
        ],
    )
