"""Console rows -> the strings and files that go into a guide bundle.

The template is generic (any business). The business and identity slots
come from Configuration and `{{knowledge.topics}}` lists the titles of the
knowledge items Publish sends; the rendering test below checks those land
and that the authored contract (marker, tool names) survives.
"""

import re
from datetime import date, datetime

import pytest

from app import config, models
from app.guide.publish import render, template


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

    assert "Atlanta Bikes" in rendered
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


# --- workflows ------------------------------------------------------------

def _step(**overrides):
    fields = dict(
        id="s1",
        name="Pickup day",
        description="ask which day they would like to pick up",
        type="ask_customer",
    )
    fields.update(overrides)
    return fields


def _workflow(**overrides):
    fields = dict(
        id="w1",
        organization_id="org-1",
        name="Book it",
        description="Taking a new reservation",
        applies_when="when a caller asks to make a reservation",
        status="active",
        version=2,
        steps=[_step()],
        execution_count=0,
        last_updated_at=datetime(2026, 11, 1),
    )
    fields.update(overrides)
    return models.Workflow(**fields)


def _steps(count, **overrides):
    return [_step(id=f"s{n}", name=f"Part {n}", **overrides) for n in range(1, count + 1)]


def test_no_workflows_renders_none():
    assert render.workflow_prose([]) == ("none", [])


def test_draft_and_inactive_workflows_are_absent():
    prose, warnings = render.workflow_prose(
        [
            _workflow(id="a", name="Drafted", status="draft"),
            _workflow(id="b", name="Switched off", status="inactive"),
        ]
    )
    assert (prose, warnings) == ("none", [])

    prose, _ = render.workflow_prose(
        [_workflow(id="a", name="Drafted", status="draft"), _workflow(id="c", name="Live one")]
    )
    assert "Live one" in prose
    assert "Drafted" not in prose


@pytest.mark.parametrize("applies_when", [None, "", "   ", "**"])
def test_active_workflow_with_blank_applies_when_is_skipped_with_a_warning(applies_when):
    prose, warnings = render.workflow_prose([_workflow(applies_when=applies_when)])
    assert prose == "none"
    assert warnings == [
        "Workflow 'Book it' is active but has no 'Applies when', so the guide does not see it."
    ]


def test_active_workflow_with_no_steps_is_skipped_with_a_warning():
    """The console refuses to publish a workflow with no steps, but an
    active one can still be edited down to none. A procedure with nothing
    to follow is not worth a paragraph of the prompt."""
    prose, warnings = render.workflow_prose([_workflow(steps=[])])
    assert prose == "none"
    assert warnings == [
        "Workflow 'Book it' is active but has no steps, so the guide does not see it."
    ]


def test_a_skipped_workflow_does_not_hide_the_others():
    prose, warnings = render.workflow_prose(
        [_workflow(id="a", name="Legacy", applies_when=None), _workflow(id="b", name="Book it")]
    )
    assert prose.startswith("WORKFLOW: Book it.")
    assert "Legacy" not in prose
    assert len(warnings) == 1 and "Legacy" in warnings[0]


def test_workflow_prose_names_trigger_and_numbers_steps_in_order():
    prose, warnings = render.workflow_prose(
        [
            _workflow(
                steps=[
                    _step(id="s1", name="Pickup day"),
                    _step(id="s2", name="Which item", type="look_up"),
                    _step(id="s3", name="Recap", type="confirm"),
                ]
            )
        ]
    )
    assert warnings == []
    assert "Book it" in prose
    assert "when a caller asks to make a reservation" in prose
    one, two, three = (prose.index(f"Step {n}:") for n in ("one", "two", "three"))
    assert one < two < three
    assert prose.index("Pickup day") < prose.index("Which item") < prose.index("Recap")
    assert prose.startswith(
        "WORKFLOW: Book it. Use it when a caller asks to make a reservation. "
        "Follow these steps in order, one question per turn. Step one: "
    )
    assert not any(ch.isdigit() for ch in prose)  # digits read badly aloud


def test_twenty_steps_are_spelled_out_and_twenty_one_raise():
    prose, _ = render.workflow_prose([_workflow(steps=_steps(20))])
    assert "Step twenty:" in prose
    assert "Step nineteen:" in prose

    with pytest.raises(ValueError, match="at most 20"):
        render.workflow_prose([_workflow(steps=_steps(21))])


