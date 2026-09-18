"""Pure helpers for the read-modify-write update of a GuideAnts guide.

No I/O -- unit-tested directly, in the fillers.py / speech_timing.py
tradition. `guideants_admin.py` supplies the HTTP.

Why this exists at all: GuideAnts has no instructions-only endpoint.
`PUT /api/guides/{id}` takes `UpdateGuideDto`, a **full-state** record --
an omitted file is deleted, a null field is cleared. So changing the
instructions means reading the whole guide back, rebuilding that record
from it verbatim, and changing exactly one field.

Three pieces make that safe:

  * `unsupported_features()` refuses, before anything is sent, on any part
    of a guide we have not verified round-trips through this DTO.
  * `build_update_dto()` is the verified mapping from a GET body back to
    the PUT body.
  * `comparable()` is the normalized view used to prove, after the PUT,
    that nothing but the instructions moved. It has to be
    order-insensitive: GuideAnts returns a custom tool's operations in a
    different order each read, and mints fresh operation ids.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# Kept only when normalizing a file's markdown shadow. The rest -- ids,
# timestamps, processedAt -- move on their own and say nothing about
# whether we damaged the guide.
_SHADOW_KEEP = ("status", "contentHash", "fileSize")


def unsupported_features(detail: dict) -> list[str]:
    """Every reason this guide must NOT be updated through `build_update_dto`.

    Fail closed: each entry names something that exists on the guide but
    that we have not verified survives the round-trip. An empty list means
    the guide looks like the shape the round-trip was proven on.
    """
    reasons: list[str] = []
    guide = detail.get("guide") or {}

    if detail.get("tools"):
        reasons.append(
            f"the guide has {len(detail['tools'])} shared tool(s); only custom "
            "tools have been verified to survive the update"
        )

    if guide.get("crewMemberCount"):
        reasons.append(
            f"the guide has {guide['crewMemberCount']} crew member(s); the "
            "update clears crewMemberIds"
        )
    for crew in detail.get("crews") or []:
        if crew.get("members"):
            name = crew.get("name") or crew.get("crewId") or "?"
            reasons.append(
                f"crew {name!r} has {len(crew['members'])} member(s); the "
                "update clears crewMemberIds"
            )

    for key, label in (
        ("authProviders", "auth providers"),
        ("skills", "skills"),
        ("environmentVariables", "environment variables"),
    ):
        if detail.get(key):
            reasons.append(
                f"the guide has {label} configured; they have not been "
                "verified to survive the update"
            )

    sandbox = detail.get("sandboxWireApiConfig")
    if isinstance(sandbox, dict):
        if sandbox.get("enabled"):
            reasons.append(
                "the guide has the sandbox wire API enabled; it has not been "
                "verified to survive the update"
            )
        else:
            extra = sorted(
                key
                for key, value in sandbox.items()
                if key != "enabled" and value is not None
            )
            if extra:
                reasons.append(
                    "the guide has a sandbox wire API configuration "
                    f"({', '.join(extra)}); it has not been verified to "
                    "survive the update"
                )
    elif sandbox:
        reasons.append(
            "the guide has an unrecognized sandboxWireApiConfig; it has not "
            "been verified to survive the update"
        )

    return reasons


def build_update_dto(detail: dict, instructions: str) -> dict:
    """The GET body of a guide, rebuilt as the PUT body that changes only
    its instructions.

    Every field is carried across deliberately. `fileIdsToKeep` is the one
    that matters most: naming the existing file ids keeps them, which keeps
    their vector-store index -- omitting a file deletes it and re-indexing
    it would cost minutes of a guide that cannot answer.
    """
    guide = detail["guide"]
    return {
        "name": guide["name"],
        "description": guide["description"],
        "instructions": instructions,
        "homePageMarkdown": detail["homePageMarkdown"],
        "modelId": guide["modelId"],
        "temperature": detail["temperature"],
        "topP": detail["topP"],
        "reasoningEffort": detail["reasoningEffort"],
        "toolIds": [tool["id"] for tool in detail["tools"]] if detail["tools"] else [],
        "customTools": detail["customTools"],
        "contextOptions": detail["contextOptions"],
        "authProviders": detail["authProviders"],
        "fileIdsToKeep": [file["id"] for file in detail["files"]],
        "filesToAdd": [],
        "conversationStarters": detail["conversationStarters"],
        "crewMemberIds": [],
        "environmentVariables": detail["environmentVariables"],
        "skills": detail["skills"],
        "sandboxWireApiConfig": detail["sandboxWireApiConfig"],
        "maxToolCallsPerTurn": detail["maxToolCallsPerTurn"],
    }


def _normalized_file(file: dict) -> dict:
    out = {
        key: value
        for key, value in file.items()
        if key not in ("id", "created", "markdownShadow")
    }
    shadow = file.get("markdownShadow")
    if isinstance(shadow, dict):
        out["markdownShadow"] = {
            key: shadow.get(key) for key in _SHADOW_KEEP if key in shadow
        }
    elif shadow is not None:
        out["markdownShadow"] = shadow
    return out


def _normalized_custom_tool(tool: dict) -> dict:
    out = {key: value for key, value in tool.items() if key != "operations"}
    operations = tool.get("operations") or []
    out["operations"] = sorted(
        (
            {key: value for key, value in operation.items() if key != "id"}
            for operation in operations
        ),
        key=lambda operation: str(operation.get("operationId")),
    )
    return out


def comparable(detail: dict) -> dict:
    """A normalized view of a guide used to prove an update changed nothing
    it was not meant to.

    `instructions` is excluded -- that is the field we are deliberately
    changing. So is everything the server moves on its own:

      * `guide.updated` (and `guide.id`, so the same helper can compare
        across reads without the id dominating a diff),
      * a file's `id` and `created`, and every volatile part of its
        markdown shadow except status / contentHash / fileSize,
      * an operation's `id`, which GuideAnts re-mints on every write,
      * `crews[*].crewId`.

    Lists that come back in an arbitrary order -- files, custom tools and
    a tool's operations -- are sorted, so "same set" compares equal while
    a genuinely missing tool, context option or file still shows up.
    """
    view = deepcopy(detail)
    view.pop("instructions", None)

    guide = view.get("guide")
    if isinstance(guide, dict):
        guide.pop("updated", None)
        guide.pop("id", None)

    view["files"] = sorted(
        (_normalized_file(file) for file in view.get("files") or []),
        key=lambda file: str(file.get("relativePath")),
    )

    view["customTools"] = sorted(
        (_normalized_custom_tool(tool) for tool in view.get("customTools") or []),
        key=lambda tool: str(tool.get("name")),
    )

    crews: list[Any] = []
    for crew in view.get("crews") or []:
        crew = dict(crew)
        crew.pop("crewId", None)
        crews.append(crew)
    view["crews"] = crews

    return view
