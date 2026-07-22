"""Twilio Conversation Relay <-> GuideAnts voice receptionist middleware.

POST /twiml   Twilio calls this when a call comes in; returns TwiML that opens
              a Conversation Relay WebSocket back to this server.
WS   /ws      Conversation Relay's WebSocket bridge: receives transcribed
              caller speech and streams the GuideAnts guide's reply back as
              speakable text tokens.

Conversation Relay is configured `interruptible="none"`, so Twilio itself
never pauses TTS playback on caller speech; it still arrives here as
"prompt" messages (`report_input_during_agent_speech="speech"`). Most
mid-reply speech (statements, backchannel, noise) is logged but not acted
on. The exception is a trigger utterance -- a stop/wait phrase or a new
question, per barge_in.should_interrupt() -- which cancels the in-flight
reply. A stop/wait phrase (barge_in.is_stop_command()) then just gets a
short local acknowledgment (config.STOP_ACK_PHRASES) and silence -- never
routed through GuideAnts, so it cuts over immediately with no extra
round-trip and doesn't depend on the guide choosing to reply briefly. A new
question instead starts a fresh reply for what the caller just said, same
as any other prompt. Playback is actually cut over using Conversation
Relay's per-frame `preemptible` flag (see respond_to()), not Twilio-native
interruption. Whether speech counts as "mid-reply" at all is tracked by
holding the reply task open until Twilio's agent-stopped speaker event
(`events="speaker-events"`, see speaker_events.py) reports playback
finished, falling back to a word-count estimate of the speaking time
(speech_timing.py) until the first such event is recognized on the call.
When a caller's utterance looks like a question or request
(see fillers.py) and GuideAnts' reply doesn't arrive within
config.FILLER_DELAY_SECONDS, a short filler phrase is spoken while still
waiting on the same in-flight call, to mask lookup latency.

Twilio finalizes a "prompt" at each pause in caller speech, so one spoken
turn can arrive as several prompt messages. Prompts that would start a new
turn are therefore buffered (schedule_turn()) and committed only after
config.TURN_PAUSE_SECONDS of continued caller silence, with the
clientSpeaking speaker events holding the buffer open while the caller is
still (or again) audibly speaking -- so a caller can take a brief breath
mid-sentence without the first half being answered and the second half
ignored. Stop/wait phrases are exempt: they still cut playback immediately.

Conversation memory lives server-side in GuideAnts, keyed by a conversation
id captured on the call's first turn (see guide_client.GuideSession) and
passed back as the `conversation` parameter on every later turn -- so only
the caller's latest utterance is ever sent, never a resent transcript.
`st.messages` below is therefore just a local log of what was actually said
for debugging; nothing about GuideAnts continuation depends on its
contents. When a barge-in cuts a reply short, the text the caller actually
heard is folded into the next turn's input (guide_client.build_input) so
the guide knows not to repeat itself -- see ARCHITECTURE.md's
"Interruption notes" section for how that works and its known rough edges.
"""

import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass, field

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from twilio.twiml.voice_response import Connect, VoiceResponse

import barge_in
import config
import fillers
import speaker_events
import speech_timing
from guide_client import GuideSession, build_input, stream_reply
from reservations_api import router as reservations_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice_receptionist")

app = FastAPI()
app.include_router(reservations_router)

# Ceiling on holding a buffered turn while the caller is (per clientSpeaking
# events) still audibly speaking. Normally the commit timer is re-armed by
# the coming clientSpeaking-stop event or continuation prompt long before
# this elapses; it only fires if a stop event is lost, so a stuck "on" can't
# hold the turn open forever.
PENDING_TURN_CEILING_SECONDS = 10.0


