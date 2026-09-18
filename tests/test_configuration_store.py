"""CRUD for the single console configuration row. Same conventions as
app/workflow_store.py: a Session in, no commit -- the caller owns the
transaction boundary."""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import configuration_store
from app.db import Base


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_first_read_seeds_the_bike_shop(db):
    row = configuration_store.get_configuration(db)
    assert row.business_profile["name"] == "Peachtree Pedals"
    assert row.has_unpublished_changes is False
    assert row.last_published_at is None


def test_second_read_returns_the_same_row(db):
    first = configuration_store.get_configuration(db)
    first.business_profile = {**first.business_profile, "name": "Changed"}
    db.commit()
    assert configuration_store.get_configuration(db).business_profile["name"] == "Changed"


def test_save_draft_replaces_a_section_without_touching_siblings(db):
    row = configuration_store.get_configuration(db)
    original_profile_name = row.business_profile["name"]

    configuration_store.save_draft(db, row, {"identity": {"greeting": "Hello there"}})

    assert row.identity == {"greeting": "Hello there"}
    assert row.business_profile["name"] == original_profile_name
    assert row.has_unpublished_changes is True


def test_save_draft_rejects_unknown_sections(db):
    row = configuration_store.get_configuration(db)
    with pytest.raises(ValueError, match="unknown configuration section"):
        configuration_store.save_draft(db, row, {"nonsense": {}})


def test_mark_published_clears_the_draft_flag(db):
    row = configuration_store.get_configuration(db)
    configuration_store.save_draft(db, row, {"identity": {"greeting": "Hi"}})
    published_at = datetime(2026, 9, 18, 12, 0, 0)

    configuration_store.mark_published(db, row, published_at)

    assert row.has_unpublished_changes is False
    assert row.last_published_at == published_at
