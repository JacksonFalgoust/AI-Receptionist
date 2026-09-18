"""Load rows -> render -> bundle -> push -> record.

The ordering here is a safety property, not a style choice. Everything that
can fail locally (rendering, slot checks, bundle invariants) runs before the
first network call, so a bad configuration is refused rather than published
half-way. And the draft flag clears only after a confirmed success: a failed
publish must never leave the console looking published.

What actually gets pushed is the rendered **instructions** and nothing else
(`guideants_admin.update_guide_instructions`). The bundle is still built --
it runs the invariants, produces the content hash the history and the
preview diff are keyed on, and backs the `/bundle` download -- but it is no
longer uploaded, because GuideAnts' import endpoint destroys a guide that
has indexed knowledge files. See guideants_admin.py's module docstring.

The consequence to keep in mind: knowledge is NOT synced by Publish. Every
successful publication of a guide that has knowledge items carries
KNOWLEDGE_NOT_SYNCED_WARNING so the console says so rather than implying
the vector store moved.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, configuration_store, knowledge_store, models
from . import bundle as bundle_module
from . import guideants_admin, render, template

logger = logging.getLogger(__name__)

KNOWLEDGE_NOT_SYNCED_WARNING = (
    "Knowledge items were not synced to GuideAnts: its import endpoint is "
    "unsafe for guides with indexed files, so Publish only updates the "
    "instructions. Update the knowledge base in the GuideAnts editor."
)


def _warnings_for(remote: list | None, knowledge_count: int) -> list | None:
    warnings = list(remote or [])
    if knowledge_count > 0:
        warnings.append(KNOWLEDGE_NOT_SYNCED_WARNING)
    return warnings or None


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


def build_zip(db: Session) -> tuple[bytes, str, str, int]:
    """Returns (zip_bytes, content_hash, instructions, knowledge_count).
    Raises ValueError/BundleError before any network call."""
    configuration = configuration_store.get_configuration(db)
    instructions = template.render_instructions(render.build_slots(configuration))
    knowledge = render.knowledge_files(_knowledge_items(db), date.today())
    zip_bytes, content_hash = bundle_module.build_bundle(
        instructions, knowledge, template.load_static_files()
    )
    return zip_bytes, content_hash, instructions, len(knowledge)


def render_preview(db: Session) -> PreviewResult:
    """Everything a publish does except the push -- so an admin can see
    exactly what would be sent, and an invariant failure surfaces here
    rather than at the point of no return."""
    _, content_hash, instructions, knowledge_count = build_zip(db)
    previous = latest_succeeded(db)
    return PreviewResult(
        instructions=instructions,
        content_hash=content_hash,
        knowledge_item_count=knowledge_count,
        changed=previous is None or previous.content_hash != content_hash,
        previous_instructions=previous.instructions_text if previous else None,
    )


async def publish(db: Session, published_by: str) -> models.GuidePublication:
    """Renders and pushes. Never raises for a *remote* failure -- those are
    recorded on the returned row so the caller can report them -- but does
    raise for a local one (bad configuration, failed invariant), because
    nothing was attempted and there is nothing to record."""
    zip_bytes, content_hash, instructions, knowledge_count = build_zip(db)

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

    if previous is not None and previous.instructions_text == instructions:
        # The instructions are the ONLY thing a push would change, and they
        # are identical -- so there is nothing to send. Two edits land here:
        #
        #   * a configuration-only change (greeting, closing, terminology,
        #     phone/website/timezone/locations): no template slot moves, and
        #     the greeting in particular reaches callers ONLY through
        #     published_config (app/main.py's _published_greeting reads the
        #     latest succeeded row);
        #   * a knowledge-only change, which moves the content hash but not
        #     the instructions, and which Publish does not sync at all.
        #
        # Either way a new succeeded publication must still be recorded, or
        # the new greeting never goes live and the draft flag never clears.
        logger.info(
            "publish: instructions unchanged; recording without a GuideAnts call"
        )
        publication = models.GuidePublication(
            organization_id=config.DEFAULT_ORGANIZATION_ID,
            published_by=published_by,
            content_hash=content_hash,
            instructions_text=instructions,
            published_config=snapshot,
            knowledge_item_count=knowledge_count,
            bundle_bytes=zip_bytes,
            status="succeeded",
            warnings=_warnings_for(None, knowledge_count),
        )
        db.add(publication)
        configuration_store.mark_published(db, configuration, datetime.utcnow())
        db.commit()
        return publication

    publication = models.GuidePublication(
        organization_id=config.DEFAULT_ORGANIZATION_ID,
        published_by=published_by,
        content_hash=content_hash,
        instructions_text=instructions,
        published_config={},
        knowledge_item_count=knowledge_count,
        bundle_bytes=zip_bytes,
        status="pending",
    )
    db.add(publication)
    db.flush()

    try:
        result = await guideants_admin.update_guide_instructions(instructions)
    except guideants_admin.GuideAntsAdminError as exc:
        publication.status = "failed"
        publication.error = str(exc)
        db.commit()
        logger.warning("publish failed: %s", exc)
        return publication

    publication.status = "succeeded"
    publication.warnings = _warnings_for(result.get("warnings"), knowledge_count)
    # Written only on success: this snapshot is what app/main.py's greeting
    # reads, so a failed publish must not move what callers hear.
    publication.published_config = snapshot
    configuration_store.mark_published(db, configuration, datetime.utcnow())
    db.commit()
    return publication


async def republish(
    db: Session, publication: models.GuidePublication, published_by: str
) -> models.GuidePublication:
    """Rollback: push a previously published set of instructions again.

    The stored `instructions_text` is re-sent as recorded rather than
    re-rendered -- re-rendering would pick up whatever the configuration
    says now, which is precisely what the admin is trying to back out of.

    It restores the instructions only. A publish never changed anything
    else about the guide, so there is nothing else to put back; knowledge,
    tools and context options are untouched by both directions.

    Recorded as a NEW publication rather than mutating the old one, so the
    history stays an append-only account of what was sent and when.
    """
    if not publication.instructions_text:
        raise ValueError(
            f"publication {publication.id} has no stored instructions to republish"
        )

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
        result = await guideants_admin.update_guide_instructions(
            publication.instructions_text
        )
    except guideants_admin.GuideAntsAdminError as exc:
        replay.status = "failed"
        replay.error = str(exc)
        db.commit()
        logger.warning("rollback failed: %s", exc)
        return replay

    replay.status = "succeeded"
    replay.warnings = _warnings_for(
        result.get("warnings"), publication.knowledge_item_count
    )
    replay.published_config = deepcopy(publication.published_config or {})
    # The live guide now carries these instructions, so the console is clean again
    # even though the configuration row may differ from what was restored.
    configuration = configuration_store.get_configuration(db)
    configuration_store.mark_published(db, configuration, datetime.utcnow())
    db.commit()
    return replay
