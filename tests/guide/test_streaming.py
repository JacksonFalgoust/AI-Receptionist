import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import openai
import pytest

from app import config
from app.guide import connection, sentinel, streaming
from app.guide.session import GuideSession


@pytest.fixture(autouse=True)
def _no_sentinel_gating(monkeypatch):
    """These tests exercise conversation continuation and tool
    orchestration, not the sentinel-phrase gate itself -- see
    test_final_answer_sentinel.py for that. Disable gating so every delta
    streams through unconditionally, matching an empty
    config.FINAL_ANSWER_SENTINEL (the app's control/no-op mode) -- the
    compiled patterns are module globals set once at import, so they're
    monkeypatched directly rather than through config."""
    monkeypatch.setattr(sentinel, "SENTINEL_STRICT", None)
    monkeypatch.setattr(sentinel, "SENTINEL_LOOSE", None)


async def _collect(aiter):
    return [item async for item in aiter]


def _texts(events) -> list[str]:
    return [e.text for e in events if isinstance(e, streaming.Delta)]


def _tool_events(events) -> list["streaming.ToolCallStarted"]:
    return [e for e in events if isinstance(e, streaming.ToolCallStarted)]


class _FakeClient(SimpleNamespace):
    """Stand-in for AsyncOpenAI: exposes `.responses.create` and a
    `.with_options()` that returns the same client (the real SDK returns a
    reconfigured copy; sharing one is fine for assertions here). app/guide/streaming.py
    calls with_options(max_retries=0) on tool-output submissions; each such
    call's kwargs are recorded in `with_options_calls` for assertions."""

    def __init__(self, **kwargs):
        super().__init__(with_options_calls=[], **kwargs)

    def with_options(self, **kwargs):
        self.with_options_calls.append(kwargs)
        return self


def _fake_client(create) -> _FakeClient:
    return _FakeClient(responses=SimpleNamespace(create=create))


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
    fake_client = _fake_client(create)
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    session = GuideSession()
    reply_events = asyncio.run(_collect(streaming.stream_reply("hi", session)))

    assert _texts(reply_events) == ["Hel", "lo"]
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
    fake_client = _fake_client(create)
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    session = GuideSession()
    asyncio.run(_collect(streaming.stream_reply("hi", session)))

    assert session.conversation_id == "conv_abc"


def test_conversation_captured_from_completed_when_created_lacks_it(monkeypatch):
    events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation=None)),
        SimpleNamespace(type="response.output_text.delta", delta="Hi"),
        SimpleNamespace(type="response.completed", response=SimpleNamespace(conversation="conv_late")),
    ]
    stream = FakeStream(events)
    create = AsyncMock(return_value=stream)
    fake_client = _fake_client(create)
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    session = GuideSession()
    reply_events = asyncio.run(_collect(streaming.stream_reply("hi", session)))

    assert _texts(reply_events) == ["Hi"]
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
    fake_client = _fake_client(create)
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    session = GuideSession(conversation_id="conv_abc")
    reply_events = asyncio.run(_collect(streaming.stream_reply("what did I say?", session)))

    assert _texts(reply_events) == ["Hel", "lo"]
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
    fake_client = _fake_client(create)
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    session = GuideSession(conversation_id="conv_stale")
    reply_events = asyncio.run(_collect(streaming.stream_reply("hi again", session)))

    assert _texts(reply_events) == ["Fresh reply"]
    assert session.conversation_id == "conv_new"
    assert create.call_count == 2
    first_kwargs = create.call_args_list[0].kwargs
    second_kwargs = create.call_args_list[1].kwargs
    assert first_kwargs["conversation"] == "conv_stale"
    assert first_kwargs["stream"] is True
    assert "conversation" not in second_kwargs
    assert second_kwargs["stream"] is True
    assert retry_stream.closed


def test_lost_conversation_does_not_retry_once_text_was_already_spoken(monkeypatch):
    # A BadRequestError after this turn already emitted a Delta must not be
    # retried -- a retry would re-speak text the caller already heard. Only
    # the id is cleared, so the *next* caller turn recovers on a fresh
    # conversation.
    tool_call_events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation="conv_abc")),
        SimpleNamespace(type="response.output_text.delta", delta="Sure, one sec."),
        SimpleNamespace(type="response.output_item.done", item=_function_call_item("call_1")),
        SimpleNamespace(
            type="response.completed",
            response=SimpleNamespace(conversation="conv_abc", id="resp_1", output=[]),
        ),
    ]
    create = AsyncMock(
        side_effect=[FakeStream(tool_call_events), _bad_request_error("tool_results_not_pending")]
    )
    fake_client = _fake_client(create)
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    session = GuideSession(conversation_id="conv_abc", caller_phone="+15551234567")
    with pytest.raises(openai.BadRequestError):
        asyncio.run(_collect(streaming.stream_reply("what's my number?", session)))

    assert session.conversation_id is None
    assert create.call_count == 2


