"""The only module that talks to GuideAnts' *authoring* API.

Two credentials exist and they are easy to confuse:
  - config.GUIDEANTS_API_KEY  -> the PUBLISHED guide's key, used by
    app/guide_client.py on calls.
  - the admin email/password here -> a GuideAnts user with the Admin role.
    /api/guides is RequireAuthorization("RequireAdmin").

Login returns the user in the response body but issues the JWT as an
HTTP-only cookie; the bearer handler falls back to that cookie when no
Authorization header is present. So this client holds a cookie jar. The
token has a finite lifetime, hence the single re-login-and-retry on 401.

WHY THERE IS NO import_bundle HERE ANY MORE
-------------------------------------------
`POST /api/guides/import` was measured against a real GuideAnts on
2026-09-18 and is UNSAFE on an existing guide. On update it runs a series
of non-transactional `ExecuteDeleteAsync` calls -- context options,
starters, tools, members, OpenAPI schemas, then `AssistantFiles`. The
`AssistantFiles` delete fails on the SQL foreign key
`FK_DocumentChunks_AssistantFiles_AssistantFileId` (HTTP 500) whenever the
guide has indexed knowledge files -- and by then the earlier deletes have
already committed. Observed result on a live guide: a 500 response and a
guide left with zero custom tools and zero context options. It is not
atomic, whatever the earlier design note claimed.

So publishing goes through a read-modify-write `PUT /api/guides/{id}` that
is verified afterwards, and changes only the two things it means to: the
guide's instructions and its vector-store knowledge files. See
`guide_dto.py` for the DTO mapping, the file plan and the comparison.

WHAT THE KNOWLEDGE SYNC OWNS
----------------------------
`UpdateGuideDto` is full-state, so `fileIdsToKeep` decides what survives:
an existing file whose id is omitted is deleted, and the update path
clears its `DocumentChunks` first, which is why replacing an indexed file
works here (200) where the import endpoint fails (FK, 500).

That makes Publish the owner of the guide's whole vector store. Any
`VectorStore` file the console does not publish -- including one uploaded
by hand in the GuideAnts editor -- is deleted on the next publish, and
this app cannot put it back: GuideAnts returns a file's metadata, never
its bytes. Files of any other `folderKind` are kept untouched.

Two consequences shape the code below:

  * A file that has not changed (same path, same content hash) is kept by
    id rather than re-uploaded. Replacing a file clears its chunks
    immediately while re-indexing is asynchronous, so a needless replace
    is a window in which the guide cannot answer from that document.
  * An empty desired set against a stocked vector store is REFUSED before
    any PUT. That is the one mistake with no undo.
"""

from __future__ import annotations

import logging

import httpx

from .. import config
from . import guide_dto

logger = logging.getLogger(__name__)

_LOGIN_PATH = "/api/auth/login"
_GUIDES_PATH = "/api/guides"

# The bundle folder whose files ARE the guide's vector store. Publish
# owns everything under it and nothing outside it.
_KNOWLEDGE_PREFIX = "VectorStores/default/"

# Cached across publishes so a burst of them does not re-authenticate each
# time. Cleared on 401 and by reset_session() in tests.
_cookies: dict[str, str] | None = None


class GuideAntsAdminError(RuntimeError):
    """A call to GuideAnts' authoring API failed."""


class GuideAntsNotConfigured(GuideAntsAdminError):
    """No admin credentials are configured, so publishing is unavailable."""


def is_configured() -> bool:
    return bool(config.GUIDEANTS_ADMIN_EMAIL and config.GUIDEANTS_ADMIN_PASSWORD)


def reset_session() -> None:
    global _cookies
    _cookies = None


