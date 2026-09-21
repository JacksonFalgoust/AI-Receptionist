"""The client for GuideAnts' authoring API.

Auth is unusual and worth stating: POST /api/auth/login returns the user in
the response BODY but delivers the JWT as an HTTP-only cookie, and the
bearer handler falls back to that cookie when no Authorization header is
present. So the client keeps a cookie jar rather than reading a token out
of the response.

Publishing is a read-modify-write on PUT /api/guides/{id}, NOT an import --
GuideAnts' import endpoint deletes a guide's dependent rows one
non-transactional statement at a time and then fails on a foreign key when
the guide has indexed files, leaving it stripped. These tests pin the
shape that replaced it: list, read, write, read back and verify.

The write now carries the guide's knowledge files as well as its
instructions, and `fileIdsToKeep` is full-state -- an omitted file is
deleted and its bytes are not retrievable. So the file-plan tests here are
the ones guarding against silently wiping a knowledge base.

Fakes are hand-rolled, matching tests/test_postmark_client.py -- this repo
adds no HTTP-mocking dependency. Nothing here reaches a real GuideAnts.
"""

import asyncio
import base64
import copy
import hashlib
import json
import pathlib

import pytest

from app import config
from app.guide_publish import guide_dto, guideants_admin, template

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "guide_detail.json"
GUIDE_ID = "fb9d753f-f61a-406a-9748-d90864d7acb2"

EXISTING_PATH = "bike-shop-knowledge.md"
EXISTING_BYTES = b"# Bike shop knowledge\n\nWe rent bikes.\n"
# What the console publishes when nothing about the knowledge changed. Most
# tests here are about the instructions, and this keeps them from tripping
# the wipe guard or replacing an indexed file as a side effect.
KNOWLEDGE = {f"VectorStores/default/{EXISTING_PATH}": EXISTING_BYTES}


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def load_detail():
    detail = json.loads(FIXTURE.read_text())
    # The fixture's recorded hash is of the real (untrimmed) document, which
    # no test can reproduce. Point it at EXISTING_BYTES so "the console is
    # publishing exactly what the guide already holds" is expressible.
    detail["files"][0]["markdownShadow"]["contentHash"] = sha(EXISTING_BYTES)
    return detail


class FakeResponse:
    def __init__(self, status_code, json_data=None, cookies=None):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.cookies = cookies or {}
        self.text = str(json_data)

    def json(self):
        return self._json_data


class FakeAsyncClient:
    """Records calls and replays a scripted sequence of responses."""

    calls = []
    responses = []

    def __init__(self, *args, **kwargs):
        self.cookies = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def _record(self, method, url, **kwargs):
        FakeAsyncClient.calls.append({"method": method, "url": url, **kwargs})
        if not FakeAsyncClient.responses:
            raise AssertionError(f"unscripted {method} {url}")
        response = FakeAsyncClient.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    async def post(self, url, **kwargs):
        return await self._record("POST", url, **kwargs)

    async def get(self, url, **kwargs):
        return await self._record("GET", url, **kwargs)

    async def put(self, url, **kwargs):
        return await self._record("PUT", url, **kwargs)


