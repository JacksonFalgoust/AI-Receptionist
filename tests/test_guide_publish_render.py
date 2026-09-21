"""Console rows -> the strings and files that go into a guide bundle.

The template is generic (any business). The business and identity slots
come from Configuration and `{{knowledge.topics}}` lists the titles of the
knowledge items Publish sends; the rendering test below checks those land
and that the authored contract (marker, tool names) survives.
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


# --- rendering ------------------------------------------------------------

def test_seeded_configuration_fills_every_slot_and_keeps_the_contract():
    """The five business/identity slots and the topics slot land in the
    text, nothing is left unfilled, and the authored contract (final-answer
    marker, tool names) is untouched by rendering."""
    rendered = template.render_instructions(
        render.build_slots(_configuration(), ["Damage policy", "Bike Types"])
    )

    assert "Peachtree Pedals" in rendered
    assert "a bike rental shop in Atlanta, Georgia" in rendered
    assert "every day, nine A M to six P M" in rendered
    assert "1234 Road Pkwy, Atlanta, GA" in rendered
    assert "warm, upbeat, and polite" in rendered
    assert "Damage policy; Bike Types" in rendered
    assert "{{" not in rendered  # every slot filled
    assert "FINAL ANSWER MARKER" in rendered
    assert "Declare victory." in rendered
    for tool in (
        "listCatalog",
        "checkAvailability",
        "findReservations",
        "createCustomer",
        "sendPaymentLink",
        "get_caller_phone_number",
    ):
        assert tool in rendered


def test_template_stays_generic():
    """Business specifics belong in Configuration, never in the template."""
    assert "bike" not in template.INSTRUCTIONS_PATH.read_text(encoding="utf-8").lower()


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
    rendered = template.render_instructions(render.build_slots(configuration, []))
    assert "ten A M to four P M" in rendered
    assert "every day, nine A M to six P M" not in rendered


# --- slot discipline ------------------------------------------------------

def test_unfilled_slot_raises():
    with pytest.raises(template.SlotError, match="unfilled"):
        template.render_instructions({"business.name": "X"})


def test_unknown_slot_raises():
    slots = render.build_slots(_configuration(), [])
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
        render.build_slots(configuration, [])


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


def test_knowledge_files_are_named_after_the_title():
    files = render.knowledge_files([_item()], date(2026, 9, 18))
    assert list(files) == ["VectorStores/default/damage-policy.md"]
    body = files["VectorStores/default/damage-policy.md"].decode()
    assert "Damage policy" in body
    assert "normal wear" in body


def test_unpublishable_items_are_absent_from_the_bundle():
    files = render.knowledge_files(
        [_item(id="k1"), _item(id="k2", status="disabled")], date(2026, 9, 18)
    )
    assert list(files) == ["VectorStores/default/damage-policy.md"]


@pytest.mark.parametrize(
    "title, name",
    [
        ("Cancellations & Changes!", "cancellations-changes"),
        ("  Hours -- Weekend  ", "hours-weekend"),
        ("!!!", "untitled"),
        ("", "untitled"),
    ],
)
def test_file_names_are_slugs_of_the_title(title, name):
    files = render.knowledge_files([_item(title=title)], date(2026, 9, 18))
    assert list(files) == [f"VectorStores/default/{name}.md"]


def test_items_sharing_a_title_are_numbered_in_id_order():
    files = render.knowledge_files(
        [_item(id="b"), _item(id="c"), _item(id="a")], date(2026, 9, 18)
    )
    contents = {path: body for path, body in files.items()}
    assert sorted(contents) == [
        "VectorStores/default/damage-policy-2.md",
        "VectorStores/default/damage-policy-3.md",
        "VectorStores/default/damage-policy.md",
    ]
    # Same input in a different order gives the same names.
    again = render.knowledge_files(
        [_item(id="a"), _item(id="b"), _item(id="c")], date(2026, 9, 18)
    )
    assert list(again) == list(files)


def test_static_files_include_both_tool_schemas_and_the_manifest():
    files = template.load_static_files()
    assert "manifest.json" in files
    assert "OpenAPI/voice-receptionist.json" in files
    assert "OpenAPI/caller-phone.json" in files
    assert "HostExtensions/UI/contextOptions.json" in files


def test_incomplete_hours_name_the_field_like_every_other_slot_failure():
    """hours.py raises before _clean() runs, so without help the message
    would say only "business hours must cover all seven days" -- true, but
    it never names business.hours_prose the way every other 422 does."""
    profile = dict(config.DEFAULT_BUSINESS_PROFILE)
    profile["hours"] = profile["hours"][:3]

    with pytest.raises(ValueError) as excinfo:
        render.build_slots(_configuration(business_profile=profile), [])

    message = str(excinfo.value)
    assert message.startswith("business.hours_prose: ")
    assert "all seven days" in message


def test_a_day_missing_its_times_also_names_the_field():
    profile = dict(config.DEFAULT_BUSINESS_PROFILE)
    hours = [dict(entry) for entry in profile["hours"]]
    hours[2] = {"day": 2, "closed": False}
    profile["hours"] = hours

    with pytest.raises(ValueError, match=r"^business\.hours_prose: Tuesday is open"):
        render.build_slots(_configuration(business_profile=profile), [])


# --- knowledge topics -----------------------------------------------------

TODAY = date(2026, 9, 18)


def test_topics_are_the_titles_of_publishable_items_only():
    items = [
        _item(id="a", title="Damage policy"),
        _item(id="b", title="Old policy", status="disabled"),
        _item(id="c", title="Expired", expiration_date=datetime(2026, 1, 1)),
        _item(id="d", title="Future", effective_date=datetime(2026, 12, 1)),
    ]
    assert render.knowledge_topics(items, TODAY) == ["Damage policy"]


def test_topics_are_sorted_case_insensitively():
    items = [
        _item(id="a", title="zebra"),
        _item(id="b", title="Apple"),
        _item(id="c", title="banana"),
    ]
    assert render.knowledge_topics(items, TODAY) == ["Apple", "banana", "zebra"]


def test_topics_sanitize_forbidden_characters():
    items = [_item(id="a", title="**Rental** [FAQ]_v2"), _item(id="b", title="#  ")]
    topics = render.knowledge_topics(items, TODAY)
    assert topics == ["Rental FAQ v2"]
    assert not render._FORBIDDEN.search(topics[0])


def test_topics_drop_exact_duplicates():
    items = [_item(id="a", title="Hours"), _item(id="b", title="Hours")]
    assert render.knowledge_topics(items, TODAY) == ["Hours"]


def test_topics_slot_is_none_without_items():
    assert render.knowledge_topics([], TODAY) == []
    assert render.build_slots(_configuration(), [])["knowledge.topics"] == "none"


def test_topics_slot_joins_with_semicolons():
    slots = render.build_slots(_configuration(), ["A", "B"])
    assert slots["knowledge.topics"] == "A; B"


def test_rendered_instructions_contain_each_topic_title():
    items = [_item(id="a", title="Damage policy"), _item(id="b", title="Bike Types")]
    topics = render.knowledge_topics(items, TODAY)
    rendered = template.render_instructions(render.build_slots(_configuration(), topics))
    for title in ("Damage policy", "Bike Types"):
        assert title in rendered
