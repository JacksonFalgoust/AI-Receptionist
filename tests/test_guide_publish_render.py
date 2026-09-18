"""Console rows -> the strings and files that go into a guide bundle.

The golden test here is the safety net for the whole pipeline: if
rendering the seeded configuration no longer reproduces the authored
instructions byte-for-byte, the first publish is no longer a no-op and
something changed that a caller will hear.
"""

from datetime import date, datetime

import pytest

from app import config, models
from app.guide_publish import render, template


def _configuration(**overrides):
    fields = dict(
        organization_id="org-1",
        business_profile=dict(config.DEFAULT_BUSINESS_PROFILE),
        identity=dict(config.DEFAULT_IDENTITY),
        terminology=dict(config.DEFAULT_TERMINOLOGY),
    )
    fields.update(overrides)
    return models.ConciergeConfiguration(**fields)


def _item(**overrides):
    fields = dict(
        id="k1",
        organization_id="org-1",
        title="Damage policy",
        type="policy",
        status="active",
        source="Manual entry",
        content="Riders are responsible for damage beyond normal wear.",
        tags=["damage"],
        updated_at=datetime(2026, 9, 1),
    )
    fields.update(overrides)
    return models.KnowledgeItem(**fields)


# --- the golden test ------------------------------------------------------

def test_seeded_configuration_reproduces_the_authored_instructions():
    """Rendering the seed must equal the instructions the guide runs today.
    If this fails, either the seed in app/config.py or a slot in
    instructions.template.md drifted -- fix the drift, do not update this
    assertion to match."""
    rendered = template.render_instructions(render.build_slots(_configuration()))

    assert "Peachtree Pedals" in rendered
    assert "a bike rental shop in Atlanta, Georgia" in rendered
    assert "every day, nine A M to six P M" in rendered
    assert "1234 Road Pkwy, Atlanta, GA" in rendered
    assert "warm, upbeat, and polite" in rendered
    assert "{{" not in rendered  # every slot filled
    # The authored contract survives rendering untouched.
    assert "FINAL ANSWER MARKER" in rendered
    assert "Declare victory." in rendered
    assert "findReservations" in rendered


def test_changing_hours_changes_the_rendered_instructions():
    configuration = _configuration(
        business_profile={
            **config.DEFAULT_BUSINESS_PROFILE,
            "hours": [
                {"day": 0, "closed": True},
                *[
                    {"day": d, "open": "10:00", "close": "16:00", "closed": False}
                    for d in range(1, 7)
                ],
            ],
        }
    )
    rendered = template.render_instructions(render.build_slots(configuration))
    assert "ten A M to four P M" in rendered
    assert "every day, nine A M to six P M" not in rendered


# --- slot discipline ------------------------------------------------------

def test_unfilled_slot_raises():
    with pytest.raises(template.SlotError, match="unfilled"):
        template.render_instructions({"business.name": "X"})


def test_unknown_slot_raises():
    slots = render.build_slots(_configuration())
    slots["business.nonsense"] = "boom"
    with pytest.raises(template.SlotError, match="unknown"):
        template.render_instructions(slots)


@pytest.mark.parametrize(
    "bad",
    [
        "**Peachtree**",
        "Peach_tree",
        "# Peachtree",
        "- Peachtree",
        "Peach`tree`",
        "• Peachtree",
        "Peach[tree]",
        "Peach<tree>",
    ],
)
def test_markdown_in_a_slot_value_is_rejected(bad):
    """Slot values are spoken aloud; instructions.md forbids markup and a
    caller would hear the symbols read out."""
    configuration = _configuration(
        business_profile={**config.DEFAULT_BUSINESS_PROFILE, "name": bad}
    )
    with pytest.raises(ValueError, match="business.name"):
        render.build_slots(configuration)


# --- knowledge ------------------------------------------------------------

def test_active_in_window_item_is_publishable():
    assert render.is_publishable(_item(), date(2026, 9, 18)) is True


def test_item_effective_today_is_publishable():
    """An item with effective_date set to exactly today is publishable."""
    item = _item(effective_date=datetime(2026, 9, 18))
    assert render.is_publishable(item, date(2026, 9, 18)) is True


def test_item_expiring_today_is_publishable():
    """An item with expiration_date set to exactly today is publishable."""
    item = _item(expiration_date=datetime(2026, 9, 18))
    assert render.is_publishable(item, date(2026, 9, 18)) is True


@pytest.mark.parametrize("status", ["disabled", "error", "needs_review", "processing"])
def test_non_active_item_is_not_publishable(status):
    assert render.is_publishable(_item(status=status), date(2026, 9, 18)) is False


def test_item_outside_its_effective_window_is_not_publishable():
    future = _item(effective_date=datetime(2026, 12, 1))
    expired = _item(expiration_date=datetime(2026, 1, 1))
    assert render.is_publishable(future, date(2026, 9, 18)) is False
    assert render.is_publishable(expired, date(2026, 9, 18)) is False


def test_knowledge_files_are_keyed_by_deterministic_path():
    files = render.knowledge_files([_item()], date(2026, 9, 18))
    assert list(files) == ["VectorStores/default/k1.md"]
    body = files["VectorStores/default/k1.md"].decode()
    assert "Damage policy" in body
    assert "normal wear" in body


def test_unpublishable_items_are_absent_from_the_bundle():
    files = render.knowledge_files(
        [_item(id="k1"), _item(id="k2", status="disabled")], date(2026, 9, 18)
    )
    assert list(files) == ["VectorStores/default/k1.md"]


def test_static_files_include_both_tool_schemas_and_the_manifest():
    files = template.load_static_files()
    assert "manifest.json" in files
    assert "OpenAPI/voice-receptionist.json" in files
    assert "OpenAPI/caller-phone.json" in files
    assert "HostExtensions/UI/contextOptions.json" in files