def test_stale_tool_result_recovers_with_fresh_conversation(monkeypatch):
    # A tool round-trip whose output submission is rejected as no longer
    # pending (the turn was cancelled/completed server-side, e.g. a mid-stream
    # disconnect) must recover like a lost conversation rather than crash.
    monkeypatch.setattr(config, "BOOQABLE_API_KEY", "test-booqable-key")
    tool_call_events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation="conv_abc")),
        SimpleNamespace(type="response.output_item.done", item=_function_call_item("call_1")),
        SimpleNamespace(
            type="response.completed",
            response=SimpleNamespace(conversation="conv_abc", id="resp_1", output=[]),
        ),
    ]
    fresh_events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation="conv_new")),
        SimpleNamespace(type="response.output_text.delta", delta="Fresh reply"),
        SimpleNamespace(type="response.completed", response=SimpleNamespace(conversation="conv_new")),
    ]
    fresh_stream = FakeStream(fresh_events)
    create = AsyncMock(
        side_effect=[
            FakeStream(tool_call_events),
            _bad_request_error("tool_results_not_pending"),
            fresh_stream,
        ]
    )
    fake_client = _fake_client(create)
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    session = GuideSession(conversation_id="conv_abc", caller_phone="+15551234567")
    reply_events = asyncio.run(_collect(streaming.stream_reply("what's my number?", session)))

    assert _texts(reply_events) == ["Fresh reply"]
    assert session.conversation_id == "conv_new"
    assert create.call_count == 3
    # The rejected submission carried the tool output on the original convo...
    assert create.call_args_list[1].kwargs["conversation"] == "conv_abc"
    assert create.call_args_list[1].kwargs["input"][0]["type"] == "function_call_output"
    # ...and the fresh retry re-asks the original utterance on a new convo.
    assert "conversation" not in create.call_args_list[2].kwargs
    assert create.call_args_list[2].kwargs["input"] == "what's my number?"
    assert fresh_stream.closed


def test_stale_tool_result_retries_on_a_fresh_conversation_only_once(monkeypatch):
    # If the fresh-conversation retry is itself rejected (e.g. GuideAnts
    # rejects every tool result), the turn must fail instead of opening
    # fresh conversations forever.
    monkeypatch.setattr(config, "BOOQABLE_API_KEY", "test-booqable-key")

    def tool_call_stream(conv):
        return FakeStream([
            SimpleNamespace(type="response.created", response=SimpleNamespace(conversation=conv)),
            SimpleNamespace(type="response.output_item.done", item=_function_call_item("call_1")),
            SimpleNamespace(
                type="response.completed",
                response=SimpleNamespace(conversation=conv, id="resp_1", output=[]),
            ),
        ])

    create = AsyncMock(
        side_effect=[
            tool_call_stream("conv_abc"),
            _bad_request_error("tool_results_not_pending"),
            tool_call_stream("conv_new"),
            _bad_request_error("tool_results_not_pending"),
            tool_call_stream("conv_newer"),
            _bad_request_error("tool_results_not_pending"),
        ]
    )
    fake_client = _fake_client(create)
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    session = GuideSession(conversation_id="conv_abc", caller_phone="+15551234567")
    with pytest.raises(openai.BadRequestError):
        asyncio.run(_collect(streaming.stream_reply("what's my number?", session)))

    assert create.call_count == 4
    assert session.conversation_id is None


def test_tool_output_submission_disables_sdk_retries(monkeypatch):
    # The tool-output submission (input is a list) must go out with retries
    # disabled, since re-POSTing it after a blip is what produces a stale
    # tool_results_not_pending. The initial turn keeps its retries.
    tool_call_events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation="conv_abc")),
        SimpleNamespace(type="response.output_item.done", item=_function_call_item("call_1")),
        SimpleNamespace(
            type="response.completed",
            response=SimpleNamespace(conversation="conv_abc", id="resp_1", output=[]),
        ),
    ]
    text_events = [
        SimpleNamespace(type="response.output_text.delta", delta="ok"),
        SimpleNamespace(
            type="response.completed",
            response=SimpleNamespace(conversation="conv_abc", id="resp_2", output=[]),
        ),
    ]
    create = AsyncMock(side_effect=[FakeStream(tool_call_events), FakeStream(text_events)])
    fake_client = _fake_client(create)
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    session = GuideSession(conversation_id="conv_abc", caller_phone="+15551234567")
    asyncio.run(_collect(streaming.stream_reply("what's my number?", session)))

    # Exactly the submission (the 2nd create) went through with_options; the
    # first turn did not.
    assert fake_client.with_options_calls == [{"max_retries": 0}]