async def _login(client: httpx.AsyncClient) -> dict[str, str]:
    try:
        response = await client.post(
            f"{config.GUIDEANTS_BASE_URL}{_LOGIN_PATH}",
            json={
                "email": config.GUIDEANTS_ADMIN_EMAIL,
                "password": config.GUIDEANTS_ADMIN_PASSWORD,
            },
        )
    except httpx.HTTPError as exc:
        raise GuideAntsAdminError(f"GuideAnts unreachable at login: {exc}") from exc
    if response.status_code != 200:
        # The password is never interpolated into any message, here or in
        # _request below -- these strings end up in a GuidePublication row
        # and on the console's screen.
        raise GuideAntsAdminError(
            f"could not log in to GuideAnts as {config.GUIDEANTS_ADMIN_EMAIL} "
            f"(HTTP {response.status_code}) -- check GUIDEANTS_ADMIN_EMAIL/"
            "GUIDEANTS_ADMIN_PASSWORD and that the account has the Admin role"
        )
    return dict(response.cookies)


async def _send(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    cookies: dict[str, str],
    **kwargs,
) -> httpx.Response:
    send = getattr(client, method.lower())
    try:
        return await send(f"{config.GUIDEANTS_BASE_URL}{path}", cookies=cookies, **kwargs)
    except httpx.HTTPError as exc:
        raise GuideAntsAdminError(
            f"GuideAnts unreachable on {method} {path}: {exc}"
        ) from exc


def _error_detail(response: httpx.Response) -> str:
    # Every remote failure must end up as a GuideAntsAdminError, which is
    # the only exception publisher.publish() catches -- anything else
    # escapes uncaught and the GuidePublication's failure state is rolled
    # back unrecorded. So a JSON body that is not a dict (a bare string or
    # list) must not raise on .get() here.
    try:
        body = response.json()
    except ValueError:
        return response.text
    if isinstance(body, dict):
        return body.get("error", "") or body.get("message", "") or str(body)
    return str(body)


async def _request(client: httpx.AsyncClient, method: str, path: str, **kwargs):
    """One authenticated call, with the bounded re-login-and-retry on 401.

    Shared by every endpoint so the retry discipline cannot drift between
    them. Returns the parsed JSON body (a dict or a list).
    """
    global _cookies
    cookies = _cookies or await _login(client)
    response = await _send(client, method, path, cookies, **kwargs)

    if response.status_code == 401:
        # Token expired between publishes: re-authenticate once.
        logger.info("GuideAnts %s %s returned 401; re-authenticating once", method, path)
        cookies = await _login(client)
        response = await _send(client, method, path, cookies, **kwargs)

    if response.status_code == 401:
        _cookies = None
        raise GuideAntsAdminError(
            f"GuideAnts rejected {method} {path} with 401 after re-authenticating"
        )
    if response.status_code >= 400:
        raise GuideAntsAdminError(
            f"GuideAnts rejected {method} {path} "
            f"(HTTP {response.status_code}): {_error_detail(response)}"
        )

    _cookies = cookies
    try:
        return response.json()
    except ValueError:
        return {}


