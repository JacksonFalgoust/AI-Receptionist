"""The DTO mapping and the safety guards around the read-modify-write PUT.

tests/fixtures/guide_detail.json is a real GET /api/guides/{id} body from a
GuideAnts scratch guide built as a faithful replica of the live one (two
custom tools carrying nine operations, a context option, one indexed
knowledge file), with the long strings trimmed. Everything here is pure --
nothing touches a network.
"""

import base64
import copy
import hashlib
import json
import pathlib

import pytest

from app.guide_publish import guide_dto

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "guide_detail.json"


@pytest.fixture
def detail():
    return json.loads(FIXTURE.read_text())


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def vector_store_file(file_id: str, path: str, content: bytes | None, **overrides):
    """An existing file as the GET body reports it. `content` is what it was
    indexed FROM -- None means the shadow has no hash yet, which is what a
    file still being processed looks like."""
    file = {
        "id": file_id,
        "folderKind": "VectorStore",
        "vectorStoreName": "default",
        "relativePath": path,
        "contentType": "text/markdown",
        "created": "2026-09-21T00:00:00",
        "markdownShadow": None
        if content is None
        else {"status": "Completed", "contentHash": sha(content), "fileSize": len(content)},
    }
    file.update(overrides)
    return file


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


# --------------------------------------------------------------------------
# plan_file_sync -- which knowledge files survive a publish
#
# `fileIdsToKeep` is full-state: an omitted file is DELETED, and GuideAnts
# never hands back a stored file's bytes, so these decisions are one-way.
# --------------------------------------------------------------------------


def test_an_unchanged_file_is_kept_by_id_not_re_uploaded(detail):
    content = b"# Policies\n"
    detail["files"] = [vector_store_file("keep-me", "policies.md", content)]

    plan = guide_dto.plan_file_sync(detail, {"policies.md": content})

    assert plan.keep_ids == ["keep-me"]
    assert plan.adds == []
    assert plan.unchanged == ["policies.md"]
    assert (plan.added, plan.replaced, plan.removed) == ([], [], [])


def test_a_changed_file_is_dropped_and_re_added(detail):
    detail["files"] = [vector_store_file("old", "policies.md", b"# Old\n")]

    plan = guide_dto.plan_file_sync(detail, {"policies.md": b"# New\n"})

    assert plan.keep_ids == [], "the old id is not named, which is what deletes it"
    assert plan.replaced == ["policies.md"]
    assert plan.added == [] and plan.removed == [] and plan.unchanged == []
    assert plan.adds[0]["relativePath"] == "policies.md"


def test_a_new_file_is_added(detail):
    content = b"# Policies\n"
    detail["files"] = [vector_store_file("keep-me", "policies.md", content)]

    plan = guide_dto.plan_file_sync(
        detail, {"policies.md": content, "hours.md": b"# Hours\n"}
    )

    assert plan.keep_ids == ["keep-me"]
    assert plan.added == ["hours.md"]
    assert [add["relativePath"] for add in plan.adds] == ["hours.md"]


def test_a_file_the_console_no_longer_publishes_is_removed(detail):
    content = b"# Policies\n"
    detail["files"] = [
        vector_store_file("keep-me", "policies.md", content),
        vector_store_file("gone", "expired-promo.md", b"# Promo\n"),
    ]

    plan = guide_dto.plan_file_sync(detail, {"policies.md": content})

    assert plan.keep_ids == ["keep-me"]
    assert plan.removed == ["expired-promo.md"]
    assert plan.adds == []


def test_a_hand_uploaded_file_is_removed_too(detail):
    """Publish owns the whole vector store. A file nobody published through
    the console is still a file the console will delete -- this pins that
    it is a decision, not an accident."""
    detail["files"] = [vector_store_file("by-hand", "uploaded-in-guideants.md", b"x")]
    plan = guide_dto.plan_file_sync(detail, {"policies.md": b"# Policies\n"})
    assert plan.removed == ["uploaded-in-guideants.md"]
    assert plan.keep_ids == []


def test_a_file_with_no_content_hash_counts_as_changed(detail):
    """A shadow that is missing, empty or still processing tells us nothing.
    Keeping it would leave a half-indexed file in place forever."""
    for shadow in (None, {}, {"status": "Processing", "contentHash": None}):
        detail["files"] = [
            vector_store_file("unknown", "policies.md", None, markdownShadow=shadow)
        ]
        plan = guide_dto.plan_file_sync(detail, {"policies.md": b"# Policies\n"})
        assert plan.keep_ids == [], shadow
        assert plan.replaced == ["policies.md"], shadow


def test_the_hash_comparison_ignores_case(detail):
    content = b"# Policies\n"
    detail["files"] = [
        vector_store_file(
            "keep-me",
            "policies.md",
            None,
            markdownShadow={"status": "Completed", "contentHash": sha(content).upper()},
        )
    ]
    assert guide_dto.plan_file_sync(detail, {"policies.md": content}).keep_ids == ["keep-me"]