def test_other_bad_request_errors_propagate(monkeypatch):
    create = AsyncMock(side_effect=_bad_request_error("endpoint_disabled"))
    fake_client = _fake_client(create)
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    session = GuideSession(conversation_id="conv_abc")
    with pytest.raises(openai.BadRequestError):
        asyncio.run(_collect(streaming.stream_reply("hi", session)))
    assert create.call_count == 1


def test_cancellation_closes_stream(monkeypatch):
    gate = asyncio.Event()
    events = [SimpleNamespace(type="response.output_text.delta", delta="Hel")]
    stream = FakeStream(events, gate=gate)
    create = AsyncMock(return_value=stream)
    fake_client = _fake_client(create)
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    async def scenario():
        session = GuideSession(conversation_id="conv_abc")
        gen = streaming.stream_reply("hi", session)
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
    fake_client = _fake_client(create)
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    async def scenario():
        session = GuideSession(conversation_id="conv_abc")
        gen = streaming.stream_reply("hi", session)
        first = await gen.__anext__()
        await gen.aclose()
        return first

    first = asyncio.run(scenario())
    assert first == streaming.Delta("Hel")
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
    fake_client = _fake_client(create)
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    session = GuideSession()
    reply_events = asyncio.run(_collect(streaming.stream_reply("hi", session)))

    assert _texts(reply_events) == ["ok"]
    assert session.conversation_id is None
    assert session.stream_missing_conversation is True

    # Next turn falls back to the non-streaming path to obtain an id.
    reply_events2 = asyncio.run(_collect(streaming.stream_reply("hi again", session)))
    assert _texts(reply_events2) == ["ok again"]
    assert session.conversation_id == "conv_new"
    assert create.call_count == 2
    second_kwargs = create.call_args_list[1].kwargs
    assert second_kwargs.get("stream") is not True
    assert "conversation" not in second_kwargs
    assert "conversation" not in create.call_args_list[1].kwargs


def _function_call_item(call_id: str, name: str = "get_caller_phone_number", arguments: str = "{}"):
    return SimpleNamespace(type="function_call", call_id=call_id, name=name, arguments=arguments)


def test_streamed_tool_call_round_trip_yields_tool_call_started_then_text(monkeypatch):
    tool_call_events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation="conv_abc")),
        SimpleNamespace(type="response.output_item.done", item=_function_call_item("call_1")),
        SimpleNamespace(
            type="response.completed",
            response=SimpleNamespace(conversation="conv_abc", id="resp_1", output=[]),
        ),
    ]
    text_events = [
        SimpleNamespace(type="response.output_text.delta", delta="Your number is "),
        SimpleNamespace(type="response.output_text.delta", delta="555-1234."),
        SimpleNamespace(
            type="response.completed",
            response=SimpleNamespace(conversation="conv_abc", id="resp_2", output=[]),
        ),
    ]
    tool_call_stream = FakeStream(tool_call_events)
    text_stream = FakeStream(text_events)
    create = AsyncMock(side_effect=[tool_call_stream, text_stream])
    fake_client = _fake_client(create)
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    session = GuideSession(conversation_id="conv_abc", caller_phone="+15551234567")
    reply_events = asyncio.run(_collect(streaming.stream_reply("what's my number?", session)))

    assert _texts(reply_events) == ["Your number is ", "555-1234."]
    tool_events = _tool_events(reply_events)
    assert len(tool_events) == 1
    assert tool_events[0].names == ("get_caller_phone_number",)
    # The ToolCallStarted event precedes the answer's text.
    assert reply_events.index(tool_events[0]) < reply_events.index(streaming.Delta("Your number is "))
    assert create.call_count == 2
    first_kwargs = create.call_args_list[0].kwargs
    second_kwargs = create.call_args_list[1].kwargs
    assert first_kwargs["input"] == "what's my number?"
    # The tool is declared on the guide in GuideAnts (a Client Actions tool
    # source), not attached by this app -- no `tools` kwarg is sent.
    assert "tools" not in first_kwargs
    assert "tools" not in second_kwargs
    assert second_kwargs["conversation"] == "conv_abc"
    assert second_kwargs["input"] == [
        {
            "type": "function_call_output",
            "call_id": "call_1",
            "output": json.dumps({"phone_number": "+15551234567"}),
        }
    ]
    assert tool_call_stream.closed
    assert text_stream.closed