def _guides_from(payload) -> list[dict]:
    """GET /api/guides returns the list; tolerate a paged wrapper."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "guides", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise GuideAntsAdminError(
        f"GuideAnts returned an unrecognized guide list ({type(payload).__name__})"
    )


async def _find_guide_id(client: httpx.AsyncClient) -> str:
    name = config.GUIDEANTS_GUIDE_NAME
    guides = _guides_from(await _request(client, "GET", _GUIDES_PATH))
    matches = [guide for guide in guides if guide.get("name") == name]
    if not matches:
        # Deliberately NOT created: a guide this app invents would have no
        # tools, no knowledge and no published id, and the phone number
        # would keep pointing at the real one.
        raise GuideAntsAdminError(
            f"no GuideAnts guide named {name!r} exists (GUIDEANTS_GUIDE_NAME); "
            "publishing will not create one"
        )
    if len(matches) > 1:
        raise GuideAntsAdminError(
            f"{len(matches)} GuideAnts guides are named {name!r}; refusing to "
            "guess which one to update"
        )
    guide_id = matches[0].get("id")
    if not guide_id:
        raise GuideAntsAdminError(f"the GuideAnts guide named {name!r} has no id")
    return str(guide_id)


def _describe_difference(before: dict, after: dict) -> str:
    """A short path-wise account of what moved, for the error message."""
    differences: list[str] = []

    def walk(left, right, path: str) -> None:
        if len(differences) >= 5:
            return
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left) | set(right)):
                if key not in left:
                    differences.append(f"{path}.{key} added")
                elif key not in right:
                    differences.append(f"{path}.{key} removed")
                else:
                    walk(left[key], right[key], f"{path}.{key}")
            return
        if isinstance(left, list) and isinstance(right, list):
            if len(left) != len(right):
                differences.append(
                    f"{path}: {len(left)} entries before, {len(right)} after"
                )
                return
            for index, (one, other) in enumerate(zip(left, right)):
                walk(one, other, f"{path}[{index}]")
            return
        if left != right:
            differences.append(f"{path}: {left!r} -> {right!r}")

    walk(before, after, "guide")
    return "; ".join(differences[:5]) or "an unlocated difference"


async def update_guide(instructions: str, knowledge: dict[str, bytes]) -> dict:
    """Change the live guide's instructions and its knowledge files.

    Read the guide, refuse anything we have not proven round-trips, plan
    the file sync against what was just read, rebuild the full-state DTO,
    PUT it, then read it back and prove that nothing beyond the
    instructions and the planned files moved. A failed verification
    attempts one best-effort restore before raising.

    `knowledge` is keyed by BUNDLE path (`VectorStores/default/<id>.md`);
    anything outside that folder is ignored, which keeps this function's
    contract tied to the one folder Publish owns.

    Returns {"guideId": ..., "warnings": [...], "files": {...counts}}.
    """
    if not is_configured():
        raise GuideAntsNotConfigured(
            "GUIDEANTS_ADMIN_EMAIL and GUIDEANTS_ADMIN_PASSWORD are not set, "
            "so publishing to GuideAnts is disabled"
        )

    desired = _desired_files(knowledge)

    async with httpx.AsyncClient(timeout=config.GUIDEANTS_TIMEOUT_SECONDS) as client:
        guide_id = await _find_guide_id(client)
        detail_path = f"{_GUIDES_PATH}/{guide_id}"
        before = await _request(client, "GET", detail_path)
        if not isinstance(before, dict) or "guide" not in before:
            raise GuideAntsAdminError(
                f"GuideAnts returned an unrecognized guide body for {guide_id}"
            )

        # Fail closed BEFORE any write: nothing is sent when the guide
        # carries a feature this DTO has not been proven to preserve.
        reasons = guide_dto.unsupported_features(before)
        if reasons:
            raise GuideAntsAdminError(
                "refusing to update the GuideAnts guide because it uses "
                "features this publisher has not been verified to preserve: "
                + "; ".join(reasons)
            )

        # Planned from the body we just read, never from a cached one: the
        # plan names file ids, and a stale id would delete the wrong file.
        plan = guide_dto.plan_file_sync(before, desired)
        if plan.would_delete_everything:
            # Also before any PUT, and for a harder reason: deleting a
            # file is the one step of this flow that cannot be undone.
            raise GuideAntsAdminError(
                "there are no publishable knowledge items, and refusing to "
                "delete the guide's entire knowledge base -- enable or add "
                "items in the console first"
            )

        await _request(
            client,
            "PUT",
            detail_path,
            json=guide_dto.build_update_dto(before, instructions, plan),
        )

        after = await _request(client, "GET", detail_path)
        if not isinstance(after, dict) or "guide" not in after:
            raise GuideAntsAdminError(
                f"GuideAnts returned an unrecognized guide body for {guide_id} "
                "when verifying the update"
            )

        problem = _verification_problem(before, after, instructions, plan, desired)
        if problem:
            restored = await _restore(client, detail_path, before, after)
            raise GuideAntsAdminError(
                f"GuideAnts guide {guide_id} failed verification -- {problem}. "
                + (
                    "The previous instructions and settings were restored, and "
                    "every file still on the guide was kept -- but a file the "
                    "update deleted cannot be restored from here, because "
                    "GuideAnts does not hand back a stored file's bytes."
                    if restored is None
                    else f"Restoring the previous state ALSO failed: {restored}"
                )
            )

        return {
            "guideId": guide_id,
            "warnings": [],
            "files": {
                "added": len(plan.added),
                "replaced": len(plan.replaced),
                "removed": len(plan.removed),
                "unchanged": len(plan.unchanged),
            },
        }


def _verification_problem(
    before: dict,
    after: dict,
    instructions: str,
    plan: guide_dto.FileSyncPlan,
    desired: dict[str, bytes],
) -> str | None:
    """What the read-back disproves, or None if the write did exactly what
    was asked. The file set is checked separately from the rest of the
    guide, because the files are the part that was meant to move."""
    if after.get("instructions") != instructions:
        return "the guide's instructions are not what was sent"

    before_view = guide_dto.comparable(before, include_files=False)
    after_view = guide_dto.comparable(after, include_files=False)
    if before_view != after_view:
        return (
            "the update changed more than the instructions and the knowledge "
            "files: " + _describe_difference(before_view, after_view)
        )

    expected_paths = sorted(desired)
    actual_paths = guide_dto.vector_store_paths(after)
    if actual_paths != expected_paths:
        return (
            "the guide's knowledge files are not the ones that were sent: "
            f"expected {expected_paths}, found {actual_paths}"
        )

    # An id that vanished means a file we asked to KEEP was replaced or
    # deleted -- the paths can still line up while the index behind them
    # was thrown away and is being rebuilt.
    surviving = {str(file.get("id")) for file in after.get("files") or []}
    lost = sorted(
        (set(plan.keep_ids) | guide_dto.non_vector_store_file_ids(before)) - surviving
    )
    if lost:
        return f"files that were meant to be kept were not: {', '.join(lost)}"
    return None


def _desired_files(knowledge: dict[str, bytes] | None) -> dict[str, bytes]:
    """Bundle paths -> the bare relativePath GuideAnts stores.

    The bundle also carries `instructions.md`, `manifest.json` and the
    OpenAPI schemas; none of those belong in the vector store, so anything
    outside `VectorStores/default/` is dropped rather than uploaded.
    """
    desired: dict[str, bytes] = {}
    for path, content in (knowledge or {}).items():
        if not path.startswith(_KNOWLEDGE_PREFIX):
            continue
        name = path[len(_KNOWLEDGE_PREFIX) :]
        if not name or "/" in name:
            continue
        desired[name] = content
    return desired


async def _restore(
    client: httpx.AsyncClient, detail_path: str, before: dict, current: dict
) -> str | None:
    """One best-effort PUT of the pre-update instructions and settings.
    Returns None on success or the failure message -- it never raises,
    because the caller is already raising about the verification failure
    and must report both outcomes.

    It keeps every file that is on the guide *now* rather than every file
    that was there before: a file the failed update deleted is gone for
    good (its bytes are not retrievable), and naming its id would only
    make the restore itself fail.
    """
    dto = guide_dto.build_update_dto(before, before.get("instructions") or "")
    # `current` is the read-back that failed verification. If it did not even
    # report a file list, fall back to the ids that were valid a moment ago
    # rather than sending an empty keep-list, which would delete everything.
    source = current if isinstance(current.get("files"), list) else before
    dto["fileIdsToKeep"] = [
        file["id"] for file in source.get("files") or [] if file.get("id")
    ]
    dto["filesToAdd"] = []
    try:
        await _request(client, "PUT", detail_path, json=dto)
    except GuideAntsAdminError as exc:
        logger.error("restoring the previous guide state failed: %s", exc)
        return str(exc)
    logger.info("restored the guide's previous state after a failed verification")
    return None
