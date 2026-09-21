"""Load rows -> render -> bundle -> push -> record.

The ordering here is a safety property, not a style choice. Everything that
can fail locally (rendering, slot checks, bundle invariants) runs before the
first network call, so a bad configuration is refused rather than published
half-way. And the draft flag clears only after a confirmed success: a failed
publish must never leave the console looking published.

What gets pushed is the rendered **instructions** and the rendered
**knowledge files** (`guideants_admin.update_guide`), through the verified
read-modify-write PUT. The bundle zip is still built -- it runs the
invariants, produces the content hash the history and the preview diff are
keyed on, and backs the `/bundle` download -- but it is never uploaded,
because GuideAnts' import endpoint destroys a guide that has indexed
knowledge files. See guideants_admin.py's module docstring.

Publish owns the guide's whole vector store, so the push/no-push decision
keys on the **content hash**, which covers the instructions and the
knowledge files together. `_HASH_MARKER` is folded into that hash so a row
recorded before knowledge sync existed can never match a hash computed now
-- otherwise the first publish after this change would see "unchanged" and
skip the very sync it exists to perform.
"""

from __future__ import annotations

import hashlib
import io
import logging
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, configuration_store, knowledge_store, models
from . import bundle as bundle_module
from . import guideants_admin, render, template

logger = logging.getLogger(__name__)

# Folded into every stored content_hash. A GuidePublication written before
# Publish synced knowledge recorded the bare bundle hash, and its bundle
# would hash identically today -- so without this marker the first publish
# after the change would be taken for a no-op and the knowledge would never
# be sent. Bump the suffix again if what a push covers ever changes.
_HASH_MARKER = ":knowledge-sync-v1"

KNOWLEDGE_PREFIX = "VectorStores/default/"


def _marked(bundle_hash: str) -> str:
    return hashlib.sha256((bundle_hash + _HASH_MARKER).encode("utf-8")).hexdigest()


def _knowledge_warning(files: dict | None) -> str | None:
    """The one warning a successful push earns: what moved in the vector
    store, and that it is not searchable the instant this returns."""
    files = files or {}
    changed = int(files.get("added", 0)) + int(files.get("replaced", 0))
    removed = int(files.get("removed", 0))
    if changed + removed == 0:
        return None
    return (
        f"Knowledge updated ({changed} added or replaced, {removed} removed). "
        "GuideAnts indexes it in the background, so changed items may take a "
        "minute to become searchable."
    )


def _warnings_for(remote: list | None, files: dict | None = None) -> list | None:
    warnings = list(remote or [])
    knowledge = _knowledge_warning(files)
    if knowledge:
        warnings.append(knowledge)
    return warnings or None


