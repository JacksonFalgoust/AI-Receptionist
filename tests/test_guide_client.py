import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import openai
import pytest

from app import guide_client
from app.guide_client import GuideSession, build_input


async def _collect(aiter):
    return [item async for item in aiter]


class FakeStream:
    """Minimal stand-in for the openai SDK's responses streaming context
    manager: an async context manager that is also an async iterator."""

    def __init__(self, events, gate: asyncio.Event | None = None):
        self._events = list(events)
        self._gate = gate
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        self.closed = True
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._gate is not None:
            await self._gate.wait()
        if not self._events:
            raise StopAsyncIteration
        return self._events.pop(0)


def _bad_request_error(code: str) -> openai.BadRequestError:
    response = httpx.Response(400, request=httpx.Request("POST", "http://test/v1/responses"))
    return openai.BadRequestError(code, response=response, body={"code": code, "message": code})


def test_first_turn_streams_and_captures_conversation_from_created_event(monkeypatch):
    events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation="conv_abc")),
        SimpleNamespace(type="response.output_text.delta", delta="Hel"),
        SimpleNamespace(type="response.output_text.delta", delta="lo"),
        SimpleNamespace(type="response.completed", response=SimpleNamespace(conversation="conv_abc")),
    ]
    stream = FakeStream(events)
    create = AsyncMock(return_value=stream)
    fake_client = SimpleNamespace(responses=SimpleNamespace(create=create))
    monkeypatch.setattr(guide_client, "_get_client", lambda: fake_client)

    session = GuideSession()
    deltas = asyncio.run(_collect(guide_client.stream_reply("hi", session)))

    assert deltas == ["Hel", "lo"]
    assert session.conversation_id == "conv_abc"
    assert session.stream_missing_conversation is False
    assert stream.closed
    _, kwargs = create.call_args
    assert kwargs["stream"] is True
    assert "conversation" not in kwargs
    assert kwargs["input"] == "hi"


def test_first_turn_accepts_object_shaped_conversation(monkeypatch):
    events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation=SimpleNamespace(id="conv_abc"))),
        SimpleNamespace(type="response.completed", response=SimpleNamespace(conversation=SimpleNamespace(id="conv_abc"))),
    ]
    stream = FakeStream(events)
    create = AsyncMock(return_value=stream)
    fake_client = SimpleNamespace(responses=SimpleNamespace(create=create))
    monkeypatch.setattr(guide_client, "_get_client", lambda: fake_client)

    session = GuideSession()
    asyncio.run(_collect(guide_client.stream_reply("hi", session)))

    assert session.conversation_id == "conv_abc"


def test_conversation_captured_from_completed_when_created_lacks_it(monkeypatch):
    events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation=None)),
        SimpleNamespace(type="response.output_text.delta", delta="Hi"),
        SimpleNamespace(type="response.completed", response=SimpleNamespace(conversation="conv_late")),
    ]
    stream = FakeStream(events)
    create = AsyncMock(return_value=stream)
    fake_client = SimpleNamespace(responses=SimpleNamespace(create=create))
    monkeypatch.setattr(guide_client, "_get_client", lambda: fake_client)

    session = GuideSession()
    deltas = asyncio.run(_collect(guide_client.stream_reply("hi", session)))

    assert deltas == ["Hi"]
    assert session.conversation_id == "conv_late"
    assert session.stream_missing_conversation is False


def test_continuation_turn_streams_with_conversation_param(monkeypatch):
    events = [
        SimpleNamespace(type="response.created"),
        SimpleNamespace(type="response.output_text.delta", delta="Hel"),
        SimpleNamespace(type="response.output_text.delta", delta="lo"),
        SimpleNamespace(type="response.output_text.done"),
        SimpleNamespace(type="response.completed"),
    ]
    stream = FakeStream(events)
    create = AsyncMock(return_value=stream)
    fake_client = SimpleNamespace(responses=SimpleNamespace(create=create))
    monkeypatch.setattr(guide_client, "_get_client", lambda: fake_client)

    session = GuideSession(conversation_id="conv_abc")
    deltas = asyncio.run(_collect(guide_client.stream_reply("what did I say?", session)))

    assert deltas == ["Hel", "lo"]
    assert stream.closed
    _, kwargs = create.call_args
    assert kwargs["stream"] is True
    assert kwargs["conversation"] == "conv_abc"
    assert kwargs["input"] == "what did I say?"
    assert session.conversation_id == "conv_abc"


def test_lost_conversation_recovers_with_fresh_streaming_call(monkeypatch):
    retry_events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation="conv_new")),
        SimpleNamespace(type="response.output_text.delta", delta="Fresh reply"),
        SimpleNamespace(type="response.completed", response=SimpleNamespace(conversation="conv_new")),
    ]
    retry_stream = FakeStream(retry_events)
    create = AsyncMock(side_effect=[_bad_request_error("conversation_not_found"), retry_stream])
    fake_client = SimpleNamespace(responses=SimpleNamespace(create=create))
    monkeypatch.setattr(guide_client, "_get_client", lambda: fake_client)

    session = GuideSession(conversation_id="conv_stale")
    deltas = asyncio.run(_collect(guide_client.stream_reply("hi again", session)))

    assert deltas == ["Fresh reply"]
    assert session.conversation_id == "conv_new"
    assert create.call_count == 2
    first_kwargs = create.call_args_list[0].kwargs
    second_kwargs = create.call_args_list[1].kwargs
    assert first_kwargs["conversation"] == "conv_stale"
    assert first_kwargs["stream"] is True
    assert "conversation" not in second_kwargs
    assert second_kwargs["stream"] is True
    assert retry_stream.closed