@app.post("/twiml")
async def twiml(request: Request) -> Response:
    """Return TwiML that connects the call to our Conversation Relay WebSocket."""
    host = request.headers.get("host", request.url.hostname)

    vr = VoiceResponse()
    connect = Connect()
    connect.conversation_relay(
        url=f"wss://{host}/ws",
        welcome_greeting=config.WELCOME_GREETING,
        tts_provider="ElevenLabs",
        transcription_provider="Deepgram",
        interruptible="none",
        # The welcome greeting has its own interruptibility setting, separate
        # from `interruptible` -- without this, Twilio cuts the greeting off
        # whenever it detects caller-side audio during it (including echo of
        # the greeting itself picked up on speakerphone) and sends an
        # `interrupt` message. Observed on real calls before this was set.
        welcome_greeting_interruptible="none",
        report_input_during_agent_speech="speech",
        events="speaker-events",
    )
    vr.append(connect)

    return Response(content=str(vr), media_type="application/xml")


@dataclass
class CallState:
    guide: GuideSession = field(default_factory=GuideSession)
    messages: list = field(default_factory=list)  # local log only, see module docstring
    task: object = None  # asyncio.Task | None
    partial_reply: str = ""  # real reply text streamed so far this turn (never the filler)
    # Text of a reply the caller was actually cut off mid-way through by a
    # barge-in, if any -- folded into the *next* start_reply()'s input via
    # build_input(), then cleared. None means the previous turn (if any)
    # completed normally (or was interrupted before any of it was heard).
    interrupted_reply: str | None = None
    # The fully-generated reply currently being spoken by Twilio during
    # respond_to()'s playback hold, and when that playback (approximately)
    # started. Used to *estimate* how much the caller heard when a barge-in
    # lands during the hold -- st.partial_reply is already cleared by then,
    # and with a model that returns the whole reply in one burst (see
    # ARCHITECTURE.md) the hold is where nearly every real barge-in lands.
    playback_text: str = ""
    playback_start: float = 0.0
    # Set by the WS loop when an agent-stopped speaker event arrives
    # (events="speaker-events"); awaited by respond_to()'s playback hold.
    playback_done: asyncio.Event = field(default_factory=asyncio.Event)
    # True once any agent-stop event has been recognized this call. Until
    # then the hold uses the word-count estimate alone, so an account/shape
    # that never emits recognizable events behaves exactly as before.
    agent_stop_seen: bool = False
    # Caller text transcribed but not yet committed as a turn, plus the timer
    # task that will commit it (see schedule_turn()). Twilio finalizes a
    # prompt at each brief pause, so one spoken turn can arrive as several
    # prompt messages; these hold the fragments together until the caller has
    # actually stopped talking.
    pending_text: str = ""
    pending_commit: object = None  # asyncio.Task | None
    # Whether the caller is currently speaking, per the clientSpeaking
    # speaker events. Stays False if those events never arrive (or aren't
    # recognized), so such a call degrades to the plain TURN_PAUSE_SECONDS
    # debounce instead of misbehaving.
    client_speaking: bool = False