def knowledge_from_bundle(zip_bytes: bytes | None) -> dict[str, bytes]:
    """The knowledge files stored inside a publication's bundle zip.

    This is what makes a rollback complete: the stored instructions alone
    would restore the guide's wording while leaving whatever knowledge the
    publish being rolled back had put there.
    """
    if not zip_bytes:
        return {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        return {
            name: archive.read(name)
            for name in archive.namelist()
            if name.startswith(KNOWLEDGE_PREFIX) and not name.endswith("/")
        }


@dataclass
class RenderResult:
    """Everything one render produces. `build_zip` is the narrower, older
    view of it kept for the API layer and the /bundle download."""

    zip_bytes: bytes
    content_hash: str
    instructions: str
    knowledge: dict[str, bytes]


@dataclass
class PreviewResult:
    instructions: str
    content_hash: str
    knowledge_item_count: int
    changed: bool
    previous_instructions: str | None


def _knowledge_items(db: Session) -> list[models.KnowledgeItem]:
    # Seeds an empty table first, so the bundle download and the knowledge
    # count describe the shop's real policy set rather than an empty store --
    # an admin can reach Publish without ever opening the console's
    # Knowledge page.
    knowledge_store.seed_default_items(db)
    return list(
        db.scalars(
            select(models.KnowledgeItem).where(
                models.KnowledgeItem.organization_id == config.DEFAULT_ORGANIZATION_ID
            )
        )
    )


def latest_succeeded(db: Session) -> models.GuidePublication | None:
    return db.scalar(
        select(models.GuidePublication)
        .where(
            models.GuidePublication.organization_id == config.DEFAULT_ORGANIZATION_ID,
            models.GuidePublication.status == "succeeded",
        )
        .order_by(models.GuidePublication.created_at.desc())
    )


def _render(db: Session) -> RenderResult:
    """Render and bundle. Raises ValueError/BundleError -- always before
    the caller reaches the network."""
    configuration = configuration_store.get_configuration(db)
    instructions = template.render_instructions(render.build_slots(configuration))
    knowledge = render.knowledge_files(_knowledge_items(db), date.today())
    zip_bytes, bundle_hash = bundle_module.build_bundle(
        instructions, knowledge, template.load_static_files()
    )
    return RenderResult(
        zip_bytes=zip_bytes,
        content_hash=_marked(bundle_hash),
        instructions=instructions,
        knowledge=knowledge,
    )


def build_zip(db: Session) -> tuple[bytes, str, str, int]:
    """Returns (zip_bytes, content_hash, instructions, knowledge_count).
    Raises ValueError/BundleError before any network call."""
    rendered = _render(db)
    return (
        rendered.zip_bytes,
        rendered.content_hash,
        rendered.instructions,
        len(rendered.knowledge),
    )


def render_preview(db: Session) -> PreviewResult:
    """Everything a publish does except the push -- so an admin can see
    exactly what would be sent, and an invariant failure surfaces here
    rather than at the point of no return."""
    rendered = _render(db)
    previous = latest_succeeded(db)
    return PreviewResult(
        instructions=rendered.instructions,
        content_hash=rendered.content_hash,
        knowledge_item_count=len(rendered.knowledge),
        changed=previous is None or previous.content_hash != rendered.content_hash,
        previous_instructions=previous.instructions_text if previous else None,
    )


async def publish(db: Session, published_by: str) -> models.GuidePublication:
    """Renders and pushes. Never raises for a *remote* failure -- those are
    recorded on the returned row so the caller can report them -- but does
    raise for a local one (bad configuration, failed invariant), because
    nothing was attempted and there is nothing to record."""
    rendered = _render(db)
    content_hash = rendered.content_hash
    knowledge_count = len(rendered.knowledge)

    configuration = configuration_store.get_configuration(db)
    # Deep-copied so the stored snapshot is a frozen record of what was
    # published, not a live alias of the configuration row's JSON columns.
    snapshot = deepcopy(
        {
            "business_profile": configuration.business_profile,
            "identity": configuration.identity,
            "terminology": configuration.terminology,
        }
    )

    previous = latest_succeeded(db)
    if (
        previous is not None
        and previous.content_hash == content_hash
        and previous.published_config == snapshot
    ):
        # Nothing changed anywhere: no push, no new row.
        logger.info("publish skipped: content unchanged since %s", previous.created_at)
        return previous

    if previous is not None and previous.content_hash == content_hash:
        # A push would send exactly what the guide already has. The hash
        # covers the instructions AND the knowledge files, so "same hash"
        # really does mean there is nothing on the wire to change.
        #
        # But something local did change -- the configuration snapshot --
        # and the snapshot is how the greeting reaches callers
        # (app/main.py's _published_greeting reads the latest succeeded
        # row). Most configuration fields are not template slots:
        # identity.greeting/closing, terminology.*, and the profile's
        # phone/website/timezone/locations appear nowhere in the template.
        # So a new succeeded publication must still be recorded, or the new
        # greeting never goes live and the draft flag never clears.
        logger.info(
            "publish: nothing to send GuideAnts; recording the new configuration"
        )
        publication = models.GuidePublication(
            organization_id=config.DEFAULT_ORGANIZATION_ID,
            published_by=published_by,
            content_hash=content_hash,
            instructions_text=rendered.instructions,
            published_config=snapshot,
            knowledge_item_count=knowledge_count,
            bundle_bytes=rendered.zip_bytes,
            status="succeeded",
            warnings=None,
        )
        db.add(publication)
        configuration_store.mark_published(db, configuration, datetime.utcnow())
        db.commit()
        return publication

    publication = models.GuidePublication(
        organization_id=config.DEFAULT_ORGANIZATION_ID,
        published_by=published_by,
        content_hash=content_hash,
        instructions_text=rendered.instructions,
        published_config={},
        knowledge_item_count=knowledge_count,
        bundle_bytes=rendered.zip_bytes,
        status="pending",
    )
    db.add(publication)
    db.flush()

    try:
        result = await guideants_admin.update_guide(
            rendered.instructions, rendered.knowledge
        )
    except guideants_admin.GuideAntsAdminError as exc:
        publication.status = "failed"
        publication.error = str(exc)
        db.commit()
        logger.warning("publish failed: %s", exc)
        return publication

    publication.status = "succeeded"
    publication.warnings = _warnings_for(result.get("warnings"), result.get("files"))
    # Written only on success: this snapshot is what app/main.py's greeting
    # reads, so a failed publish must not move what callers hear.
    publication.published_config = snapshot
    configuration_store.mark_published(db, configuration, datetime.utcnow())
    db.commit()
    return publication


async def republish(
    db: Session, publication: models.GuidePublication, published_by: str
) -> models.GuidePublication:
    """Rollback: push a previously published guide state again.

    The stored `instructions_text` and the knowledge files stored inside
    that publication's `bundle_bytes` are re-sent as recorded rather than
    re-rendered -- re-rendering would pick up whatever the configuration
    and the knowledge table say now, which is precisely what the admin is
    trying to back out of.

    Because Publish owns the guide's whole vector store, a rollback must
    carry the knowledge too: replaying the instructions alone would leave
    the guide answering old wording out of the newer knowledge base. That
    is why a row with no stored bundle is refused rather than replayed.

    Recorded as a NEW publication rather than mutating the old one, so the
    history stays an append-only account of what was sent and when.
    """
    if not publication.instructions_text:
        raise ValueError(
            f"publication {publication.id} has no stored instructions to republish"
        )
    if not publication.bundle_bytes:
        raise ValueError(
            f"publication {publication.id} has no stored bundle, so its knowledge "
            "files cannot be replayed -- rolling back to it would leave the "
            "guide's knowledge base where it is now"
        )

    knowledge = knowledge_from_bundle(publication.bundle_bytes)

    replay = models.GuidePublication(
        organization_id=config.DEFAULT_ORGANIZATION_ID,
        published_by=published_by,
        content_hash=publication.content_hash,
        instructions_text=publication.instructions_text,
        published_config={},
        knowledge_item_count=publication.knowledge_item_count,
        bundle_bytes=publication.bundle_bytes,
        status="pending",
    )
    db.add(replay)
    db.flush()

    try:
        result = await guideants_admin.update_guide(
            publication.instructions_text, knowledge
        )
    except guideants_admin.GuideAntsAdminError as exc:
        replay.status = "failed"
        replay.error = str(exc)
        db.commit()
        logger.warning("rollback failed: %s", exc)
        return replay

    replay.status = "succeeded"
    replay.warnings = _warnings_for(result.get("warnings"), result.get("files"))
    replay.published_config = deepcopy(publication.published_config or {})
    # The live guide now carries these instructions, so the console is clean again
    # even though the configuration row may differ from what was restored.
    configuration = configuration_store.get_configuration(db)
    configuration_store.mark_published(db, configuration, datetime.utcnow())
    db.commit()
    return replay
