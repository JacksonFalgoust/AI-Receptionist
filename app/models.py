"""SQLAlchemy models backing conversation history (E6 slice 1), console
knowledge items (E6 slice 2), and console workflows (E6 slice 3). Field names
are snake_case; app/conversations_api.py translates to the frontend's exact
camelCase JSON shape (frontend/src/types/conversation.ts) -- these models don't
know about that shape themselves.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON, Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    customer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    channel: Mapped[str] = mapped_column(String, nullable=False, default="voice")
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    intent: Mapped[str | None] = mapped_column(String, nullable=True)
    outcome: Mapped[str] = mapped_column(String, nullable=False, default="completed")
    escalated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Always null in v1 -- no live transfer to a human exists yet.
    assigned_employee: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.at",
    )
    actions: Mapped[list["ConversationAction"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationAction.at",
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id"), nullable=False, index=True
    )
    speaker: Mapped[str] = mapped_column(String, nullable=False)  # "customer" | "concierge"
    text: Mapped[str] = mapped_column(Text, nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class ConversationAction(Base):
    __tablename__ = "conversation_actions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String, nullable=False)
    system: Mapped[str] = mapped_column(String, nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)  # "success" | "error" | "pending"
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="actions")


class KnowledgeItem(Base):
    """A console-managed knowledge item (frontend/src/types/knowledge.ts).
    Published: app/guide_publish/render.py renders every publishable row
    into the guide bundle, and GuideAnts' import replaces the live vector
    store wholesale -- see
    docs/superpowers/specs/2026-09-18-guide-publish-pipeline-design.md."""

    __tablename__ = "knowledge_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # KnowledgeType
    status: Mapped[str] = mapped_column(String, nullable=False)  # KnowledgeStatus
    # "Manual entry", an uploaded document's filename, or a URL.
    source: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    effective_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expiration_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class Workflow(Base):
    """A console-managed workflow (frontend/src/types/workflow.ts).
    Console-only: publishing has no effect on live calls -- nothing in
    app/ reads this table today. See
    docs/superpowers/specs/2026-09-17-e6-workflows-design.md, "Future"."""

    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)  # WorkflowStatus
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # The whole WorkflowStep[] array, replaced wholesale on every save --
    # never merged field-by-field. See app/workflow_store.py.
    steps: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    # Always 0 in this slice -- no execution engine exists yet.
    execution_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class AuthSession(Base):
    """A logged-in session's bearer token -- the frontend AuthProvider's
    Session (frontend/src/types/user.ts), stored server-side so logout and
    expiry are enforced rather than only client-trusted. Unrelated to
    GuideAnts' own conversation-continuation id (app/guide_client.py's
    GuideSession.conversation_id)."""

    __tablename__ = "auth_sessions"

    token: Mapped[str] = mapped_column(String, primary_key=True)
    user_email: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class ConciergeConfiguration(Base):
    """The console's Configuration pages (frontend/src/types/concierge.ts's
    ConciergeConfiguration), and the source of the slot values rendered into
    the published guide's instructions.

    Three JSON columns rather than flat fields because saveDraft merges
    section-wise: a PATCH carrying `identity` alone must not wipe
    `business_profile`. A section present in a patch replaces that column
    wholesale -- never a field-by-field merge, the same rule
    models.Workflow.steps follows."""

    __tablename__ = "concierge_configuration"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String, nullable=False, unique=True, index=True
    )
    business_profile: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    identity: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    terminology: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Set by any PATCH; cleared ONLY by a confirmed successful publish.
    has_unpublished_changes: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    last_published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class GuidePublication(Base):
    """One attempt to push a rendered bundle to the live GuideAnts guide.

    Every publish is a full declarative replacement of the guide, so this
    history is the only record of what was sent -- `bundle_bytes` is kept so
    a bad publish can be rolled back by re-pushing an earlier one."""

    __tablename__ = "guide_publications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    published_by: Mapped[str] = mapped_column(String, nullable=False)
    # sha256 over the canonical file map -- drives no-op detection and diffs.
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    instructions_text: Mapped[str] = mapped_column(Text, nullable=False)
    # The three config sections as published. app/main.py's _greeting_for()
    # reads the latest succeeded row's copy, which is what keeps draft edits
    # from reaching callers before Publish.
    published_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    knowledge_item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bundle_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)  # pending|succeeded|failed
    # GuideAnts' ImportGuideResultDto warnings -- surfaced, never swallowed.
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