def test_step_type_hint_and_tool_are_rendered():
    prose, _ = render.workflow_prose(
        [
            _workflow(
                steps=[
                    _step(id="s1", name="Day", type="ask_customer"),
                    _step(id="s2", name="Stock", type="look_up", tool="checkAvailability"),
                    _step(id="s3", name="Phone", type="look_up", tool="get_caller_phone_number"),
                    _step(id="s4", name="Recap", type="confirm"),
                    _step(id="s5", name="Wrap up", type="end", description="say goodbye"),
                ]
            )
        ]
    )
    assert "Ask the caller for this." in prose
    assert "Look this up using the checkAvailability tool." in prose
    assert "Look this up using the get_caller_phone_number tool." in prose
    assert "Read it back and ask the caller to confirm." in prose
    assert "Step five: Wrap up. say goodbye. Say a short goodbye, then end the call." in prose


@pytest.mark.parametrize(
    "step_type, hint",
    [
        ("validate", "Check this."),
        ("look_up", "Look this up."),
        ("make_decision", "Decide this."),
        ("execute_action", "Carry this out."),
        ("send_communication", "Send the caller a message."),
        ("escalate", "Offer to have a team member call back."),
    ],
)
def test_every_other_step_type_has_a_spoken_hint(step_type, hint):
    prose, _ = render.workflow_prose(
        [_workflow(steps=[_step(type=step_type, name="Thing", description="")])]
    )
    assert f"Step one: Thing. {hint}" in prose


def test_end_step_with_end_call_tool_does_not_repeat_itself():
    prose, _ = render.workflow_prose(
        [_workflow(steps=[_step(type="end", tool="endCall", name="Goodbye", description="")])]
    )
    step_line = prose[prose.index("Step one:"):]
    assert step_line == "Step one: Goodbye. Say a short goodbye, then end the call."
    assert step_line.lower().count("end the call") == 1
    assert "endCall" not in step_line


def test_end_call_tool_on_another_step_type_is_still_named():
    """Tool and type are independent: only the end/endCall pair collapses."""
    prose, _ = render.workflow_prose(
        [_workflow(steps=[_step(type="escalate", tool="endCall", name="Hand off", description="")])]
    )
    assert "Offer to have a team member call back using the endCall tool." in prose


def test_error_and_escalation_behavior_are_rendered():
    prose, _ = render.workflow_prose(
        [
            _workflow(
                steps=[
                    _step(
                        errorBehavior="offer the next open day",
                        escalationBehavior="take a callback",
                    )
                ]
            )
        ]
    )
    assert "If this step fails: offer the next open day." in prose
    assert "If that does not resolve it: take a callback." in prose
    assert prose.index("If this step fails") < prose.index("If that does not resolve it")


def test_escalation_without_error_behavior_is_what_to_do_on_failure():
    """"If that does not resolve it" needs something before it to refer to."""
    prose, _ = render.workflow_prose(
        [_workflow(steps=[_step(errorBehavior="  ", escalationBehavior="take a callback")])]
    )
    assert "If this step fails: take a callback." in prose
    assert "If that does not resolve it" not in prose


def test_trailing_punctuation_in_admin_text_is_not_doubled():
    prose, _ = render.workflow_prose(
        [
            _workflow(
                name="Book it.",
                applies_when="when a caller asks to make a reservation.",
                steps=[_step(description="ask which day.", errorBehavior="take a callback!")],
            )
        ]
    )
    assert ".." not in prose
    assert "!." not in prose
    assert "Use it when a caller asks to make a reservation. Follow" in prose


def test_markup_in_admin_text_is_replaced_not_rejected():
    prose, warnings = render.workflow_prose(
        [
            _workflow(
                name="**Book** [it]",
                applies_when="when {{x}} asks",
                steps=[
                    _step(
                        name="# Day <one>",
                        description="ask the_day\n- then - - the `time` • here",
                        errorBehavior="_retry_ {once}",
                        escalationBehavior="- callback",
                    )
                ],
            )
        ]
    )
    assert warnings == []
    assert not render._FORBIDDEN.search(prose)
    assert "{{" not in prose and "}}" not in prose
    assert "{" not in prose and "}" not in prose
    assert prose.startswith("WORKFLOW: Book it. Use it when x asks.")
    assert "\n" not in prose  # one paragraph per workflow


def test_unknown_tool_refuses_rather_than_naming_a_tool_the_guide_lacks():
    """Tool names are inserted unstripped (get_caller_phone_number keeps its
    underscores), which is only safe for the guide's own tool list."""
    with pytest.raises(ValueError, match="bookTable"):
        render.workflow_prose([_workflow(steps=[_step(tool="bookTable")])])