def test_only_the_first_matching_duplicate_path_is_kept(detail):
    content = b"# Policies\n"
    detail["files"] = [
        vector_store_file("first", "policies.md", content),
        vector_store_file("second", "policies.md", content),
    ]

    plan = guide_dto.plan_file_sync(detail, {"policies.md": content})

    assert plan.keep_ids == ["first"]
    assert plan.unchanged == ["policies.md"]
    assert plan.adds == [], "the duplicate is dropped, not re-uploaded"


def test_folder_kinds_publish_does_not_own_are_ignored_by_the_plan(detail):
    detail["files"] = [
        vector_store_file("sheet", "data.csv", b"a,b\n", folderKind="CodeInterpreter"),
    ]

    plan = guide_dto.plan_file_sync(detail, {"policies.md": b"# Policies\n"})

    assert plan.removed == [], "another folder kind is never deleted by Publish"
    assert plan.would_delete_everything is False
    assert guide_dto.non_vector_store_file_ids(detail) == {"sheet"}
    assert guide_dto.vector_store_paths(detail) == []


def test_the_folder_kind_is_matched_case_insensitively(detail):
    content = b"# Policies\n"
    detail["files"] = [
        vector_store_file("keep-me", "policies.md", content, folderKind="vectorstore")
    ]
    assert guide_dto.plan_file_sync(detail, {"policies.md": content}).keep_ids == ["keep-me"]


def test_wiping_the_whole_vector_store_is_flagged(detail):
    detail["files"] = [vector_store_file("only", "policies.md", b"x")]
    assert guide_dto.plan_file_sync(detail, {}).would_delete_everything is True


def test_an_empty_guide_and_an_empty_console_is_not_a_wipe(detail):
    detail["files"] = []
    plan = guide_dto.plan_file_sync(detail, {})
    assert plan.would_delete_everything is False
    assert plan.keep_ids == [] and plan.adds == []


def test_an_upload_entry_carries_base64_content_and_the_folder(detail):
    detail["files"] = []
    content = "# Hours\n\nOpen every day.\n".encode()

    plan = guide_dto.plan_file_sync(detail, {"hours.md": content})

    assert plan.adds == [
        {
            "folderKind": "VectorStore",
            "vectorStoreName": "default",
            "relativePath": "hours.md",
            "contentBytes": base64.b64encode(content).decode(),
            "contentType": "text/markdown",
        }
    ]
    assert base64.b64decode(plan.adds[0]["contentBytes"]) == content


def test_the_plan_does_not_mutate_its_input(detail):
    original = copy.deepcopy(detail)
    guide_dto.plan_file_sync(detail, {"anything.md": b"x"})
    assert detail == original


# --------------------------------------------------------------------------
# build_update_dto with a plan
# --------------------------------------------------------------------------


def test_the_dto_keeps_the_planned_ids_and_uploads_the_planned_files(detail):
    content = b"# Policies\n"
    detail["files"] = [
        vector_store_file("keep-me", "policies.md", content),
        vector_store_file("stale", "hours.md", b"# Old hours\n"),
        vector_store_file("sheet", "data.csv", b"a,b\n", folderKind="CodeInterpreter"),
    ]
    desired = {"policies.md": content, "hours.md": b"# New hours\n"}
    plan = guide_dto.plan_file_sync(detail, desired)

    dto = guide_dto.build_update_dto(detail, "NEW INSTRUCTIONS", plan)

    assert dto["instructions"] == "NEW INSTRUCTIONS"
    # The kept knowledge file and the foreign folder kind; NOT the stale one.
    assert dto["fileIdsToKeep"] == ["keep-me", "sheet"]
    assert [add["relativePath"] for add in dto["filesToAdd"]] == ["hours.md"]
    # Everything else is still carried across verbatim.
    assert dto["customTools"] == detail["customTools"]
    assert dto["contextOptions"] == detail["contextOptions"]


def test_without_a_plan_the_dto_keeps_every_file_and_adds_none(detail):
    """The restore path and any instructions-only write.  """
    dto = guide_dto.build_update_dto(detail, "x")
    assert dto["fileIdsToKeep"] == [f["id"] for f in detail["files"]]
    assert dto["filesToAdd"] == []


# --------------------------------------------------------------------------
# comparable(include_files=False)
# --------------------------------------------------------------------------


def test_comparable_can_exclude_the_files_that_a_sync_moves(detail):
    other = copy.deepcopy(detail)
    other["files"] = []
    assert guide_dto.comparable(detail, include_files=False) == guide_dto.comparable(
        other, include_files=False
    )
    assert "files" not in guide_dto.comparable(detail, include_files=False)


def test_excluding_the_files_still_catches_collateral_damage(detail):
    other = copy.deepcopy(detail)
    other["files"] = []
    other["contextOptions"] = []
    assert guide_dto.comparable(detail, include_files=False) != guide_dto.comparable(
        other, include_files=False
    )
