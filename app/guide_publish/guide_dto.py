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
    different order each read, and mints fresh operation ids. Pass
    `include_files=False` when the files are *meant* to move -- a
    knowledge sync compares the file set separately.
  * `missing_custom_tools()` fills in the custom tool sources a guide has
    none of -- an empty guide otherwise stays empty, because the PUT
    carries `customTools` across from the read verbatim. Only a source
    whose NAME is absent is added; one already on the guide is never
    rewritten, which is what keeps the verified round-trip on a stocked
    guide byte-for-byte unchanged.
  * `plan_file_sync()` decides, before anything is sent, which existing
    vector-store files to keep by id and which to (re-)upload. Publish
    owns the guide's whole vector store: a file the console does not
    publish is omitted from `fileIdsToKeep`, and an omitted file is
    DELETED. Only files that genuinely changed are replaced, because
    replacing one clears its chunks immediately while re-indexing runs
    asynchronously -- a needless replace is a window in which the guide
    cannot answer from that document.
"""

from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

# Kept only when normalizing a file's markdown shadow. The rest -- ids,
# timestamps, processedAt -- move on their own and say nothing about
# whether we damaged the guide.
_SHADOW_KEEP = ("status", "contentHash", "fileSize")
_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


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


def missing_custom_tools(detail: dict, sources: dict[str, str]) -> list[dict]:
    """The custom tool sources in `sources` (name -> OpenAPI document text)
    that the guide does not have yet, shaped for `customTools`.

    Only `name`, `apiHost` and the raw `openApiSpec` are sent. GuideAnts
    derives every operation -- its `schemaFragment` and `toolDefinition` --
    from the spec on write (measured 2026-09-21: an empty `operations`
    list came back with all nine operations). The spec must be the file's
    text unchanged, since that is what an admin's own paste stores.
    """
    have = {tool.get("name") for tool in detail.get("customTools") or []}
    return [
        {"name": name, "openApiSpec": text, "apiHost": name, "authConfig": None,
         "operations": []}
        for name, text in sources.items()
        if name not in have
    ]


def spec_operation_ids(spec_text: str) -> list[str]:
    """Sorted operationIds declared by an OpenAPI document."""
    document = json.loads(spec_text)
    return sorted(
        operation["operationId"]
        for methods in (document.get("paths") or {}).values()
        for method, operation in methods.items()
        if method.lower() in _HTTP_METHODS and "operationId" in operation
    )


# The one folder kind Publish owns. Compared case-insensitively because
# the field is a server-side enum name and nothing guarantees its casing.
VECTOR_STORE_KIND = "vectorstore"
VECTOR_STORE_NAME = "default"


def _is_vector_store(file: dict) -> bool:
    return str(file.get("folderKind") or "").lower() == VECTOR_STORE_KIND


def _content_hash_of(file: dict) -> str:
    """The SHA-256 hex of the stored file's raw bytes, as GuideAnts records
    it on the markdown shadow.

    An empty string means "unknown": the shadow is missing, or the file is
    still being processed and has no hash yet. Unknown must read as
    CHANGED -- treating it as unchanged would leave a half-processed file
    in place and silently skip the upload that fixes it.
    """
    shadow = file.get("markdownShadow")
    if not isinstance(shadow, dict):
        return ""
    return str(shadow.get("contentHash") or "")


@dataclass(frozen=True)
class FileSyncPlan:
    """What a publish will do to the guide's vector store.

    `keep_ids` and `adds` go straight into the DTO; the four path lists and
    `would_delete_everything` are for the caller's guard, its warning and
    its counts.
    """

    keep_ids: list[str] = field(default_factory=list)
    adds: list[dict] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    replaced: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    would_delete_everything: bool = False


def plan_file_sync(detail: dict, desired: dict[str, bytes]) -> FileSyncPlan:
    """Reconcile the guide's vector store against what the console publishes.

    `desired` maps a bare relativePath (`<title-slug>.md`) to the
    file's bytes. Only `folderKind == "VectorStore"` files are considered:
    every other folder kind is kept untouched, because Publish does not own
    them.

    An existing vector-store file is kept exactly when `desired` still has
    its path AND its recorded content hash matches the bytes we would
    upload. Anything else is dropped -- and dropped means deleted, since
    `fileIdsToKeep` is a full-state field. A dropped path that is still
    desired is re-added (a replace); one that is not is simply gone.
    """
    wanted = {
        path: hashlib.sha256(content).hexdigest() for path, content in desired.items()
    }

    existing = [file for file in detail.get("files") or [] if _is_vector_store(file)]
    existing_paths = {str(file.get("relativePath")) for file in existing}

    keep_ids: list[str] = []
    kept_paths: set[str] = set()
    for file in existing:
        path = str(file.get("relativePath"))
        if path in kept_paths:
            # A duplicate path: keep at most the first match, so the second
            # copy is dropped rather than silently shadowing the first.
            continue
        if path in wanted and _content_hash_of(file).lower() == wanted[path]:
            keep_ids.append(str(file.get("id")))
            kept_paths.add(path)

    add_paths = sorted(path for path in desired if path not in kept_paths)
    adds = [
        {
            "folderKind": "VectorStore",
            "vectorStoreName": VECTOR_STORE_NAME,
            "relativePath": path,
            "contentBytes": base64.b64encode(desired[path]).decode("ascii"),
            "contentType": "text/markdown",
        }
        for path in add_paths
    ]

    return FileSyncPlan(
        keep_ids=keep_ids,
        adds=adds,
        unchanged=sorted(kept_paths),
        added=[path for path in add_paths if path not in existing_paths],
        replaced=[path for path in add_paths if path in existing_paths],
        removed=sorted(existing_paths - set(desired)),
        # Refusing this is the caller's job, but recognizing it is this
        # function's: an empty render against a stocked vector store would
        # wipe the guide's whole knowledge base, and the bytes of a deleted
        # file cannot be read back to undo it.
        would_delete_everything=not desired and bool(existing),
    )


def vector_store_paths(detail: dict) -> list[str]:
    """Every vector-store file's relativePath, sorted -- the set a sync is
    verified against after the PUT."""
    return sorted(
        str(file.get("relativePath"))
        for file in detail.get("files") or []
        if _is_vector_store(file)
    )


def non_vector_store_file_ids(detail: dict) -> set[str]:
    """Files Publish does not own. They are always kept by id."""
    return {
        str(file.get("id"))
        for file in detail.get("files") or []
        if not _is_vector_store(file)
    }


def build_update_dto(
    detail: dict,
    instructions: str,
    plan: FileSyncPlan | None = None,
    new_tools: list[dict] | None = None,
) -> dict:
    """The GET body of a guide, rebuilt as the PUT body that changes only
    its instructions and, with a plan, its vector-store files. `new_tools`
    (from `missing_custom_tools`) are appended to the guide's own.

    Every field is carried across deliberately. `fileIdsToKeep` is the one
    that matters most: naming an existing file id keeps it, which keeps its
    vector-store index -- omitting a file deletes it, and re-indexing costs
    minutes of a guide that cannot answer.

    Without a `plan` this keeps every file and adds none, which is what a
    restore and an instructions-only write want. With one, it keeps the
    files the plan matched plus every file Publish does not own, and
    uploads the rest.
    """
    guide = detail["guide"]
    if plan is None:
        file_ids_to_keep = [file["id"] for file in detail["files"]]
        files_to_add: list[dict] = []
    else:
        untouched = non_vector_store_file_ids(detail)
        file_ids_to_keep = list(plan.keep_ids) + [
            file["id"] for file in detail["files"] if str(file.get("id")) in untouched
        ]
        files_to_add = list(plan.adds)
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
        "customTools": list(detail["customTools"]) + list(new_tools or []),
        "contextOptions": detail["contextOptions"],
        "authProviders": detail["authProviders"],
        "fileIdsToKeep": file_ids_to_keep,
        "filesToAdd": files_to_add,
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


def comparable(detail: dict, include_files: bool = True) -> dict:
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

    `include_files=False` drops the `files` key entirely, for the one
    caller whose write is *meant* to change it.
    """
    view = deepcopy(detail)
    view.pop("instructions", None)

    guide = view.get("guide")
    if isinstance(guide, dict):
        guide.pop("updated", None)
        guide.pop("id", None)

    if include_files:
        view["files"] = sorted(
            (_normalized_file(file) for file in view.get("files") or []),
            key=lambda file: str(file.get("relativePath")),
        )
    else:
        # A knowledge sync moves the files on purpose, so comparing them
        # here would always fail. The file set is verified separately,
        # against the paths and ids the plan asked for.
        view.pop("files", None)

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
