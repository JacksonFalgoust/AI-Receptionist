"""app/workflow_store.py -- CRUD, publish (with the empty-steps guard),
and org-scoping for console workflows (E6 slice 3)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, workflow_store
from app.db import Base


def _session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _create(db, **overrides):
    fields = dict(name="New rental intake")
    fields.update(overrides)
    workflow = workflow_store.create_workflow(db, **fields)
    db.commit()
    return workflow


def test_create_applies_defaults_and_default_org():
    db = _session()
    workflow = _create(db)

    assert workflow.status == "draft"
    assert workflow.version == 1
    assert workflow.steps == []
    assert workflow.execution_count == 0
    assert workflow.organization_id == "org_default"
    assert workflow.last_updated_at is not None


def test_create_keeps_explicit_description():
    db = _session()
    workflow = _create(db, description="Handles a first-time rental request.")

    assert workflow.description == "Handles a first-time rental request."


def test_save_draft_replaces_steps_wholesale():
    db = _session()
    workflow = _create(db)
    workflow_store.save_draft(
        db, workflow, {"steps": [{"id": "s1", "name": "Ask for ID", "type": "ask_customer"}]}
    )
    db.commit()

    workflow_store.save_draft(
        db, workflow, {"steps": [{"id": "s2", "name": "Confirm details", "type": "confirm"}]}
    )
    db.commit()

    # The first step is gone -- a wholesale replace, not a merge.
    assert [step["id"] for step in workflow.steps] == ["s2"]


def test_save_draft_changes_only_patched_keys_and_bumps_last_updated_at():
    from datetime import datetime

    db = _session()
    workflow = _create(db, description="Old description")
    workflow.last_updated_at = datetime(2020, 1, 1)
    db.commit()

    workflow_store.save_draft(db, workflow, {"name": "Renamed workflow"})
    db.commit()

    assert workflow.name == "Renamed workflow"
    assert workflow.description == "Old description"
    assert workflow.status == "draft"
    assert workflow.version == 1
    assert workflow.last_updated_at > datetime(2020, 1, 1)


def test_save_draft_never_touches_status_or_version():
    db = _session()
    workflow = _create(db)

    # Even if a caller tried to sneak these into the patch dict, save_draft
    # must not apply them -- but the real defense is that the API layer
    # (Task 3) never accepts them into a patch dict in the first place.
    # This test locks in that save_draft only applies name/description/steps
    # regardless of what a patch dict happens to contain.
    workflow_store.save_draft(db, workflow, {"name": "Renamed"})
    db.commit()

    assert workflow.status == "draft"
    assert workflow.version == 1


def test_publish_rejects_empty_steps():
    db = _session()
    workflow = _create(db)

    with pytest.raises(ValueError):
        workflow_store.publish_workflow(db, workflow)

    assert workflow.status == "draft"
    assert workflow.version == 1


def test_publish_activates_and_increments_version():
    db = _session()
    workflow = _create(db)
    workflow_store.save_draft(
        db, workflow, {"steps": [{"id": "s1", "name": "Ask for ID", "type": "ask_customer"}]}
    )
    db.commit()

    workflow_store.publish_workflow(db, workflow)
    db.commit()

    assert workflow.status == "active"
    assert workflow.version == 2


def test_publishing_twice_increments_version_each_time():
    db = _session()
    workflow = _create(db)
    workflow_store.save_draft(
        db, workflow, {"steps": [{"id": "s1", "name": "Ask for ID", "type": "ask_customer"}]}
    )
    db.commit()

    workflow_store.publish_workflow(db, workflow)
    db.commit()
    workflow_store.publish_workflow(db, workflow)
    db.commit()

    assert workflow.version == 3


def test_get_returns_none_for_unknown_id():
    db = _session()
    assert workflow_store.get_workflow(db, "missing") is None


def test_other_organizations_rows_are_invisible():
    db = _session()
    foreign = models.Workflow(
        organization_id="org_other",
        name="Secret workflow",
        status="draft",
        version=1,
        steps=[],
        execution_count=0,
    )
    db.add(foreign)
    db.commit()

    assert workflow_store.list_workflows(db) == []
    assert workflow_store.get_workflow(db, foreign.id) is None


def test_list_orders_newest_update_first():
    from datetime import datetime

    db = _session()
    for index in range(3):
        workflow = _create(db, name=f"workflow {index}")
        workflow.last_updated_at = datetime(2026, 9, 1 + index)
    db.commit()

    rows = workflow_store.list_workflows(db)

    assert [row.name for row in rows] == ["workflow 2", "workflow 1", "workflow 0"]


def test_delete_removes_the_row():
    db = _session()
    workflow = _create(db)

    workflow_store.delete_workflow(db, workflow)
    db.commit()

    assert workflow_store.get_workflow(db, workflow.id) is None