def test_function_call_backstop_from_completed_output(monkeypatch):
    # No response.output_item.done event at all -- only response.completed's
    # embedded response.output carries the function_call. Covers a GuideAnts
    # build that doesn't stream discrete tool-call output_item events.
    tool_call_events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation="conv_abc")),
        SimpleNamespace(
            type="response.completed",
            response=SimpleNamespace(conversation="conv_abc", id="resp_1", output=[_function_call_item("call_9")]),
        ),
    ]
    text_events = [
        SimpleNamespace(type="response.output_text.delta", delta="Sure."),
        SimpleNamespace(
            type="response.completed",
            response=SimpleNamespace(conversation="conv_abc", id="resp_2", output=[]),
        ),
    ]
    create = AsyncMock(side_effect=[FakeStream(tool_call_events), FakeStream(text_events)])
    fake_client = _fake_client(create)
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    session = GuideSession(conversation_id="conv_abc", caller_phone="555")
    reply_events = asyncio.run(_collect(streaming.stream_reply("ok", session)))

    assert _texts(reply_events) == ["Sure."]
    assert create.call_count == 2
    second_input = create.call_args_list[1].kwargs["input"]
    assert second_input[0]["call_id"] == "call_9"


def test_tool_loop_stops_at_iteration_bound(monkeypatch):
    def tool_call_stream(call_id: str) -> FakeStream:
        return FakeStream(
            [
                SimpleNamespace(type="response.output_item.done", item=_function_call_item(call_id)),
                SimpleNamespace(
                    type="response.completed",
                    response=SimpleNamespace(conversation="conv_abc", id=f"resp_{call_id}", output=[]),
                ),
            ]
        )

    create = AsyncMock(side_effect=[tool_call_stream(f"call_{i}") for i in range(10)])
    fake_client = _fake_client(create)
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    session = GuideSession(conversation_id="conv_abc")
    reply_events = asyncio.run(_collect(streaming.stream_reply("hi", session)))

    assert _texts(reply_events) == []
    assert create.call_count == streaming._MAX_TOOL_ITERATIONS


def test_no_tools_kwarg_sent_on_any_turn(monkeypatch):
    # The tool is declared on the guide in GuideAnts (a Client Actions tool
    # source, see guide-demo/caller-phone-client-tool.json) -- this app never
    # attaches a `tools` kwarg itself, on any of the three request shapes it
    # can send (first turn, continuation, or the non-streaming fallback).
    events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation="conv_abc")),
        SimpleNamespace(type="response.completed", response=SimpleNamespace(conversation="conv_abc", output=[])),
    ]
    create = AsyncMock(return_value=FakeStream(events))
    fake_client = _fake_client(create)
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    session = GuideSession()
    asyncio.run(_collect(streaming.stream_reply("hi", session)))
    assert "tools" not in create.call_args.kwargs

    session2 = GuideSession(conversation_id="conv_abc")
    asyncio.run(_collect(streaming.stream_reply("hi", session2)))
    assert "tools" not in create.call_args.kwargs

    non_streaming_response = SimpleNamespace(id="resp_x", conversation="conv_new", output_text="ok", output=[])
    create.side_effect = [non_streaming_response]
    session3 = GuideSession(stream_missing_conversation=True)
    reply_events = asyncio.run(_collect(streaming.stream_reply("hi", session3)))
    assert _texts(reply_events) == ["ok"]
    assert "tools" not in create.call_args.kwargs


def test_aclose_during_tool_round_trip_closes_active_stream(monkeypatch):
    # Mirrors test_cancellation_closes_stream, but the cancellation lands
    # while the *second* request (the tool-output follow-up) is in flight --
    # both nested aclosing layers must still close whichever stream is live.
    gate = asyncio.Event()
    tool_call_events = [
        SimpleNamespace(type="response.output_item.done", item=_function_call_item("call_1")),
        SimpleNamespace(type="response.completed", response=SimpleNamespace(conversation="conv_abc", output=[])),
    ]
    tool_call_stream = FakeStream(tool_call_events)
    text_stream = FakeStream([SimpleNamespace(type="response.output_text.delta", delta="Sure")], gate=gate)
    create = AsyncMock(side_effect=[tool_call_stream, text_stream])
    fake_client = _fake_client(create)
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    async def scenario():
        session = GuideSession(conversation_id="conv_abc")
        gen = streaming.stream_reply("what's my number", session)
        # First __anext__() returns promptly with the ToolCallStarted event
        # from round 1 (a pure tool call, no text) -- it doesn't touch the
        # gated second stream at all.
        first = await gen.__anext__()
        task = asyncio.ensure_future(gen.__anext__())
        await asyncio.sleep(0)  # let the task run the tool round-trip up to the gated second stream
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await gen.aclose()
        return first

    first = asyncio.run(scenario())
    assert isinstance(first, streaming.ToolCallStarted)
    assert tool_call_stream.closed
    assert text_stream.closed
