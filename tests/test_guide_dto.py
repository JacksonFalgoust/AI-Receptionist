"""The DTO mapping and the safety guards around the read-modify-write PUT.

tests/fixtures/guide_detail.json is a real GET /api/guides/{id} body from a
GuideAnts scratch guide built as a faithful replica of the live one (two
custom tools carrying nine operations, a context option, one indexed
knowledge file), with the long strings trimmed. Everything here is pure --
nothing touches a network.
"""

import copy
import json
import pathlib

import pytest

from app.guide_publish import guide_dto

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "guide_detail.json"


@pytest.fixture
def detail():
    return json.loads(FIXTURE.read_text())


# --------------------------------------------------------------------------
# unsupported_features -- the fail-closed guard
# --------------------------------------------------------------------------


def test_a_realistic_guide_is_supported(detail):
    assert guide_dto.unsupported_features(detail) == []


def test_shared_tools_are_unsupported(detail):
    detail["tools"] = [{"id": "t1", "name": "Web search"}]
    reasons = guide_dto.unsupported_features(detail)
    assert len(reasons) == 1
    assert "shared tool" in reasons[0]


def test_a_crew_member_count_is_unsupported(detail):
    detail["guide"]["crewMemberCount"] = 2
    assert any("crew member" in reason for reason in guide_dto.unsupported_features(detail))


def test_crew_members_are_unsupported(detail):
    detail["crews"][0]["members"] = [{"id": "m1"}]
    reasons = guide_dto.unsupported_features(detail)
    assert any("member" in reason for reason in reasons)
    # The crew's name is in the message so an admin can find it.
    assert any(detail["crews"][0]["name"] in reason for reason in reasons)


def test_an_empty_crew_is_supported(detail):
    """The live guide has exactly this: one auto-created, empty crew."""
    assert detail["crews"][0]["members"] == []
    assert guide_dto.unsupported_features(detail) == []


@pytest.mark.parametrize(
    "key, value",
    [
        ("authProviders", [{"id": "ap1"}]),
        ("skills", [{"name": "search"}]),
        ("environmentVariables", [{"key": "TOKEN", "value": "x"}]),
    ],
)
def test_truthy_extension_fields_are_unsupported(detail, key, value):
    detail[key] = value
    assert guide_dto.unsupported_features(detail), key


def test_an_enabled_sandbox_is_unsupported(detail):
    detail["sandboxWireApiConfig"] = {"enabled": True, "baseUrl": None}
    assert any("sandbox" in r for r in guide_dto.unsupported_features(detail))


def test_a_disabled_sandbox_with_settings_is_unsupported(detail):
    detail["sandboxWireApiConfig"] = {"enabled": False, "baseUrl": "http://sandbox"}
    reasons = guide_dto.unsupported_features(detail)
    assert any("baseUrl" in r for r in reasons)


def test_a_purely_disabled_sandbox_is_supported(detail):
    detail["sandboxWireApiConfig"] = {"enabled": False, "baseUrl": None}
    assert guide_dto.unsupported_features(detail) == []


def test_every_reason_is_reported_not_just_the_first(detail):
    detail["tools"] = [{"id": "t1"}]
    detail["skills"] = [{"name": "s"}]
    detail["guide"]["crewMemberCount"] = 1
    assert len(guide_dto.unsupported_features(detail)) == 3


# --------------------------------------------------------------------------
# build_update_dto
# --------------------------------------------------------------------------


def test_the_dto_changes_only_the_instructions(detail):
    dto = guide_dto.build_update_dto(detail, "NEW INSTRUCTIONS")

    assert dto["instructions"] == "NEW INSTRUCTIONS"
    assert dto["name"] == detail["guide"]["name"]
    assert dto["description"] == detail["guide"]["description"]
    assert dto["modelId"] == detail["guide"]["modelId"]
    assert dto["customTools"] == detail["customTools"]
    assert dto["contextOptions"] == detail["contextOptions"]
    assert dto["conversationStarters"] == detail["conversationStarters"]
    assert dto["maxToolCallsPerTurn"] == detail["maxToolCallsPerTurn"]


def test_existing_files_are_kept_by_id(detail):
    """The property that keeps the vector-store index alive: name every
    existing file, add none. An omitted file is deleted and re-indexing it
    would cost minutes of a guide that cannot answer."""
    dto = guide_dto.build_update_dto(detail, "x")
    assert dto["fileIdsToKeep"] == [f["id"] for f in detail["files"]]
    assert dto["fileIdsToKeep"]
    assert dto["filesToAdd"] == []


def test_tool_ids_come_from_shared_tools(detail):
    assert guide_dto.build_update_dto(detail, "x")["toolIds"] == []
    detail["tools"] = [{"id": "t1"}, {"id": "t2"}]
    assert guide_dto.build_update_dto(detail, "x")["toolIds"] == ["t1", "t2"]