@pytest.fixture(autouse=True)
def _client(monkeypatch):
    FakeAsyncClient.calls = []
    FakeAsyncClient.responses = []
    monkeypatch.setattr(guideants_admin.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(config, "GUIDEANTS_ADMIN_EMAIL", "svc@example.com")
    monkeypatch.setattr(config, "GUIDEANTS_ADMIN_PASSWORD", "hunter2-secret")
    monkeypatch.setattr(config, "GUIDEANTS_GUIDE_NAME", "Twilio Demo Agent")
    guideants_admin.reset_session()
    yield


LOGIN_OK = lambda: FakeResponse(200, {"email": "svc@example.com"}, cookies={"auth": "jwt"})
GUIDE_LIST = lambda: FakeResponse(
    200, [{"id": "other", "name": "Something Else"}, {"id": GUIDE_ID, "name": "Twilio Demo Agent"}]
)


def script_happy_path(instructions="NEW INSTRUCTIONS", after=None):
    before = load_detail()
    if after is None:
        after = copy.deepcopy(before)
        after["instructions"] = instructions
        # The server genuinely does all of this on a write; none of it may
        # be mistaken for damage.
        after["guide"]["updated"] = "2030-01-01T00:00:00"
        after["customTools"].reverse()
        for tool in after["customTools"]:
            tool["operations"].reverse()
            for index, operation in enumerate(tool["operations"]):
                operation["id"] = f"reminted-{index}"
    FakeAsyncClient.responses = [
        LOGIN_OK(),
        GUIDE_LIST(),
        FakeResponse(200, before),
        FakeResponse(200, {"id": GUIDE_ID}),
        FakeResponse(200, after),
    ]
    return before, after


def methods_and_paths():
    return [(c["method"], c["url"].split("/api/", 1)[-1]) for c in FakeAsyncClient.calls]


def test_not_configured_when_credentials_are_unset(monkeypatch):
    monkeypatch.setattr(config, "GUIDEANTS_ADMIN_EMAIL", "")
    assert guideants_admin.is_configured() is False


def test_configured_when_credentials_are_set():
    assert guideants_admin.is_configured() is True


def test_import_bundle_is_gone():
    """No dead destructive code: the endpoint that stripped the live guide
    must not be reachable from this module at all."""
    assert not hasattr(guideants_admin, "import_bundle")
    assert not hasattr(guideants_admin, "_IMPORT_PATH")
    source = pathlib.Path(guideants_admin.__file__).read_text()
    body = source.split('"""', 2)[2]  # everything after the module docstring
    assert "/api/guides/import" not in body


def test_happy_path_logs_in_lists_reads_writes_and_verifies():
    script_happy_path()
    result = asyncio.run(guideants_admin.update_guide("NEW INSTRUCTIONS", KNOWLEDGE))

    assert result == {
        "guideId": GUIDE_ID,
        "warnings": [],
        # Nothing about the knowledge moved, which is the point: the one
        # indexed file was kept by id, not re-uploaded.
        "files": {"added": 0, "replaced": 0, "removed": 0, "unchanged": 1},
    }
    assert methods_and_paths() == [
        ("POST", "auth/login"),
        ("GET", "guides"),
        ("GET", f"guides/{GUIDE_ID}"),
        ("PUT", f"guides/{GUIDE_ID}"),
        ("GET", f"guides/{GUIDE_ID}"),
    ]


def test_the_put_body_is_the_guide_rebuilt_with_new_instructions():
    before, _ = script_happy_path()
    asyncio.run(guideants_admin.update_guide("NEW INSTRUCTIONS", KNOWLEDGE))

    put = next(c for c in FakeAsyncClient.calls if c["method"] == "PUT")
    plan = guide_dto.plan_file_sync(before, {EXISTING_PATH: EXISTING_BYTES})
    assert put["json"] == guide_dto.build_update_dto(before, "NEW INSTRUCTIONS", plan)
    # The one that matters: every existing knowledge file is kept by id.
    assert put["json"]["fileIdsToKeep"] == [f["id"] for f in before["files"]]
    assert put["json"]["customTools"] == before["customTools"]


def test_an_unchanged_knowledge_sync_uploads_nothing_and_keeps_every_id():
    """Replacing a file clears its chunks immediately while re-indexing is
    asynchronous, so a file that did not change must never be re-sent."""
    before, _ = script_happy_path()
    result = asyncio.run(guideants_admin.update_guide("NEW INSTRUCTIONS", KNOWLEDGE))

    put = next(c for c in FakeAsyncClient.calls if c["method"] == "PUT")
    assert put["json"]["filesToAdd"] == []
    assert put["json"]["fileIdsToKeep"] == [f["id"] for f in before["files"]]
    assert result["files"] == {
        "added": 0, "replaced": 0, "removed": 0, "unchanged": 1
    }


def test_the_put_body_carries_a_mixed_file_plan():
    """One file kept, one replaced, one added, one removed, and a file of
    another folder kind that Publish does not own kept regardless."""
    before = load_detail()
    kept = before["files"][0]
    stale = copy.deepcopy(kept)
    stale["id"] = "stale-id"
    stale["relativePath"] = "winter-hours.md"
    stale["markdownShadow"]["contentHash"] = "0" * 64
    doomed = copy.deepcopy(kept)
    doomed["id"] = "doomed-id"
    doomed["relativePath"] = "hand-uploaded.md"
    other = copy.deepcopy(kept)
    other["id"] = "other-folder-id"
    other["folderKind"] = "CodeInterpreter"
    other["relativePath"] = "sheet.csv"
    before["files"] = [kept, stale, doomed, other]

    desired = {
        EXISTING_PATH: EXISTING_BYTES,
        "winter-hours.md": b"# Winter hours\n",
        "new-policy.md": b"# New policy\n",
    }
    knowledge = {f"VectorStores/default/{n}": b for n, b in desired.items()}

    after = copy.deepcopy(before)
    after["instructions"] = "NEW"
    after["files"] = [
        kept,
        other,
        _added_file("fresh-1", "winter-hours.md"),
        _added_file("fresh-2", "new-policy.md"),
    ]
    FakeAsyncClient.responses = [
        LOGIN_OK(), GUIDE_LIST(), FakeResponse(200, before),
        FakeResponse(200, {}), FakeResponse(200, after),
    ]

    result = asyncio.run(guideants_admin.update_guide("NEW", knowledge))

    put = next(c for c in FakeAsyncClient.calls if c["method"] == "PUT")
    # The unchanged file and the foreign folder kind survive by id; the
    # stale one and the hand-uploaded one are simply not named, which is
    # what deletes them.
    assert put["json"]["fileIdsToKeep"] == [kept["id"], "other-folder-id"]
    assert put["json"]["filesToAdd"] == [
        {
            "folderKind": "VectorStore",
            "vectorStoreName": "default",
            "relativePath": "new-policy.md",
            "contentBytes": base64.b64encode(b"# New policy\n").decode(),
            "contentType": "text/markdown",
        },
        {
            "folderKind": "VectorStore",
            "vectorStoreName": "default",
            "relativePath": "winter-hours.md",
            "contentBytes": base64.b64encode(b"# Winter hours\n").decode(),
            "contentType": "text/markdown",
        },
    ]
    assert result["files"] == {
        "added": 1, "replaced": 1, "removed": 1, "unchanged": 1
    }


def _added_file(file_id: str, path: str) -> dict:
    """A file as GuideAnts reports it moments after an upload: a fresh id
    and a shadow that has not finished processing."""
    return {
        "id": file_id,
        "folderKind": "VectorStore",
        "vectorStoreName": "default",
        "relativePath": path,
        "contentType": "text/markdown",
        "created": "2026-09-21T00:00:00",
        "markdownShadow": None,
    }


def test_empty_knowledge_is_refused_before_any_write():
    """The one mistake with no undo: GuideAnts hands back a file's metadata
    but never its bytes, so a wiped vector store cannot be restored."""
    before = load_detail()
    FakeAsyncClient.responses = [LOGIN_OK(), GUIDE_LIST(), FakeResponse(200, before)]

    with pytest.raises(guideants_admin.GuideAntsAdminError) as excinfo:
        asyncio.run(guideants_admin.update_guide("x", {}))

    message = str(excinfo.value)
    assert "no publishable knowledge items" in message
    assert "console" in message
    assert not [c for c in FakeAsyncClient.calls if c["method"] == "PUT"]


def test_an_empty_guide_accepts_an_empty_knowledge_set():
    """The guard is about deleting, not about being empty -- a guide with
    no files and a console with no items is a legitimate no-op."""
    before = load_detail()
    before["files"] = []
    after = copy.deepcopy(before)
    after["instructions"] = "x"
    FakeAsyncClient.responses = [
        LOGIN_OK(), GUIDE_LIST(), FakeResponse(200, before),
        FakeResponse(200, {}), FakeResponse(200, after),
    ]
    result = asyncio.run(guideants_admin.update_guide("x", {}))
    assert result["files"] == {"added": 0, "replaced": 0, "removed": 0, "unchanged": 0}


def test_non_knowledge_bundle_entries_are_never_uploaded():
    before, _ = script_happy_path()
    asyncio.run(
        guideants_admin.update_guide(
            "NEW INSTRUCTIONS",
            {
                **KNOWLEDGE,
                "instructions.md": b"# instructions",
                "manifest.json": b"{}",
                "OpenAPI/voice-receptionist.json": b"{}",
            },
        )
    )
    put = next(c for c in FakeAsyncClient.calls if c["method"] == "PUT")
    assert put["json"]["filesToAdd"] == []


def test_a_wrong_file_set_triggers_exactly_one_restore_and_raises():
    """The PUT reported success but the guide came back without the file
    that was uploaded -- a silent half-write, treated like any other
    failed verification."""
    before = load_detail()
    after = copy.deepcopy(before)
    after["instructions"] = "NEW INSTRUCTIONS"
    after["files"] = []  # the file we asked to keep is gone
    FakeAsyncClient.responses = [
        LOGIN_OK(), GUIDE_LIST(), FakeResponse(200, before),
        FakeResponse(200, {}), FakeResponse(200, after),
        FakeResponse(200, {}),  # the restore PUT
    ]

    with pytest.raises(guideants_admin.GuideAntsAdminError) as excinfo:
        asyncio.run(guideants_admin.update_guide("NEW INSTRUCTIONS", KNOWLEDGE))

    message = str(excinfo.value)
    assert "knowledge files are not the ones that were sent" in message
    assert "does not hand back a stored file's bytes" in message
    puts = [c for c in FakeAsyncClient.calls if c["method"] == "PUT"]
    assert len(puts) == 2, "one update, one restore -- and no retry loop"
    # The restore keeps what is on the guide NOW: naming the deleted file's
    # id would only make the restore fail too.
    assert puts[1]["json"]["fileIdsToKeep"] == []
    assert puts[1]["json"]["filesToAdd"] == []
    assert puts[1]["json"]["instructions"] == before["instructions"]


def test_a_kept_file_that_was_replaced_anyway_fails_verification():
    """Same paths, different ids: the index behind them was thrown away and
    is being rebuilt, which is exactly what keeping by id avoids."""
    before = load_detail()
    after = copy.deepcopy(before)
    after["instructions"] = "NEW INSTRUCTIONS"
    after["files"][0]["id"] = "silently-reindexed"
    FakeAsyncClient.responses = [
        LOGIN_OK(), GUIDE_LIST(), FakeResponse(200, before),
        FakeResponse(200, {}), FakeResponse(200, after),
        FakeResponse(200, {}),
    ]
    with pytest.raises(guideants_admin.GuideAntsAdminError) as excinfo:
        asyncio.run(guideants_admin.update_guide("NEW INSTRUCTIONS", KNOWLEDGE))
    assert "meant to be kept were not" in str(excinfo.value)


def test_an_unsupported_guide_is_refused_without_any_write():
    before = load_detail()
    before["skills"] = [{"name": "web-search"}]
    before["guide"]["crewMemberCount"] = 2
    FakeAsyncClient.responses = [LOGIN_OK(), GUIDE_LIST(), FakeResponse(200, before)]

    with pytest.raises(guideants_admin.GuideAntsAdminError) as excinfo:
        asyncio.run(guideants_admin.update_guide("x", KNOWLEDGE))

    message = str(excinfo.value)
    assert "skills" in message and "crew member" in message
    assert not [c for c in FakeAsyncClient.calls if c["method"] == "PUT"], (
        "fail closed: nothing may be written to a guide we cannot round-trip"
    )


def test_a_missing_guide_raises_and_never_creates_one():
    FakeAsyncClient.responses = [
        LOGIN_OK(),
        FakeResponse(200, [{"id": "other", "name": "Something Else"}]),
    ]
    with pytest.raises(guideants_admin.GuideAntsAdminError, match="no GuideAnts guide named"):
        asyncio.run(guideants_admin.update_guide("x", KNOWLEDGE))
    assert [c["method"] for c in FakeAsyncClient.calls] == ["POST", "GET"]


def test_an_ambiguous_guide_name_raises():
    FakeAsyncClient.responses = [
        LOGIN_OK(),
        FakeResponse(
            200,
            [
                {"id": "a", "name": "Twilio Demo Agent"},
                {"id": "b", "name": "Twilio Demo Agent"},
            ],
        ),
    ]
    with pytest.raises(guideants_admin.GuideAntsAdminError, match="refusing to guess"):
        asyncio.run(guideants_admin.update_guide("x", KNOWLEDGE))


def test_a_paged_guide_list_is_understood():
    before = load_detail()
    after = copy.deepcopy(before)
    after["instructions"] = "x"
    FakeAsyncClient.responses = [
        LOGIN_OK(),
        FakeResponse(200, {"items": [{"id": GUIDE_ID, "name": "Twilio Demo Agent"}]}),
        FakeResponse(200, before),
        FakeResponse(200, {}),
        FakeResponse(200, after),
    ]
    assert asyncio.run(guideants_admin.update_guide("x", KNOWLEDGE))["guideId"] == GUIDE_ID


def test_unverified_instructions_trigger_exactly_one_restore_and_raise():
    before = load_detail()
    unchanged = copy.deepcopy(before)  # the PUT silently did nothing
    FakeAsyncClient.responses = [
        LOGIN_OK(),
        GUIDE_LIST(),
        FakeResponse(200, before),
        FakeResponse(200, {}),
        FakeResponse(200, unchanged),
        FakeResponse(200, {}),  # the restore PUT
    ]

    with pytest.raises(guideants_admin.GuideAntsAdminError) as excinfo:
        asyncio.run(guideants_admin.update_guide("NEW INSTRUCTIONS", KNOWLEDGE))

    assert "instructions are not what was sent" in str(excinfo.value)
    assert "instructions and settings were restored" in str(excinfo.value)
    puts = [c for c in FakeAsyncClient.calls if c["method"] == "PUT"]
    assert len(puts) == 2, "one update, one restore -- and no retry loop"
    assert puts[1]["json"] == guide_dto.build_update_dto(before, before["instructions"])


def test_collateral_damage_triggers_a_restore_and_names_what_moved():
    before = load_detail()
    damaged = copy.deepcopy(before)
    damaged["instructions"] = "NEW INSTRUCTIONS"
    damaged["contextOptions"] = []  # exactly what the import endpoint did
    FakeAsyncClient.responses = [
        LOGIN_OK(),
        GUIDE_LIST(),
        FakeResponse(200, before),
        FakeResponse(200, {}),
        FakeResponse(200, damaged),
        FakeResponse(200, {}),
    ]

    with pytest.raises(guideants_admin.GuideAntsAdminError) as excinfo:
        asyncio.run(guideants_admin.update_guide("NEW INSTRUCTIONS", KNOWLEDGE))

    message = str(excinfo.value)
    assert "changed more than the instructions" in message
    assert "contextOptions" in message
    assert len([c for c in FakeAsyncClient.calls if c["method"] == "PUT"]) == 2


def test_a_failed_restore_is_reported_rather_than_hidden():
    before = load_detail()
    FakeAsyncClient.responses = [
        LOGIN_OK(),
        GUIDE_LIST(),
        FakeResponse(200, before),
        FakeResponse(200, {}),
        FakeResponse(200, copy.deepcopy(before)),
        FakeResponse(500, {"error": "restore exploded"}),
    ]
    with pytest.raises(guideants_admin.GuideAntsAdminError) as excinfo:
        asyncio.run(guideants_admin.update_guide("NEW INSTRUCTIONS", KNOWLEDGE))

    assert "Restoring the previous state ALSO failed" in str(excinfo.value)
    assert "restore exploded" in str(excinfo.value)


def test_a_401_triggers_exactly_one_relogin_and_retry():
    before = load_detail()
    after = copy.deepcopy(before)
    after["instructions"] = "x"
    FakeAsyncClient.responses = [
        LOGIN_OK(),
        GUIDE_LIST(),
        FakeResponse(401, {"error": "expired"}),  # detail GET -> token expired
        LOGIN_OK(),                                # re-login
        FakeResponse(200, before),                 # retry
        FakeResponse(200, {}),
        FakeResponse(200, after),
    ]
    assert asyncio.run(guideants_admin.update_guide("x", KNOWLEDGE))["guideId"] == GUIDE_ID
    assert [c["method"] for c in FakeAsyncClient.calls] == [
        "POST", "GET", "GET", "POST", "GET", "PUT", "GET"
    ]


def test_a_second_401_gives_up():
    FakeAsyncClient.responses = [
        LOGIN_OK(),
        FakeResponse(401, {"error": "expired"}),
        LOGIN_OK(),
        FakeResponse(401, {"error": "expired"}),
    ]
    with pytest.raises(guideants_admin.GuideAntsAdminError, match="401"):
        asyncio.run(guideants_admin.update_guide("x", KNOWLEDGE))


def test_failed_login_raises_clearly_without_leaking_the_password():
    FakeAsyncClient.responses = [
        FakeResponse(401, {"message": "Invalid email or password."})
    ]
    with pytest.raises(guideants_admin.GuideAntsAdminError) as excinfo:
        asyncio.run(guideants_admin.update_guide("x", KNOWLEDGE))
    assert "log in" in str(excinfo.value)
    assert config.GUIDEANTS_ADMIN_PASSWORD not in str(excinfo.value)


def test_no_error_ever_carries_the_password():
    """These strings land in a GuidePublication row and on the console."""
    for responses in (
        [FakeResponse(500, {"error": "boom"})],
        [LOGIN_OK(), FakeResponse(403, {"error": "forbidden"})],
        [LOGIN_OK(), GUIDE_LIST(), FakeResponse(500, {"error": "boom"})],
    ):
        guideants_admin.reset_session()
        FakeAsyncClient.responses = list(responses)
        with pytest.raises(guideants_admin.GuideAntsAdminError) as excinfo:
            asyncio.run(guideants_admin.update_guide("x", KNOWLEDGE))
        assert "hunter2-secret" not in str(excinfo.value)


def test_a_rejected_update_surfaces_the_server_message():
    before = load_detail()
    FakeAsyncClient.responses = [
        LOGIN_OK(),
        GUIDE_LIST(),
        FakeResponse(200, before),
        FakeResponse(400, {"error": "Model not available"}),
    ]
    with pytest.raises(guideants_admin.GuideAntsAdminError, match="Model not available"):
        asyncio.run(guideants_admin.update_guide("x", KNOWLEDGE))


def test_unreachable_host_raises_a_clean_error():
    import httpx

    FakeAsyncClient.responses = [httpx.ConnectError("refused")]
    with pytest.raises(guideants_admin.GuideAntsAdminError, match="unreachable"):
        asyncio.run(guideants_admin.update_guide("x", KNOWLEDGE))


def test_an_unreachable_host_mid_flow_raises_a_clean_error():
    import httpx

    FakeAsyncClient.responses = [LOGIN_OK(), httpx.ReadTimeout("slow")]
    with pytest.raises(guideants_admin.GuideAntsAdminError, match="unreachable"):
        asyncio.run(guideants_admin.update_guide("x", KNOWLEDGE))


def test_unconfigured_update_raises_not_configured(monkeypatch):
    monkeypatch.setattr(config, "GUIDEANTS_ADMIN_PASSWORD", "")
    with pytest.raises(guideants_admin.GuideAntsNotConfigured):
        asyncio.run(guideants_admin.update_guide("x", KNOWLEDGE))
    assert FakeAsyncClient.calls == []


@pytest.mark.parametrize("body", ["Guide update failed.", ["manifest not found"]])
def test_a_non_dict_error_body_still_raises_a_recorded_admin_error(body):
    """publisher.publish() catches only GuideAntsAdminError. An
    AttributeError from .get() on a bare string or list body would escape
    uncaught, roll back the GuidePublication's failure row, and return an
    unrecorded 500 -- defeating "every failure is recorded"."""
    FakeAsyncClient.responses = [LOGIN_OK(), FakeResponse(400, body)]
    with pytest.raises(guideants_admin.GuideAntsAdminError) as excinfo:
        asyncio.run(guideants_admin.update_guide("x", KNOWLEDGE))

    assert not isinstance(excinfo.value, AttributeError)
    assert "HTTP 400" in str(excinfo.value)
    assert str(body) in str(excinfo.value)


def test_an_unparseable_error_body_falls_back_to_the_raw_text():
    class NotJson(FakeResponse):
        def json(self):
            raise ValueError("no JSON")

    FakeAsyncClient.responses = [LOGIN_OK(), NotJson(500, "<html>502 Bad Gateway</html>")]
    with pytest.raises(guideants_admin.GuideAntsAdminError, match="Bad Gateway"):
        asyncio.run(guideants_admin.update_guide("x", KNOWLEDGE))


def test_an_unrecognized_guide_list_is_refused():
    FakeAsyncClient.responses = [LOGIN_OK(), FakeResponse(200, "not a list")]
    with pytest.raises(guideants_admin.GuideAntsAdminError, match="unrecognized guide list"):
        asyncio.run(guideants_admin.update_guide("x", KNOWLEDGE))


def test_an_unrecognized_detail_body_is_refused_before_any_write():
    FakeAsyncClient.responses = [LOGIN_OK(), GUIDE_LIST(), FakeResponse(200, {"oops": 1})]
    with pytest.raises(guideants_admin.GuideAntsAdminError, match="unrecognized guide body"):
        asyncio.run(guideants_admin.update_guide("x", KNOWLEDGE))
    assert not [c for c in FakeAsyncClient.calls if c["method"] == "PUT"]


def test_a_read_back_with_no_file_list_restores_every_file_it_knew_about():
    """Defensive: an `after` body that reports no files at all must not make
    the restore send an empty keep-list, which would delete the lot."""
    before = load_detail()
    after = {"guide": before["guide"], "instructions": "not what was sent"}
    FakeAsyncClient.responses = [
        LOGIN_OK(), GUIDE_LIST(), FakeResponse(200, before),
        FakeResponse(200, {}), FakeResponse(200, after),
        FakeResponse(200, {}),
    ]

    with pytest.raises(guideants_admin.GuideAntsAdminError):
        asyncio.run(guideants_admin.update_guide("NEW INSTRUCTIONS", KNOWLEDGE))

    restore = [c for c in FakeAsyncClient.calls if c["method"] == "PUT"][1]
    assert restore["json"]["fileIdsToKeep"] == [f["id"] for f in before["files"]]


# --------------------------------------------------------------------------
# Tool sources: an empty guide is given the template's
# --------------------------------------------------------------------------


def _server_side_tools():
    """The tools as GuideAnts hands them back after a write: it derives the
    operations from the spec that was sent."""
    return [
        {
            "name": name,
            "openApiSpec": text,
            "apiHost": name,
            "authConfig": None,
            "operations": [
                {"id": f"{name}-{op}", "operationId": op}
                for op in guide_dto.spec_operation_ids(text)
            ],
        }
        for name, text in template.load_tool_sources().items()
    ]


def _toolless_guide():
    before = load_detail()
    before["customTools"] = []
    return before


def test_publishing_to_a_guide_with_no_tools_adds_the_template_tools():
    before = _toolless_guide()
    after = copy.deepcopy(before)
    after["instructions"] = "NEW"
    after["customTools"] = _server_side_tools()
    FakeAsyncClient.responses = [
        LOGIN_OK(), GUIDE_LIST(), FakeResponse(200, before),
        FakeResponse(200, {}), FakeResponse(200, after),
    ]

    result = asyncio.run(guideants_admin.update_guide("NEW", KNOWLEDGE))

    put = next(c for c in FakeAsyncClient.calls if c["method"] == "PUT")
    sent = {tool["name"]: tool for tool in put["json"]["customTools"]}
    assert sorted(sent) == ["caller-phone", "voice-receptionist"]
    # The spec goes up exactly as the file has it; the server does the rest.
    for name, text in template.load_tool_sources().items():
        assert sent[name]["openApiSpec"] == text
        assert sent[name]["apiHost"] == name
    assert result["warnings"] == [
        "Added tool source(s) the guide was missing: voice-receptionist, caller-phone."
    ]


def test_a_guide_that_already_has_its_tools_is_sent_them_unchanged():
    before, _ = script_happy_path()
    result = asyncio.run(guideants_admin.update_guide("NEW INSTRUCTIONS", KNOWLEDGE))

    put = next(c for c in FakeAsyncClient.calls if c["method"] == "PUT")
    assert put["json"]["customTools"] == before["customTools"]
    assert result["warnings"] == []


def test_only_the_missing_tool_source_is_added():
    before = load_detail()
    kept = next(t for t in before["customTools"] if t["name"] == "caller-phone")
    before["customTools"] = [kept]
    missing = guide_dto.missing_custom_tools(before, template.load_tool_sources())
    assert [t["name"] for t in missing] == ["voice-receptionist"]


def test_added_tools_that_come_back_without_operations_fail_verification():
    before = _toolless_guide()
    after = copy.deepcopy(before)
    after["instructions"] = "NEW"
    after["customTools"] = _server_side_tools()
    after["customTools"][0]["operations"] = []
    FakeAsyncClient.responses = [
        LOGIN_OK(), GUIDE_LIST(), FakeResponse(200, before),
        FakeResponse(200, {}), FakeResponse(200, after),
        FakeResponse(200, {}),  # the restore PUT
    ]

    with pytest.raises(guideants_admin.GuideAntsAdminError) as excinfo:
        asyncio.run(guideants_admin.update_guide("NEW", KNOWLEDGE))

    assert "expected operations" in str(excinfo.value)
