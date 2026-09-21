"""Orchestration: load rows, render, bundle, push, record.

The rule these tests exist to protect: a FAILED publish must never leave
the console looking published. has_unpublished_changes stays set, no
published_config is written, and the greeting a caller hears does not move.

A push now carries the rendered knowledge files as well as the rendered
instructions, so the second rule is that "nothing to send" must key on the
content hash, which covers both -- a knowledge edit that left the
instructions alone used to be swallowed.
"""

import asyncio
import hashlib

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


class Push(list):
    """Every (instructions, knowledge) pair that reached GuideAnts, plus the
    file counts the next push should report back."""

    files = {"added": 0, "replaced": 0, "removed": 0, "unchanged": 0}

    @property
    def instructions(self):
        return [call[0] for call in self]

    @property
    def knowledge(self):
        return [call[1] for call in self]


@pytest.fixture
def push_ok(monkeypatch):
    calls = Push()

    async def fake_update(instructions, knowledge):
        calls.append((instructions, knowledge))
        return {
            "guideId": "abc",
            "warnings": ["model alias not resolved"],
            "files": dict(calls.files),
        }

    monkeypatch.setattr(guideants_admin, "update_guide", fake_update)
    monkeypatch.setattr(guideants_admin, "is_configured", lambda: True)
    return calls


