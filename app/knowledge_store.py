"""SQLAlchemy-backed CRUD for console knowledge items (E6 slice 2). Called
only by app/knowledge_api.py. Same conventions as app/conversation_store.py:
every function takes a Session and none commit, so the caller owns the
transaction boundary.

No longer console-only: a publish renders these rows into the guide bundle
and GuideAnts' import replaces the live vector store wholesale, so a row
edited or deleted here changes the next call. See
docs/superpowers/specs/2026-09-18-guide-publish-pipeline-design.md.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from . import config, models


def _resolve_status(status: str) -> str:
    """The frontend asks for 'processing' only for a fresh document upload.
    With no ingestion pipeline nothing would ever move it on, so record the
    honest state instead: a record exists, its content hasn't been read.
    Remove this once real ingestion exists (spec, "Future" route 1 step 4)."""
    return "needs_review" if status == "processing" else status


def _scoped():
    return select(models.KnowledgeItem).where(
        models.KnowledgeItem.organization_id == config.DEFAULT_ORGANIZATION_ID
    )


def seed_default_items(db: Session) -> None:
    """Populates an empty table from config.DEFAULT_KNOWLEDGE_ITEMS.

    Seed-on-first-read, exactly as app/configuration_store.py does and for
    the same reason: app/db.py's create_all() is the real runtime schema
    path, so a migration's data step would never run for most checkouts.

    This runs on the publish path too (app/guide_publish/publisher.py), not
    only when the console's Knowledge page is opened. A publish replaces the
    live guide's vector store wholesale, so publishing from an empty table
    would DELETE the shop's entire policy knowledge -- and an admin who goes
    straight from Configuration to Publish never touches list_items().

    No commit: the caller owns the transaction, as everywhere else here.
    """
    if db.scalar(select(func.count()).select_from(_scoped().subquery())):
        return
    for seed in config.DEFAULT_KNOWLEDGE_ITEMS:
        db.add(
            models.KnowledgeItem(
                id=seed["id"],
                organization_id=config.DEFAULT_ORGANIZATION_ID,
                title=seed["title"],
                type=seed["type"],
                status="active",
                source="Manual entry",
                category=seed.get("category"),
                content=seed["content"],
                tags=[],
                updated_at=datetime.utcnow(),
            )
        )
    db.flush()


def list_items(
    db: Session,
    *,
    search: str | None = None,
    type: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[models.KnowledgeItem], int]:
    """Most recently updated first, matching the mock service's
    sortByDesc(updatedAt)."""
    seed_default_items(db)
    query = _scoped()
    if type:
        query = query.where(models.KnowledgeItem.type == type)
    if status:
        query = query.where(models.KnowledgeItem.status == status)
    if search:
        like = f"%{search}%"
        query = query.where(
            models.KnowledgeItem.title.ilike(like)
            | models.KnowledgeItem.content.ilike(like)
            | models.KnowledgeItem.category.ilike(like)
            | models.KnowledgeItem.source.ilike(like)
            # tags is a JSON array; matching its serialized text is enough
            # for a substring search over tag values.
            | cast(models.KnowledgeItem.tags, String).ilike(like)
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    page = max(page, 1)
    page_size = max(page_size, 1)
    rows = list(
        db.scalars(
            query.order_by(models.KnowledgeItem.updated_at.desc(), models.KnowledgeItem.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return rows, total


def get_item(db: Session, item_id: str) -> models.KnowledgeItem | None:
    return db.scalar(_scoped().where(models.KnowledgeItem.id == item_id))


def create_item(
    db: Session,
    *,
    title: str,
    type: str,
    status: str | None = None,
    source: str | None = None,
    category: str | None = None,
    content: str | None = None,
    tags: list[str] | None = None,
    effective_date: datetime | None = None,
    expiration_date: datetime | None = None,
) -> models.KnowledgeItem:
    item = models.KnowledgeItem(
        organization_id=config.DEFAULT_ORGANIZATION_ID,
        title=title,
        type=type,
        status=_resolve_status(status or "active"),
        source=source or "Manual entry",
        category=category,
        content=content,
        tags=list(tags or []),
        effective_date=effective_date,
        expiration_date=expiration_date,
        updated_at=datetime.utcnow(),
    )
    db.add(item)
    db.flush()
    return item


def update_item(
    db: Session, item: models.KnowledgeItem, patch: dict[str, Any]
) -> models.KnowledgeItem:
    """Applies only the keys present in `patch` (snake_case attribute names)."""
    for key, value in patch.items():
        if key == "status":
            value = _resolve_status(value)
        setattr(item, key, value)
    item.updated_at = datetime.utcnow()
    db.flush()
    return item


def delete_item(db: Session, item: models.KnowledgeItem) -> None:
    db.delete(item)
    db.flush()
