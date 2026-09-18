"""app/knowledge_store.py -- CRUD, filters, search, paging, and the
processing -> needs_review status rule (E6 slice 2)."""

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import knowledge_store, models
from app.db import Base


def _session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _create(db, **overrides):
    fields = dict(title="Damage policy", type="policy")
    fields.update(overrides)
    item = knowledge_store.create_item(db, **fields)
    db.commit()
    return item


def test_create_applies_defaults_and_default_org():
    db = _session()
    item = _create(db)

    assert item.status == "active"
    assert item.source == "Manual entry"
    assert item.tags == []
    assert item.organization_id == "org_default"
    assert item.updated_at is not None


def test_create_keeps_explicit_fields():
    db = _session()
    item = _create(
        db,
        type="url",
        status="disabled",
        source="https://example.com/faq",
        category="Web",
        content="Body",
        tags=["web"],
        effective_date=datetime(2026, 1, 1),
        expiration_date=datetime(2026, 12, 31),
    )

    assert (item.type, item.status, item.source) == ("url", "disabled", "https://example.com/faq")
    assert item.tags == ["web"]
    assert item.expiration_date == datetime(2026, 12, 31)


def test_create_records_requested_processing_as_needs_review():
    db = _session()
    item = _create(db, type="document", status="processing", source="menu.pdf")

    assert item.status == "needs_review"


def test_update_records_requested_processing_as_needs_review():
    db = _session()
    item = _create(db, type="document", source="menu.pdf")

    knowledge_store.update_item(db, item, {"status": "processing"})

    assert item.status == "needs_review"


def test_update_changes_only_patched_keys_and_bumps_updated_at():
    db = _session()
    item = _create(db, category="Policies", content="Old")
    item.updated_at = datetime(2020, 1, 1)
    db.commit()

    knowledge_store.update_item(db, item, {"content": "New", "category": None})
    db.commit()

    assert item.content == "New"
    assert item.category is None
    assert item.title == "Damage policy"
    assert item.updated_at > datetime(2020, 1, 1)


def test_get_returns_none_for_unknown_id():
    db = _session()
    assert knowledge_store.get_item(db, "missing") is None


def test_other_organizations_rows_are_invisible():
    db = _session()
    foreign = models.KnowledgeItem(
        organization_id="org_other",
        title="Secret",
        type="faq",
        status="active",
        source="Manual entry",
    )
    db.add(foreign)
    db.commit()

    rows, total = knowledge_store.list_items(db)

    assert (rows, total) == ([], 0)
    assert knowledge_store.get_item(db, foreign.id) is None


def test_list_filters_by_type_and_status():
    db = _session()
    _create(db, title="A", type="faq")
    _create(db, title="B", type="policy", status="disabled")
    _create(db, title="C", type="policy")

    rows, total = knowledge_store.list_items(db, type="policy", status="active")

    assert [r.title for r in rows] == ["C"]
    assert total == 1


def test_search_matches_each_text_field_case_insensitively():
    db = _session()
    _create(db, title="Helmet RULES")
    _create(db, title="t2", content="Deposits are refundable")
    _create(db, title="t3", category="Directions")
    _create(db, title="t4", type="url", source="https://peachtree.example/tours")
    _create(db, title="t5", tags=["e-bike", "battery"])
    _create(db, title="unrelated")

    def titles(term):
        return [r.title for r in knowledge_store.list_items(db, search=term)[0]]

    assert titles("helmet") == ["Helmet RULES"]
    assert titles("REFUNDABLE") == ["t2"]
    assert titles("direction") == ["t3"]
    assert titles("peachtree") == ["t4"]
    assert titles("battery") == ["t5"]
    assert titles("nothing-matches") == []


def test_list_orders_newest_update_first_and_paginates():
    db = _session()
    for index in range(5):
        item = _create(db, title=f"item {index}")
        item.updated_at = datetime(2026, 9, 1 + index)
    db.commit()

    page_one, total = knowledge_store.list_items(db, page=1, page_size=2)
    page_three, _ = knowledge_store.list_items(db, page=3, page_size=2)

    assert total == 5
    assert [r.title for r in page_one] == ["item 4", "item 3"]
    assert [r.title for r in page_three] == ["item 0"]


def test_delete_removes_the_row():
    db = _session()
    item = _create(db)

    knowledge_store.delete_item(db, item)
    db.commit()

    assert knowledge_store.get_item(db, item.id) is None