@pytest.fixture
def push_fails(monkeypatch):
    async def fake_update(instructions, knowledge):
        raise guideants_admin.GuideAntsAdminError("GuideAnts unreachable on GET /api/guides")

    monkeypatch.setattr(guideants_admin, "update_guide", fake_update)
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
    assert publication.warnings == ["model alias not resolved"]
    assert publication.published_config["identity"]["greeting"] == "Hi there"
    assert publication.bundle_bytes
    assert push_ok.instructions == [publication.instructions_text]
    # And the knowledge, keyed by the bundle path the admin client strips.
    assert push_ok.knowledge[0], "a publish sends the rendered knowledge too"
    assert all(
        name.startswith("VectorStores/default/") for name in push_ok.knowledge[0]
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
    assert push_ok.instructions[-1] == first.instructions_text, (
        "a rollback re-sends the STORED instructions, not a re-render"
    )
    assert push_ok.knowledge[-1] == publisher.knowledge_from_bundle(
        first.bundle_bytes
    ), "and the knowledge it was published with, not today's"


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


def test_republish_without_a_stored_bundle_is_refused(db, push_ok):
    """The bundle is where a rollback's knowledge files come from. Replaying
    the instructions alone would leave the guide answering restored wording
    out of the knowledge base the admin is rolling back from."""
    publication = models.GuidePublication(
        organization_id=config.DEFAULT_ORGANIZATION_ID,
        published_by="admin@example.com", content_hash="old",
        instructions_text="the instructions as published",
        published_config={"identity": {"greeting": "Old greeting"}},
        knowledge_item_count=0, bundle_bytes=None, status="succeeded",
    )
    db.add(publication)
    db.commit()

    with pytest.raises(ValueError, match="no stored bundle"):
        asyncio.run(publisher.republish(db, publication, published_by="a@example.com"))
    assert push_ok == []


def test_republish_restores_the_stored_snapshot_and_bundle_knowledge(db, push_ok):
    """A stored bundle is the whole rollback payload: the instructions the
    row recorded, the knowledge that bundle holds, and the snapshot the
    greeting is read out of."""
    zip_bytes, content_hash, _instructions, _count = publisher.build_zip(db)
    publication = models.GuidePublication(
        organization_id=config.DEFAULT_ORGANIZATION_ID,
        published_by="admin@example.com", content_hash=content_hash,
        instructions_text="the instructions as published",
        published_config={"identity": {"greeting": "Old greeting"}},
        knowledge_item_count=1, bundle_bytes=zip_bytes, status="succeeded",
    )
    db.add(publication)
    db.commit()

    replay = asyncio.run(
        publisher.republish(db, publication, published_by="a@example.com")
    )

    assert replay.status == "succeeded"
    assert push_ok.instructions == ["the instructions as published"]
    assert push_ok.knowledge[0] == publisher.knowledge_from_bundle(zip_bytes)
    assert push_ok.knowledge[0], "the stored bundle really does carry knowledge"
    assert all(
        name.startswith("VectorStores/default/") for name in push_ok.knowledge[0]
    ), "only the vector-store folder is replayed, not instructions.md or the schemas"
    assert replay.published_config == {"identity": {"greeting": "Old greeting"}}


def test_a_knowledge_only_change_is_pushed(db, push_ok):
    """Editing an existing item's content moves no template slot (its title,
    and so the topics list, is unchanged), so the instructions are
    byte-identical -- the content hash is what notices, and the whole point
    of keying on it is that this edit reaches the guide."""
    first = asyncio.run(publisher.publish(db, published_by="admin@example.com"))
    assert len(push_ok) == 1

    item = publisher._knowledge_items(db)[0]
    item.content = "We close an hour early in January."
    db.commit()

    second = asyncio.run(publisher.publish(db, published_by="admin@example.com"))

    assert second.id != first.id
    assert second.status == "succeeded"
    assert second.content_hash != first.content_hash
    assert second.instructions_text == first.instructions_text
    assert second.knowledge_item_count == first.knowledge_item_count
    assert len(push_ok) == 2, "a knowledge edit must reach the guide"
    assert b"close an hour early" in push_ok.knowledge[-1][
        f"VectorStores/default/{item.id}.md"
    ]


def test_the_warning_reports_what_moved_in_the_vector_store(db, push_ok):
    """Indexing is asynchronous, so a publish that changed knowledge is not
    fully live when it returns -- the console has to say so."""
    push_ok.files = {"added": 2, "replaced": 1, "removed": 3, "unchanged": 5}
    publication = asyncio.run(publisher.publish(db, published_by="admin@example.com"))

    warning = next(w for w in publication.warnings if w.startswith("Knowledge"))
    assert "3 added or replaced" in warning
    assert "3 removed" in warning
    assert "background" in warning
    # The remote warning is still carried, not replaced.
    assert "model alias not resolved" in publication.warnings


def test_no_knowledge_warning_when_no_file_moved(db, push_ok):
    push_ok.files = {"added": 0, "replaced": 0, "removed": 0, "unchanged": 4}
    publication = asyncio.run(publisher.publish(db, published_by="admin@example.com"))
    assert publication.warnings == ["model alias not resolved"]


def test_no_knowledge_warning_on_the_no_push_path(db, push_ok):
    """Nothing was sent, so there is nothing to say about indexing."""
    asyncio.run(publisher.publish(db, published_by="admin@example.com"))
    row = configuration_store.get_configuration(db)
    configuration_store.save_draft(
        db, row, {"identity": {**row.identity, "greeting": "Howdy!"}}
    )
    db.commit()

    second = asyncio.run(publisher.publish(db, published_by="admin@example.com"))
    assert len(push_ok) == 1
    assert second.warnings is None


def test_the_knowledge_sync_marker_is_folded_into_the_stored_hash(db, push_ok):
    """A publication recorded before Publish synced knowledge stored the
    bare bundle hash. If that row could still match today's hash, the first
    publish after this change would be read as a no-op and the knowledge
    would never be sent."""
    zip_bytes, content_hash, instructions, _count = publisher.build_zip(db)
    bare = hashlib.sha256()
    # The pre-marker hash: name + bytes of every file in the bundle.
    import zipfile, io

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        for name in sorted(archive.namelist()):
            bare.update(name.encode("utf-8"))
            bare.update(archive.read(name))
    assert content_hash != bare.hexdigest(), "the marker must change the hash"

    db.add(
        models.GuidePublication(
            organization_id=config.DEFAULT_ORGANIZATION_ID,
            published_by="admin@example.com",
            content_hash=bare.hexdigest(),           # an old-style row
            instructions_text=instructions,
            published_config={}, knowledge_item_count=1,
            bundle_bytes=zip_bytes, status="succeeded",
        )
    )
    db.commit()

    publication = asyncio.run(publisher.publish(db, published_by="admin@example.com"))

    assert len(push_ok) == 1, "an old-style row must not suppress the first sync"
    assert publication.content_hash == content_hash


def test_an_instructions_change_pushes_exactly_the_new_instructions(db, push_ok):
    asyncio.run(publisher.publish(db, published_by="admin@example.com"))
    row = configuration_store.get_configuration(db)
    configuration_store.save_draft(
        db, row, {"business_profile": {**row.business_profile, "name": "Dogwood Cycles"}}
    )
    db.commit()

    second = asyncio.run(publisher.publish(db, published_by="admin@example.com"))

    assert len(push_ok) == 2
    assert push_ok.instructions[-1] == second.instructions_text
    assert "Dogwood Cycles" in push_ok.instructions[-1]


def test_a_knowledge_title_appears_in_the_instructions_publish_sends(db, push_ok):
    asyncio.run(publisher.publish(db, published_by="admin@example.com"))
    sent = push_ok.instructions[0]
    from app.guide_publish import render as render_module

    titles = render_module.knowledge_topics(
        publisher._knowledge_items(db), __import__("datetime").date.today()
    )
    assert titles, "the seed has publishable knowledge"
    assert all(title in sent for title in titles)


def test_adding_or_renaming_knowledge_changes_the_pushed_instructions(db, push_ok):
    from datetime import datetime

    asyncio.run(publisher.publish(db, published_by="admin@example.com"))
    item = models.KnowledgeItem(
        id="k-topic",
        organization_id=config.DEFAULT_ORGANIZATION_ID,
        title="Winter hours",
        type="policy", status="active", source="Manual entry",
        content="We close early in January.", tags=[],
        updated_at=datetime.utcnow(),
    )
    db.add(item)
    db.commit()

    asyncio.run(publisher.publish(db, published_by="admin@example.com"))
    assert len(push_ok) == 2, "a new topic must push, not be treated as a no-op"
    assert "Winter hours" in push_ok.instructions[1]
    assert "Winter hours" not in push_ok.instructions[0]

    item.title = "Holiday hours"
    db.commit()
    asyncio.run(publisher.publish(db, published_by="admin@example.com"))
    assert len(push_ok) == 3
    assert "Holiday hours" in push_ok.instructions[2]
    assert "Winter hours" not in push_ok.instructions[2]