def test_workflows_are_ordered_by_name_then_id():
    a = _workflow(id="a", name="Book it", applies_when="when first")
    b = _workflow(id="b", name="Book it", applies_when="when second")
    c = _workflow(id="c", name="apple pickup", applies_when="when apples")
    first = render.workflow_prose([b, c, a])
    second = render.workflow_prose([a, b, c])
    assert first == second
    prose = first[0]
    assert prose.index("when apples") < prose.index("when first") < prose.index("when second")
    assert prose.count("\n\n") == 2  # paragraphs separated by a blank line


def test_over_the_cap_raises_naming_the_cap():
    long = "describe this part of the procedure in a great deal of detail " * 6
    workflows = [
        _workflow(id=f"w{n}", name=f"Flow {n}", steps=_steps(5, description=long))
        for n in range(4)
    ]
    with pytest.raises(ValueError, match="6000") as excinfo:
        render.workflow_prose(workflows)
    assert re.search(r"\d+ characters", str(excinfo.value))


def test_build_slots_includes_workflows_prose_and_template_accepts_it():
    slots = render.build_slots(_configuration(), [])
    assert slots["workflows.prose"] == "none"
    rendered = template.render_instructions(slots)
    assert "WORKFLOWS:" in rendered
    assert "{{" not in rendered

    prose, _ = render.workflow_prose([_workflow()])
    rendered = template.render_instructions(
        render.build_slots(_configuration(), [], workflows_prose=prose)
    )
    assert prose in rendered
    # The precedence sentence follows the procedures, not the generic text.
    assert rendered.index(prose) < rendered.index("instead of the generic RESERVATIONS")
    assert rendered.index("BOOKING STEPS (follow in order") < rendered.index("WORKFLOWS:")


def test_steps_read_as_short_sentences_with_hint_after_the_text():
    prose, _ = render.workflow_prose(
        [
            _workflow(
                steps=[
                    _step(name="Ask what they want to reserve",
                          description="Get the item, dates and times"),
                    _step(name="Check availability", description="See if it is free",
                          type="look_up", tool="checkAvailability"),
                    _step(name="Confirm the details", description="Read back the reservation.",
                          type="confirm"),
                ]
            )
        ]
    )
    assert (
        "Step one: Ask what they want to reserve. Get the item, dates and times. "
        "Ask the caller for this. "
        "Step two: Check availability. See if it is free. "
        "Look this up using the checkAvailability tool. "
        "Step three: Confirm the details. Read back the reservation. "
        "Read it back and ask the caller to confirm."
    ) in prose


def test_step_with_no_name_or_description_renders_the_hint_alone():
    prose, _ = render.workflow_prose([_workflow(steps=[_step(name="", description="")])])
    assert prose.endswith("Step one: Ask the caller for this.")
    assert ": ." not in prose


def test_step_with_nothing_to_say_has_no_dangling_colon():
    prose, _ = render.workflow_prose(
        [_workflow(steps=[_step(type="bogus", name="", description="")])]
    )
    assert prose.endswith("Step one.")


def test_capitalized_applies_when_is_lowercased_at_the_first_character_only():
    prose, _ = render.workflow_prose(
        [_workflow(applies_when="When a caller asks about NYC pickups")]
    )
    assert "Use it when a caller asks about NYC pickups. " in prose


def test_end_step_says_goodbye_first():
    prose, _ = render.workflow_prose(
        [_workflow(steps=[_step(type="end", name="Wrap up", description="")])]
    )
    assert prose.endswith("Step one: Wrap up. Say a short goodbye, then end the call.")


def test_template_places_none_sentence_before_the_slot():
    text = template.render_instructions(render.build_slots(_configuration(), []))
    assert (
        "If the procedures below say none, there are none to follow.\n"
        "none\n"
    ) in text
    assert "list above says none, there are no procedures" not in text


@pytest.mark.parametrize(
    "trigger, expected",
    [
        ("When a caller asks to make a reservation", "Use it when a caller asks to make a reservation."),
        ("a caller wants to cancel", "Use it when a caller wants to cancel."),
        ("VIP callers call", "Use it when VIP callers call."),
        ("If the caller is upset", "Use it if the caller is upset."),
    ],
)
def test_trigger_wording_reads_as_a_sentence(trigger, expected):
    prose, _ = render.workflow_prose([_workflow(applies_when=trigger)])
    assert f". {expected} Follow" in prose
