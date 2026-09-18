"""GET/PATCH /api/concierge/configuration, POST .../preview, POST
.../publish, GET /api/concierge/publications, GET /api/concierge/bundle --
the live backing for frontend/src/services/configurationService.ts.

Unlike app/knowledge_api.py and app/workflow_api.py, these records are NOT
console-only: a successful publish rewrites the live GuideAnts guide and
changes what the next caller hears.

Wire shape is camelCase; the models are snake_case. The translation happens
here, the same split app/conversations_api.py uses.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import auth, config, configuration_store, models
from .db import get_db
from .guide_publish import bundle as bundle_module
from .guide_publish import guideants_admin, publisher, template

router = APIRouter(prefix="/api/concierge")

# Wire (camelCase) -> column (snake_case). Only these three are patchable,
# matching the frontend's ConciergeConfigurationPatch.
_SECTIONS = {
    "businessProfile": "business_profile",
    "identity": "identity",
    "terminology": "terminology",
}


class ConfigurationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    businessProfile: dict[str, Any] | None = None
    identity: dict[str, Any] | None = None
    terminology: dict[str, Any] | None = None


def _serialize(row: models.ConciergeConfiguration) -> dict:
    return {
        "organizationId": row.organization_id,
        "businessProfile": row.business_profile,
        "identity": row.identity,
        "terminology": row.terminology,
        "hasUnpublishedChanges": row.has_unpublished_changes,
        "lastPublishedAt": row.last_published_at.isoformat()
        if row.last_published_at
        else None,
    }


def _serialize_publication(row: models.GuidePublication) -> dict:
    return {
        "id": row.id,
        "createdAt": row.created_at.isoformat(),
        "publishedBy": row.published_by,
        "contentHash": row.content_hash,
        "knowledgeItemCount": row.knowledge_item_count,
        "status": row.status,
        "warnings": row.warnings or [],
        "error": row.error,
    }


@router.get("/configuration")
def get_configuration(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[models.AuthSession, Depends(auth.require_auth)],
) -> dict:
    row = configuration_store.get_configuration(db)
    db.commit()  # the first read seeds the row
    return _serialize(row)


@router.patch("/configuration")
def patch_configuration(
    patch: ConfigurationPatch,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[models.AuthSession, Depends(auth.require_auth)],
) -> dict:
    sections = {
        _SECTIONS[key]: value
        for key, value in patch.model_dump(exclude_none=True).items()
    }
    row = configuration_store.get_configuration(db)
    configuration_store.save_draft(db, row, sections)
    db.commit()
    return _serialize(row)


def _render_or_422(db: Session):
    try:
        return publisher.render_preview(db)
    except (ValueError, bundle_module.BundleError, template.SlotError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.post("/configuration/preview")
def preview(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[models.AuthSession, Depends(auth.require_auth)],
) -> dict:
    result = _render_or_422(db)
    db.commit()
    return {
        "instructions": result.instructions,
        "contentHash": result.content_hash,
        "knowledgeItemCount": result.knowledge_item_count,
        "changed": result.changed,
        "previousInstructions": result.previous_instructions,
    }


@router.post("/configuration/publish")
async def publish(
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[models.AuthSession, Depends(auth.require_auth)],
) -> dict:
    if not guideants_admin.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Publishing is not configured: set GUIDEANTS_ADMIN_EMAIL and "
                "GUIDEANTS_ADMIN_PASSWORD. Preview and bundle download still work."
            ),
        )
    _render_or_422(db)  # surface local failures as 422 before attempting a push
    publication = await publisher.publish(db, published_by=session.user_email)
    configuration = configuration_store.get_configuration(db)
    db.commit()
    return {
        "published": publication.status == "succeeded",
        "status": publication.status,
        "publicationId": publication.id,
        "warnings": publication.warnings or [],
        "error": publication.error,
        "configuration": _serialize(configuration),
    }


@router.get("/publications")
def list_publications(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[models.AuthSession, Depends(auth.require_auth)],
) -> list[dict]:
    rows = db.scalars(
        select(models.GuidePublication)
        .where(models.GuidePublication.organization_id == config.DEFAULT_ORGANIZATION_ID)
        .order_by(models.GuidePublication.created_at.desc())
    )
    return [_serialize_publication(row) for row in rows]


@router.post("/publications/{publication_id}/rollback")
async def rollback(
    publication_id: str,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[models.AuthSession, Depends(auth.require_auth)],
) -> dict:
    """Re-push a stored bundle byte for byte. Because every publish replaces
    the guide wholesale, this is the only real undo."""
    if not guideants_admin.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Publishing is not configured: set GUIDEANTS_ADMIN_EMAIL and "
                "GUIDEANTS_ADMIN_PASSWORD."
            ),
        )
    publication = db.scalar(
        select(models.GuidePublication).where(
            models.GuidePublication.id == publication_id,
            models.GuidePublication.organization_id == config.DEFAULT_ORGANIZATION_ID,
        )
    )
    if publication is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    try:
        replay = await publisher.republish(
            db, publication, published_by=session.user_email
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    configuration = configuration_store.get_configuration(db)
    db.commit()
    return {
        "published": replay.status == "succeeded",
        "status": replay.status,
        "publicationId": replay.id,
        "warnings": replay.warnings or [],
        "error": replay.error,
        "configuration": _serialize(configuration),
    }


@router.get("/bundle")
def download_bundle(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[models.AuthSession, Depends(auth.require_auth)],
) -> Response:
    """The escape hatch: when GuideAnts is unreachable or credentials are
    unset, an admin can still download the exact zip and import it by hand
    in the GuideAnts UI."""
    try:
        zip_bytes, _hash, _instructions, _count = publisher.build_zip(db)
    except (ValueError, bundle_module.BundleError, template.SlotError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    db.commit()
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="guide-bundle.zip"'},
    )
