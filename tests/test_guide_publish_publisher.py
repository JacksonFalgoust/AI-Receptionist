"""Orchestration: load rows, render, bundle, push, record.

The rule these tests exist to protect: a FAILED publish must never leave
the console looking published. has_unpublished_changes stays set, no
published_config is written, and the greeting a caller hears does not move.
"""

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config, configuration_store, models
from app.db import Base
from app.guide_publish import guideants_admin, publisher


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def push_ok(monkeypatch):
    """Records the INSTRUCTIONS pushed -- a publish sends nothing else."""
    calls = []

    async def fake_update(instructions):
        calls.append(instructions)
        return {"guideId": "abc", "warnings": ["model alias not resolved"]}

    monkeypatch.setattr(guideants_admin, "update_guide_instructions", fake_update)
    monkeypatch.setattr(guideants_admin, "is_configured", lambda: True)
    return calls


@pytest.fixture
def push_fails(monkeypatch):
    async def fake_update(instructions):
        raise guideants_admin.GuideAntsAdminError("GuideAnts unreachable on GET /api/guides")

    monkeypatch.setattr(guideants_admin, "update_guide_instructions", fake_update)
    monkeypatch.setattr(guideants_admin, "is_configured", lambda: True)


def test_preview_renders_without_touching_the_network(db):
    preview = publisher.render_preview(db)
    assert "Peachtree Pedals" in preview.instructions
    assert preview.content_hash
    assert preview.changed is True  # nothing published yet


def test_successful_publish_records_and_clears_the_draft_flag(db, push_ok):
    row = configuration_store.get_configuration(db)
    configuration_store.save_draft(db, row, {"identity": {"greeting": "Hi there"}})
    db.commit()

    publication = asyncio.run(publisher.publish(db, published_by="admin@example.com"))

    assert publication.status == "succeeded"
    assert publication.warnings[0] == "model alias not resolved"
    assert publisher.KNOWLEDGE_NOT_SYNCED_WARNING in publication.warnings
    assert publication.published_config["identity"]["greeting"] == "Hi there"
    assert publication.bundle_bytes
    assert push_ok == [publication.instructions_text], (
        "a publish sends the rendered instructions and nothing else"
    )
    assert configuration_store.get_configuration(db).has_unpublished_changes is False


def test_failed_publish_leaves_the_console_unpublished(db, push_fails):
    row = configuration_store.get_configuration(db)
    configuration_store.save_draft(db, row, {"identity": {"greeting": "Hi there"}})
    db.commit()

    publication = asyncio.run(publisher.publish(db, published_by="admin@example.com"))

    assert publication.status == "failed"
    assert "unreachable" in publication.error
    assert publication.published_config == {}
    # The critical assertion: still dirty, so the UI cannot claim success.
    assert configuration_store.get_configuration(db).has_unpublished_changes is True
    assert publisher.latest_succeeded(db) is None


def test_republishing_unchanged_content_is_a_no_op(db, push_ok):
    first = asyncio.run(publisher.publish(db, published_by="admin@example.com"))
    second = asyncio.run(publisher.publish(db, published_by="admin@example.com"))

    assert second.status == "succeeded"
    assert len(push_ok) == 1, "unchanged content must not be pushed twice"
    # A TRUE no-op -- same bundle AND same configuration -- records nothing.
    assert second.id == first.id
    assert db.query(models.GuidePublication).count() == 1


