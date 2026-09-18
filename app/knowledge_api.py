"""GET/POST /api/knowledge, GET/PATCH/DELETE /api/knowledge/{id} --
frontend/src/services/knowledgeService.ts's httpKnowledgeService, made real
(E6 slice 2).

CONSOLE-ONLY: these records drive the admin console's Knowledge pages and
nothing else. On a live call the GuideAnts guide answers from its own
vector store (guide-demo/Twillio demo agent/VectorStores/), not this table,
so editing an item here does not change what the concierge says. What has
to change to close that gap: docs/superpowers/specs/
2026-09-16-e6-knowledge-design.md, "Future: syncing to the published guide".
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, StringConstraints, model_validator
from sqlalchemy.orm import Session

from . import auth, knowledge_store, models
from .db import get_db

router = APIRouter()

KnowledgeType = Literal[
    "faq", "policy", "procedure", "product", "service",
    "pricing", "location", "instruction", "document", "url",
]
KnowledgeStatus = Literal["active", "processing", "needs_review", "error", "disabled"]
NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# camelCase request field -> KnowledgeItem attribute, for fields whose names differ.
_FIELD_TO_ATTR = {"effectiveDate": "effective_date", "expirationDate": "expiration_date"}


class KnowledgeItemOut(BaseModel):
    id: str
    organizationId: str
    title: str
    type: str
    status: str
    source: str
    category: str | None = None
    content: str | None = None
    tags: list[str]
    effectiveDate: str | None = None
    expirationDate: str | None = None
    updatedAt: str


class PaginatedKnowledge(BaseModel):
    items: list[KnowledgeItemOut]
    page: int
    pageSize: int
    total: int


class CreateKnowledgeIn(BaseModel):
    title: NonBlankStr
    type: KnowledgeType
    category: str | None = None
    content: str | None = None
    tags: list[str] = Field(default_factory=list)
    effectiveDate: datetime | None = None
    expirationDate: datetime | None = None
    status: KnowledgeStatus | None = None
    source: str | None = None


class KnowledgePatchIn(BaseModel):
    title: NonBlankStr | None = None
    type: KnowledgeType | None = None
    status: KnowledgeStatus | None = None
    source: str | None = None
    category: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    effectiveDate: datetime | None = None
    expirationDate: datetime | None = None

    @model_validator(mode="after")
    def _required_columns_cannot_be_null(self) -> "KnowledgePatchIn":
        # Absent means "leave alone"; an explicit null would violate a
        # NOT NULL column, so reject it here rather than 500 at commit.
        for name in ("title", "type", "status", "tags", "source"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


def _to_iso(value: datetime | None) -> str | None:
    return value.isoformat() + "Z" if value else None


def _naive_utc(value: datetime | None) -> datetime | None:
    """The database stores naive UTC (like the rest of app/models.py);
    incoming ISO strings usually carry a 'Z'."""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _item_out(item: models.KnowledgeItem) -> KnowledgeItemOut:
    return KnowledgeItemOut(
        id=item.id,
        organizationId=item.organization_id,
        title=item.title,
        type=item.type,
        status=item.status,
        source=item.source,
        category=item.category,
        content=item.content,
        tags=list(item.tags or []),
        effectiveDate=_to_iso(item.effective_date),
        expirationDate=_to_iso(item.expiration_date),
        updatedAt=_to_iso(item.updated_at),
    )


def _require_item(db: Session, item_id: str) -> models.KnowledgeItem:
    item = knowledge_store.get_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge item not found")
    return item


@router.get("/api/knowledge", response_model=PaginatedKnowledge)
def list_knowledge(
    search: str | None = None,
    type: KnowledgeType | None = None,
    status_: KnowledgeStatus | None = Query(default=None, alias="status"),
    page: int = 1,
    pageSize: int = 20,
    db: Session = Depends(get_db),
    _auth: models.AuthSession = Depends(auth.require_auth),
) -> PaginatedKnowledge:
    rows, total = knowledge_store.list_items(
        db, search=search, type=type, status=status_, page=page, page_size=pageSize
    )
    return PaginatedKnowledge(
        items=[_item_out(row) for row in rows], page=page, pageSize=pageSize, total=total
    )


@router.get("/api/knowledge/{item_id}", response_model=KnowledgeItemOut)
def get_knowledge(
    item_id: str,
    db: Session = Depends(get_db),
    _auth: models.AuthSession = Depends(auth.require_auth),
) -> KnowledgeItemOut:
    return _item_out(_require_item(db, item_id))


@router.post("/api/knowledge", response_model=KnowledgeItemOut, status_code=status.HTTP_201_CREATED)
def create_knowledge(
    payload: CreateKnowledgeIn,
    db: Session = Depends(get_db),
    _auth: models.AuthSession = Depends(auth.require_auth),
) -> KnowledgeItemOut:
    item = knowledge_store.create_item(
        db,
        title=payload.title,
        type=payload.type,
        status=payload.status,
        source=payload.source,
        category=payload.category,
        content=payload.content,
        tags=payload.tags,
        effective_date=_naive_utc(payload.effectiveDate),
        expiration_date=_naive_utc(payload.expirationDate),
    )
    db.commit()
    return _item_out(item)


@router.patch("/api/knowledge/{item_id}", response_model=KnowledgeItemOut)
def update_knowledge(
    item_id: str,
    payload: KnowledgePatchIn,
    db: Session = Depends(get_db),
    _auth: models.AuthSession = Depends(auth.require_auth),
) -> KnowledgeItemOut:
    item = _require_item(db, item_id)
    patch: dict[str, Any] = {}
    for field, value in payload.model_dump(exclude_unset=True).items():
        attr = _FIELD_TO_ATTR.get(field, field)
        patch[attr] = _naive_utc(value) if attr in _FIELD_TO_ATTR.values() else value
    knowledge_store.update_item(db, item, patch)
    db.commit()
    return _item_out(item)


@router.delete("/api/knowledge/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge(
    item_id: str,
    db: Session = Depends(get_db),
    _auth: models.AuthSession = Depends(auth.require_auth),
) -> None:
    knowledge_store.delete_item(db, _require_item(db, item_id))
    db.commit()