def test_the_dto_carries_every_field_the_update_record_declares(detail):
    assert set(guide_dto.build_update_dto(detail, "x")) == {
        "name", "description", "instructions", "homePageMarkdown", "modelId",
        "temperature", "topP", "reasoningEffort", "toolIds", "customTools",
        "contextOptions", "authProviders", "fileIdsToKeep", "filesToAdd",
        "conversationStarters", "crewMemberIds", "environmentVariables",
        "skills", "sandboxWireApiConfig", "maxToolCallsPerTurn",
    }


# --------------------------------------------------------------------------
# comparable
# --------------------------------------------------------------------------


def test_comparable_ignores_the_instructions(detail):
    other = copy.deepcopy(detail)
    other["instructions"] = "something else entirely"
    assert guide_dto.comparable(detail) == guide_dto.comparable(other)


def test_comparable_ignores_the_updated_timestamp(detail):
    other = copy.deepcopy(detail)
    other["guide"]["updated"] = "2030-01-01T00:00:00"
    assert guide_dto.comparable(detail) == guide_dto.comparable(other)


def test_comparable_ignores_reordered_tools_and_operations(detail):
    """GuideAnts hands the operations back in a different order on every
    read. Without this, every publish would look like a failure."""
    other = copy.deepcopy(detail)
    other["customTools"].reverse()
    for tool in other["customTools"]:
        tool["operations"].reverse()
    assert other["customTools"] != detail["customTools"]
    assert guide_dto.comparable(detail) == guide_dto.comparable(other)


def test_comparable_ignores_reminted_operation_ids(detail):
    other = copy.deepcopy(detail)
    for index, tool in enumerate(other["customTools"]):
        for position, operation in enumerate(tool["operations"]):
            operation["id"] = f"fresh-{index}-{position}"
    assert guide_dto.comparable(detail) == guide_dto.comparable(other)


def test_comparable_ignores_file_ids_and_shadow_churn(detail):
    other = copy.deepcopy(detail)
    other["files"][0]["id"] = "regenerated"
    other["files"][0]["created"] = "2030-01-01T00:00:00"
    other["files"][0]["markdownShadow"]["id"] = "regenerated-shadow"
    other["files"][0]["markdownShadow"]["processedAt"] = "2030-01-01T00:00:00"
    assert guide_dto.comparable(detail) == guide_dto.comparable(other)


def test_comparable_ignores_file_order(detail):
    other = copy.deepcopy(detail)
    extra = copy.deepcopy(detail["files"][0])
    extra["id"] = "second"
    extra["relativePath"] = "aaa-first-alphabetically.md"
    detail["files"].append(extra)
    other["files"].insert(0, extra)
    assert guide_dto.comparable(detail) == guide_dto.comparable(other)


def test_comparable_ignores_the_crew_id(detail):
    other = copy.deepcopy(detail)
    other["crews"][0]["crewId"] = "a-different-id"
    assert guide_dto.comparable(detail) == guide_dto.comparable(other)


def test_comparable_detects_a_missing_custom_tool(detail):
    """The exact damage the import endpoint did to the live guide."""
    other = copy.deepcopy(detail)
    other["customTools"] = []
    assert guide_dto.comparable(detail) != guide_dto.comparable(other)


def test_comparable_detects_a_missing_operation(detail):
    other = copy.deepcopy(detail)
    voice = next(t for t in other["customTools"] if len(t["operations"]) > 1)
    voice["operations"] = [
        o for o in voice["operations"] if o["operationId"] != "findReservations"
    ]
    assert guide_dto.comparable(detail) != guide_dto.comparable(other)


def test_comparable_detects_a_missing_context_option(detail):
    other = copy.deepcopy(detail)
    other["contextOptions"] = []
    assert guide_dto.comparable(detail) != guide_dto.comparable(other)


def test_comparable_detects_a_deleted_knowledge_file(detail):
    other = copy.deepcopy(detail)
    other["files"] = []
    assert guide_dto.comparable(detail) != guide_dto.comparable(other)


def test_comparable_detects_a_reindexed_file(detail):
    """A changed contentHash means the file was replaced, not preserved --
    which is a re-index, and a window where the guide cannot answer."""
    other = copy.deepcopy(detail)
    other["files"][0]["markdownShadow"]["contentHash"] = "0" * 64
    assert guide_dto.comparable(detail) != guide_dto.comparable(other)


def test_comparable_detects_a_cleared_model(detail):
    other = copy.deepcopy(detail)
    other["guide"]["modelId"] = None
    assert guide_dto.comparable(detail) != guide_dto.comparable(other)


def test_comparable_does_not_mutate_its_input(detail):
    original = copy.deepcopy(detail)
    guide_dto.comparable(detail)
    assert detail == original