def test_configuration_only_change_publishes_without_a_push(db, push_ok):
    """A greeting edit changes no template slot, so the bundle's hash is
    unchanged -- but identity.greeting reaches callers only through
    published_config, so the publish must still be recorded."""
    first = asyncio.run(publisher.publish(db, published_by="admin@example.com"))
    assert len(push_ok) == 1

    row = configuration_store.get_configuration(db)
    configuration_store.save_draft(
        db, row, {"identity": {**row.identity, "greeting": "Peachtree Pedals, howdy!"}}
    )
    db.commit()
    assert configuration_store.get_configuration(db).has_unpublished_changes is True

    second = asyncio.run(publisher.publish(db, published_by="admin@example.com"))

    # (a) a NEW succeeded publication carrying the new snapshot, no push
    assert second.id != first.id
    assert second.status == "succeeded"
    assert second.published_config["identity"]["greeting"] == "Peachtree Pedals, howdy!"
    assert second.content_hash == first.content_hash
    assert second.bundle_bytes == first.bundle_bytes
    assert second.instructions_text == first.instructions_text
    assert second.knowledge_item_count == first.knowledge_item_count
    assert len(push_ok) == 1, "unchanged instructions must not be sent again"

    # (b) the draft flag clears
    assert configuration_store.get_configuration(db).has_unpublished_changes is False

    # (c) the greeting app/main.py reads is the new one
    latest = publisher.latest_succeeded(db)
    assert latest.id == second.id
    assert latest.published_config["identity"]["greeting"] == "Peachtree Pedals, howdy!"


def test_configuration_only_change_does_not_mutate_the_earlier_snapshot(db, push_ok):
    """published_config is a frozen record: editing the draft afterwards
    must not rewrite what an earlier publication says was published."""
    first = asyncio.run(publisher.publish(db, published_by="admin@example.com"))
    original = first.published_config["identity"]["greeting"]

    row = configuration_store.get_configuration(db)
    row.identity["greeting"] = "mutated in place"
    configuration_store.save_draft(db, row, {"identity": row.identity})
    db.commit()

    assert first.published_config["identity"]["greeting"] == original


def test_changed_content_publishes_again(db, push_ok):
    asyncio.run(publisher.publish(db, published_by="admin@example.com"))
    row = configuration_store.get_configuration(db)
    configuration_store.save_draft(
        db, row, {"business_profile": {**row.business_profile, "name": "Dogwood Cycles"}}
    )
    db.commit()

    asyncio.run(publisher.publish(db, published_by="admin@example.com"))
    assert len(push_ok) == 2


def test_invariant_failure_refuses_before_any_network_call(db, push_ok, monkeypatch):
    row = configuration_store.get_configuration(db)
    configuration_store.save_draft(
        db, row, {"business_profile": {**row.business_profile, "name": "**Bad**"}}
    )
    db.commit()

    with pytest.raises(ValueError, match="business.name"):
        asyncio.run(publisher.publish(db, published_by="admin@example.com"))
    assert push_ok == [], "nothing may reach GuideAnts when an invariant fails"


def test_publishable_knowledge_is_counted(db, push_ok):
    from datetime import datetime

    db.add(
        models.KnowledgeItem(
            id="k1",
            organization_id=config.DEFAULT_ORGANIZATION_ID,  # "org_default"
            title="Damage policy",
            type="policy", status="active", source="Manual entry",
            content="Riders pay for damage.", tags=[], updated_at=datetime.utcnow(),
        )
    )
    db.commit()
    publication = asyncio.run(publisher.publish(db, published_by="admin@example.com"))
    assert publication.knowledge_item_count == 1


def test_republish_pushes_the_stored_instructions_again(db, push_ok):
    first = asyncio.run(publisher.publish(db, published_by="admin@example.com"))
    row = configuration_store.get_configuration(db)
    configuration_store.save_draft(
        db, row, {"business_profile": {**row.business_profile, "name": "Dogwood Cycles"}}
    )
    db.commit()
    asyncio.run(publisher.publish(db, published_by="admin@example.com"))

    rolled_back = asyncio.run(
        publisher.republish(db, first, published_by="admin@example.com")
    )

    assert rolled_back.status == "succeeded"
    assert rolled_back.content_hash == first.content_hash
    assert rolled_back.instructions_text == first.instructions_text
    assert rolled_back.id != first.id, "a rollback is recorded as its own publication"
    assert len(push_ok) == 3
    assert push_ok[-1] == first.instructions_text, (
        "a rollback re-sends the STORED instructions, not a re-render"
    )