@app.websocket("/ws")
async def conversation_relay_ws(websocket: WebSocket) -> None:
    await websocket.accept()

    st = CallState()

    async def respond_to(input_text: str, filler_eligible: bool) -> None:
        # Every frame is marked preemptible so that if this turn is still
        # playing when a later trigger-interrupted turn starts, Twilio drops
        # this audio and switches to the new turn's audio immediately. This
        # is a no-op in the normal (non-interrupting) case, since by the
        # time a new turn starts normally the previous one has already
        # finished.
        start_time = asyncio.get_event_loop().time()
        reply_text = ""
        filler = None
        gen = stream_reply(input_text, st.guide)
        # Only utterances that look like a question/request (see fillers.py)
        # are filler-eligible at all. Among those, race GuideAnts' reply
        # against the filler delay: if it's already back within
        # FILLER_DELAY_SECONDS, skip the filler; otherwise speak one and keep
        # waiting on the same in-flight call.
        first_chunk = asyncio.ensure_future(gen.__anext__())
        try:
            if filler_eligible:
                done, _ = await asyncio.wait({first_chunk}, timeout=config.FILLER_DELAY_SECONDS)
                if first_chunk not in done:
                    filler = fillers.pick(config.FILLER_PHRASES)
                    if filler:
                        await websocket.send_json(
                            {"type": "text", "token": filler + " ", "last": False, "preemptible": True}
                        )
            try:
                first_delta = await first_chunk
            except StopAsyncIteration:
                first_delta = None
            if first_delta is not None:
                await websocket.send_json(
                    {"type": "text", "token": first_delta, "last": False, "preemptible": True}
                )
                reply_text += first_delta
                st.partial_reply = reply_text
            async for delta in gen:
                await websocket.send_json(
                    {"type": "text", "token": delta, "last": False, "preemptible": True}
                )
                reply_text += delta
                st.partial_reply = reply_text
            await websocket.send_json({"type": "text", "token": "", "last": True, "preemptible": True})
        except asyncio.CancelledError:
            first_chunk.cancel()
            with contextlib.suppress(Exception):
                await first_chunk
            # Ensure the underlying SSE response (if any) is closed before
            # the interrupting turn's request goes out, rather than at GC
            # time -- avoids a stale socket overlapping the next request on
            # the shared connection pool.
            with contextlib.suppress(Exception):
                await gen.aclose()
            raise
        except Exception:
            logger.exception("Error while streaming guide reply")
            try:
                await websocket.send_json(
                    {
                        "type": "text",
                        "token": "Sorry, I'm having trouble right now.",
                        "last": True,
                        "preemptible": True,
                    }
                )
            except Exception:
                pass
            return
        # Log the real reply -- never the filler -- for debugging only; this
        # list is not sent to GuideAnts (continuation is by conversation id,
        # see module docstring).
        if reply_text:
            st.messages.append({"role": "assistant", "content": reply_text})
            # Cleared so a later barge-in cancellation (which lands during
            # the pacing sleep below, not during generation) doesn't re-append
            # this same content via the st.partial_reply check in the `prompt`
            # handler. The playback fields take over from here: they let that
            # same barge-in handler estimate how much of the reply the caller
            # actually heard before interrupting.
            st.partial_reply = ""
            st.playback_text = reply_text
            st.playback_start = asyncio.get_event_loop().time()
        # Turns 2+ stream token-by-token, but Twilio still buffers/plays TTS
        # far slower than the deltas arrive -- this task would otherwise be
        # marked "done" well before Twilio actually finishes speaking the
        # reply aloud, making mid-reply caller speech look like it arrived
        # after the reply ended and incorrectly starting a brand-new turn.
        # Hold the task open until Twilio's agent-stopped speaker event says
        # playback actually finished (events="speaker-events", see
        # speaker_events.py); until the first such event has been recognized
        # this call, fall back to the estimated remaining speaking time,
        # exactly as before.
        spoken_text = f"{filler} {reply_text}" if filler else reply_text
        estimated_duration = speech_timing.estimate_seconds(spoken_text, config.TTS_WORDS_PER_SECOND)
        if st.agent_stop_seen:
            # Cleared only now so stale sets (the welcome greeting ending, or
            # the filler finishing while GuideAnts was still thinking) can't
            # release the wait early: the stop event that matters here can't
            # fire yet, since the reply was sent milliseconds ago and takes
            # seconds to play.
            st.playback_done.clear()
            # The estimate degrades to a generous ceiling, measured from now
            # (playback of the just-sent reply is only starting), so a lost
            # event can't hold the turn open forever.
            ceiling = estimated_duration * 1.5 + 2.0
            try:
                await asyncio.wait_for(st.playback_done.wait(), timeout=ceiling)
            except asyncio.TimeoutError:
                logger.warning(
                    "No agent-stopped speaker event within %.1fs; releasing turn on the estimate",
                    ceiling,
                )
        else:
            remaining = estimated_duration - (asyncio.get_event_loop().time() - start_time)
            if remaining > 0:
                await asyncio.sleep(remaining)

    def start_reply(user_text: str) -> None:
        input_text = build_input(user_text, st.interrupted_reply)
        if st.interrupted_reply:
            logger.info("Folding interruption note into next turn: %r", input_text)
        st.interrupted_reply = None
        st.messages.append({"role": "user", "content": user_text})
        st.partial_reply = ""
        st.playback_text = ""
        st.task = asyncio.create_task(respond_to(input_text, fillers.looks_like_question(user_text)))

    def _arm_commit(delay: float) -> None:
        if st.pending_commit and not st.pending_commit.done():
            st.pending_commit.cancel()
        st.pending_commit = asyncio.create_task(_commit_pending_after(delay))

    async def _commit_pending_after(delay: float) -> None:
        await asyncio.sleep(delay)
        # No awaits from here on, so a commit that has passed the sleep can't
        # interleave with the WS loop: the text is taken and the reply started
        # atomically. (A re-armed timer that fires after this finds
        # pending_text empty and does nothing.)
        text, st.pending_text = st.pending_text, ""
        if not text:
            return
        if st.client_speaking:
            logger.warning(
                "Committing buffered turn while caller still speaking (%.0fs ceiling hit): %r",
                delay,
                text,
            )
        else:
            logger.info("Caller stayed quiet %.1fs; committing turn: %r", delay, text)
        start_reply(text)

    def schedule_turn(user_text: str) -> None:
        # Twilio finalizes a prompt at each pause in caller speech, so this
        # transcript may only be the first half of the caller's turn. Buffer
        # it and commit only after TURN_PAUSE_SECONDS of further silence; if
        # the caller is already speaking again by the time it lands (they
        # resumed before STT finished finalizing), hold the buffer instead --
        # the coming clientSpeaking-stop event re-arms the real window.
        st.pending_text = f"{st.pending_text} {user_text}".strip()
        _arm_commit(
            PENDING_TURN_CEILING_SECONDS if st.client_speaking else config.TURN_PAUSE_SECONDS
        )

    async def _cancel_and_await(task) -> None:
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def cancel_task() -> None:
        t, st.task = st.task, None
        await _cancel_and_await(t)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Received non-JSON WS frame: %r", raw)
                continue

            msg_type = msg.get("type")

            if msg_type == "setup":
                logger.info(
                    "Call setup: callSid=%s from=%s to=%s",
                    msg.get("callSid"),
                    msg.get("from"),
                    msg.get("to"),
                )

            elif msg_type == "prompt":
                text = msg.get("voicePrompt", "") or ""
                if text.strip():
                    if st.task and not st.task.done():
                        if barge_in.should_interrupt(text, config.EXTRA_STOP_PHRASES):
                            await cancel_task()
                            # Remember what the caller actually heard as
                            # st.interrupted_reply, so the *next* real question
                            # (whether this one, if it's a new question, or a
                            # later one after a stop command) can tell the
                            # guide about the cut-off. Two cases:
                            #
                            # Mid-generation: st.partial_reply holds the real
                            # reply text streamed so far (never the filler) --
                            # log it too, same as a normal completed turn.
                            if st.partial_reply:
                                st.messages.append({"role": "assistant", "content": st.partial_reply})
                                st.interrupted_reply = st.partial_reply
                                st.partial_reply = ""
                            # Mid-playback (the common case when the model
                            # returns the whole reply in one burst): the full
                            # reply was already logged and partial_reply
                            # cleared, but Twilio was still speaking it aloud.
                            # Estimate how far playback had gotten from the
                            # elapsed time at the configured speaking rate;
                            # no note if it hadn't plausibly started, or had
                            # already finished, being heard.
                            elif st.playback_text:
                                elapsed = asyncio.get_event_loop().time() - st.playback_start
                                heard = speech_timing.estimate_spoken_prefix(
                                    st.playback_text, elapsed, config.TTS_WORDS_PER_SECOND
                                )
                                if heard and heard != st.playback_text:
                                    st.interrupted_reply = heard
                                st.playback_text = ""
                            if barge_in.is_stop_command(text, config.EXTRA_STOP_PHRASES):
                                # Stop/wait means stop -- acknowledge locally
                                # and go silent rather than asking GuideAnts
                                # what to say next, which would both add a
                                # round-trip before playback cuts over and
                                # leave whether the turn actually ends up to
                                # the guide's own reply. Never sent through
                                # GuideAnts, so (like fillers) never recorded
                                # in st.messages either.
                                logger.info("Stop command heard during active reply -- cancelling and going silent: %r", text)
                                ack = fillers.pick(config.STOP_ACK_PHRASES)
                                if ack:
                                    await websocket.send_json(
                                        {"type": "text", "token": ack, "last": True, "preemptible": True}
                                    )
                            else:
                                logger.info("Interrupting active reply for a new question: %r", text)
                                schedule_turn(text)
                        else:
                            # Logged only, never sent to GuideAnts or added to
                            # st.messages -- this utterance wasn't a trigger,
                            # so it's treated as noise, not a real turn.
                            logger.info("Ignored caller speech during active reply (not acted on): %r", text)
                    elif st.pending_text:
                        # A turn is already buffered awaiting the pause
                        # window, so this is the caller continuing that same
                        # turn -- merge it, even if this fragment alone would
                        # look like a backchannel ("...yeah" mid-sentence).
                        schedule_turn(text)
                    elif fillers.is_backchannel(text, config.EXTRA_BACKCHANNEL_PHRASES):
                        # STT can finish transcribing a short "ok" after the
                        # reply has already finished playing, so this branch
                        # (not just the one above) also has to swallow pure
                        # acknowledgments -- otherwise a late "ok" looks like
                        # a brand-new prompt and gets its own guide reply.
                        # Never sent to GuideAnts or logged to st.messages,
                        # for the same reason as above.
                        logger.info("Ignored backchannel utterance (not acted on): %r", text)
                    else:
                        schedule_turn(text)

            elif msg_type == "interrupt":
                logger.info("Received interrupt message (unexpected with interruptible=none): %s", msg.get("utteranceUntilInterrupt"))

            elif msg_type == "dtmf":
                logger.info("DTMF digit: %s", msg.get("digit"))

            elif msg_type == "error":
                logger.error("Conversation Relay error: %s", msg.get("description"))

            # Only unhandled types reach the classifier, so a prompt whose
            # transcript happens to mention "agent speaking" can't match.
            elif (speaker_kind := speaker_events.classify(msg)) is not None:
                if speaker_kind == "agent-stop":
                    st.agent_stop_seen = True
                    st.playback_done.set()
                elif speaker_kind == "client-start":
                    st.client_speaking = True
                    # The caller resumed while a turn was buffered: hold the
                    # buffer for their continuation instead of committing a
                    # half-finished turn. The ceiling applies only while
                    # they're audibly speaking -- the coming stop event
                    # re-arms the real window below.
                    if st.pending_text:
                        _arm_commit(PENDING_TURN_CEILING_SECONDS)
                elif speaker_kind == "client-stop":
                    st.client_speaking = False
                    # The continuation's transcript trails this event by STT
                    # finalization time, so give it TURN_RESUME_GRACE_SECONDS
                    # (longer than the plain pause window) to arrive before
                    # committing what we have. A stop with nothing buffered
                    # is just the normal end of an utterance whose prompt
                    # hasn't arrived yet -- nothing to re-arm.
                    if st.pending_text:
                        _arm_commit(config.TURN_RESUME_GRACE_SECONDS)
                # Full payload logged on purpose: Twilio doesn't document
                # these messages' shape, so the log is how a mismatch with
                # speaker_events.classify gets noticed and fixed.
                logger.info("Speaker event %s: %s", speaker_kind, msg)

            else:
                logger.warning("Unhandled message type: %s (%s)", msg_type, msg)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    finally:
        # Pending-turn timer first: were it still alive, it could fire during
        # the await below and start_reply() a brand-new task that cancel_task()
        # already missed.
        timer, st.pending_commit = st.pending_commit, None
        await _cancel_and_await(timer)
        await cancel_task()