def test_other_bad_request_errors_propagate(monkeypatch):
    create = AsyncMock(side_effect=_bad_request_error("endpoint_disabled"))
    fake_client = SimpleNamespace(responses=SimpleNamespace(create=create))
    monkeypatch.setattr(guide_client, "_get_client", lambda: fake_client)

    session = GuideSession(conversation_id="conv_abc")
    with pytest.raises(openai.BadRequestError):
        asyncio.run(_collect(guide_client.stream_reply("hi", session)))
    assert create.call_count == 1


def test_cancellation_closes_stream(monkeypatch):
    gate = asyncio.Event()
    events = [SimpleNamespace(type="response.output_text.delta", delta="Hel")]
    stream = FakeStream(events, gate=gate)
    create = AsyncMock(return_value=stream)
    fake_client = SimpleNamespace(responses=SimpleNamespace(create=create))
    monkeypatch.setattr(guide_client, "_get_client", lambda: fake_client)

    async def scenario():
        session = GuideSession(conversation_id="conv_abc")
        gen = guide_client.stream_reply("hi", session)
        task = asyncio.ensure_future(gen.__anext__())
        await asyncio.sleep(0)  # let the task reach the blocked __anext__
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await gen.aclose()

    asyncio.run(scenario())
    assert stream.closed


def test_aclose_after_first_delta_closes_underlying_stream(monkeypatch):
    # Mirrors a barge-in mid-reply: the caller has already consumed one delta
    # (the generator is suspended at a `yield`, not blocked inside an await)
    # and then closes the generator outright. `stream_reply` wraps its inner
    # `_stream_turn` generator in `contextlib.aclosing` specifically so this
    # still closes the underlying SSE stream deterministically.
    events = [
        SimpleNamespace(type="response.output_text.delta", delta="Hel"),
        SimpleNamespace(type="response.output_text.delta", delta="lo"),
    ]
    stream = FakeStream(events)
    create = AsyncMock(return_value=stream)
    fake_client = SimpleNamespace(responses=SimpleNamespace(create=create))
    monkeypatch.setattr(guide_client, "_get_client", lambda: fake_client)

    async def scenario():
        session = GuideSession(conversation_id="conv_abc")
        gen = guide_client.stream_reply("hi", session)
        first = await gen.__anext__()
        await gen.aclose()
        return first

    first = asyncio.run(scenario())
    assert first == "Hel"
    assert stream.closed


def test_missing_conversation_falls_back_to_non_streaming_next_turn(monkeypatch):
    turn1_events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation=None)),
        SimpleNamespace(type="response.output_text.delta", delta="ok"),
        SimpleNamespace(type="response.completed", response=SimpleNamespace(conversation=None)),
    ]
    turn1_stream = FakeStream(turn1_events)
    turn2_response = SimpleNamespace(id="resp_x", conversation="conv_new", output_text="ok again")
    create = AsyncMock(side_effect=[turn1_stream, turn2_response])
    fake_client = SimpleNamespace(responses=SimpleNamespace(create=create))
    monkeypatch.setattr(guide_client, "_get_client", lambda: fake_client)

    session = GuideSession()
    deltas = asyncio.run(_collect(guide_client.stream_reply("hi", session)))

    assert deltas == ["ok"]
    assert session.conversation_id is None
    assert session.stream_missing_conversation is True

    # Next turn falls back to the non-streaming path to obtain an id.
    deltas2 = asyncio.run(_collect(guide_client.stream_reply("hi again", session)))
    assert deltas2 == ["ok again"]
    assert session.conversation_id == "conv_new"
    assert create.call_count == 2
    second_kwargs = create.call_args_list[1].kwargs
    assert second_kwargs.get("stream") is not True
    assert "conversation" not in second_kwargs
    assert "conversation" not in create.call_args_list[1].kwargs


def test_build_input_no_note_when_no_interruption():
    assert build_input("what are your hours?", None) == "what are your hours?"
    assert build_input("what are your hours?", "") == "what are your hours?"


def test_build_input_folds_note_when_interrupted():
    partial = "Our hours are Monday through Saturday, six a.m. to nine p.m., and on Sundays we"
    result = build_input("what did you say?", partial)
    assert result.endswith("what did you say?")
    assert partial[-20:] in result
    assert result.startswith("[Note:")


def test_build_input_truncates_long_partial():
    partial = "x" * 500
    result = build_input("go on", partial)
    assert "x" * 500 not in result
    assert "x" * 150 in result