def test_republish_without_stored_instructions_fails_cleanly(db, push_ok):
    publication = models.GuidePublication(
        organization_id=config.DEFAULT_ORGANIZATION_ID,
        published_by="admin@example.com", content_hash="old", instructions_text="",
        published_config={}, knowledge_item_count=0, bundle_bytes=None,
        status="succeeded",
    )
    db.add(publication)
    db.commit()
    with pytest.raises(ValueError, match="no stored instructions"):
        asyncio.run(publisher.republish(db, publication, published_by="a@example.com"))
    assert push_ok == []


def test_republish_needs_no_stored_bundle(db, push_ok):
    """The bundle is no longer what a rollback replays, so an old row that
    predates bundle storage is still a valid rollback target."""
    publication = models.GuidePublication(
        organization_id=config.DEFAULT_ORGANIZATION_ID,
        published_by="admin@example.com", content_hash="old",
        instructions_text="the instructions as published",
        published_config={"identity": {"greeting": "Old greeting"}},
        knowledge_item_count=0, bundle_bytes=None, status="succeeded",
    )
    db.add(publication)
    db.commit()

    replay = asyncio.run(
        publisher.republish(db, publication, published_by="a@example.com")
    )
    assert replay.status == "succeeded"
    assert push_ok == ["the instructions as published"]
    assert replay.published_config == {"identity": {"greeting": "Old greeting"}}


def test_knowledge_only_change_records_without_a_push(db, push_ok):
    """Publish does not sync knowledge -- GuideAnts' import endpoint is
    unsafe for a guide with indexed files. A knowledge edit therefore moves
    the content hash but leaves the instructions alone, so nothing is sent;
    the publication is still recorded so the console stops looking dirty."""
    from datetime import datetime

    first = asyncio.run(publisher.publish(db, published_by="admin@example.com"))
    assert len(push_ok) == 1

    db.add(
        models.KnowledgeItem(
            id="k-new",
            organization_id=config.DEFAULT_ORGANIZATION_ID,
            title="Winter hours",
            type="policy", status="active", source="Manual entry",
            content="We close an hour early in January.", tags=[],
            updated_at=datetime.utcnow(),
        )
    )
    db.commit()

    second = asyncio.run(publisher.publish(db, published_by="admin@example.com"))

    assert second.id != first.id
    assert second.status == "succeeded"
    assert second.content_hash != first.content_hash, "the bundle really did change"
    assert second.instructions_text == first.instructions_text
    assert second.knowledge_item_count == first.knowledge_item_count + 1
    assert len(push_ok) == 1, "a knowledge edit changes no instructions to send"
    assert publisher.KNOWLEDGE_NOT_SYNCED_WARNING in second.warnings


def test_the_knowledge_warning_says_publish_did_not_sync_it(db, push_ok):
    publication = asyncio.run(publisher.publish(db, published_by="admin@example.com"))
    assert publication.knowledge_item_count > 0
    warning = publisher.KNOWLEDGE_NOT_SYNCED_WARNING
    assert warning in publication.warnings
    assert "not synced" in warning and "GuideAnts editor" in warning


def test_no_knowledge_warning_when_there_is_no_knowledge(db, push_ok, monkeypatch):
    monkeypatch.setattr(publisher, "_knowledge_items", lambda db: [])
    publication = asyncio.run(publisher.publish(db, published_by="admin@example.com"))
    assert publication.knowledge_item_count == 0
    assert publisher.KNOWLEDGE_NOT_SYNCED_WARNING not in (publication.warnings or [])


def test_an_instructions_change_pushes_exactly_the_new_instructions(db, push_ok):
    asyncio.run(publisher.publish(db, published_by="admin@example.com"))
    row = configuration_store.get_configuration(db)
    configuration_store.save_draft(
        db, row, {"business_profile": {**row.business_profile, "name": "Dogwood Cycles"}}
    )
    db.commit()

    second = asyncio.run(publisher.publish(db, published_by="admin@example.com"))

    assert len(push_ok) == 2
    assert push_ok[-1] == second.instructions_text
    assert "Dogwood Cycles" in push_ok[-1]
