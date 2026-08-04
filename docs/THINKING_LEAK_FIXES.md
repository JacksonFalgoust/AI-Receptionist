# Fixing assistant "thinking" leaking into the spoken reply

**Symptom:** during a tool call, the guide's reasoning/"thinking" is spoken aloud and
then gets cut off once the tool call finishes and the real final answer streams.

This document explains *why* it happens in this stack and lists every place it can be
fixed — at the model, in GuideAnts, or in this app — with the trade-offs of each.

> Investigation date: 2026-08-03. File/line citations are point-in-time; verify against
> current code before relying on them.

---

## TL;DR

- The published guide runs **`deepseek/deepseek-v4-flash:nitro`** — a reasoning model
  (Non-think / Think High / Think Max) via **OpenRouter**, with reasoning **on** by default.
- Thinking reaches the caller only when DeepSeek emits it **inline** as `<think>…</think>`
  inside `content`: GuideAnts' OpenRouter client forwards that text raw (no stripping), and
  GuideAnts flattens it into `response.output_text.delta` with no separate reasoning channel.
- A latency-sensitive **voice** app is a poor fit for a reasoning model in the first place.
- **Best fixes:** switch to a non-reasoning model (or DeepSeek's Non-think tier); or, entirely
  within this repo, strip `<think>` from deltas, or use the non-streaming responses path.

---

## Why it happens (the mechanism)

`GUIDEANTS_MODEL="guide"` is only an **alias**; the real model is chosen inside GuideAnts.
For this demo that model is `deepseek/deepseek-v4-flash:nitro`
(`guide-demo/Twillio demo agent/manifest.json` → `defaultModel`).

The leak path, end to end:

1. **DeepSeek is a reasoning model with thinking on.** DeepSeek V4 Flash supports three tiers
   (Non-think / Think High / Think Max); via OpenRouter, reasoning is enabled by default.
2. **GuideAnts' OpenRouter client forwards thinking as plain text.**
   `AntRunner.Chat.OpenRouter/OpenRouterChatClient.cs` streams back **only `delta.content`**,
   **ignores** the separate `delta.reasoning` field, and does **no `<think>` stripping**
   (unlike `LlamaCppChatClient`, which strips via its `ThoughtBlockPattern`). So if DeepSeek
   puts reasoning in the dedicated `reasoning` field, GuideAnts drops it; but if it emits
   `<think>…</think>` *inline in content*, that passes straight through as assistant text.
3. **GuideAnts flattens everything into the answer channel.** The stream engine emits every
   delta as `response.output_text.delta` with `role:"assistant"`
   (`Services/Conversations/Streaming/ConversationStreamEngine.cs:303-312`). There is **no
   separate reasoning SSE event and no visibility filter anywhere** in GuideAnts.
4. **This app speaks every delta.** `app/main.py`'s `respond_to()` sends each delta to Twilio
   as a spoken token. `app/guide_client.py` buffers each tool-call round and discards
   intermediate narration (`_stream_reply_with_tools`, commit `4e95865`), but the **final**
   round is flushed verbatim — so thinking that leads the final answer is spoken, and a
   following round's preemptible audio truncates it ("cut off").

**Streaming vs. non-streaming matters:** GuideAnts' *non-streaming* path reconstructs a clean
finalized message that **excludes** thinking
(`Endpoints/PublishedWire/WireConversationExecutor.cs:169-174`). The leak is **streaming-only**.

### Confirm which mechanism you're seeing

- Grep the running app logs for
  `Discarding intermediate-round narration ahead of another tool call:`
  (`app/guide_client.py`). If the discarded text reads like reasoning or contains `<think>`,
  the model is emitting thinking as content.
- Or call the published `/v1/responses` endpoint directly with `stream:true` and a
  tool-triggering prompt, and inspect the raw `output_text` deltas.

---

## A. Turn off the thinking at the source

**A1 — Disable reasoning on the OpenRouter/DeepSeek call.**
The reliable OpenRouter switch is `reasoning: { enabled: false }` (equivalently
`reasoning: { max_tokens: 1 }`), which makes DeepSeek behave as its **Non-think** tier — no
reasoning tokens, nothing to leak.
⚠️ In this stack, GuideAnts' OpenRouter client currently serializes only the OpenAI-style
**`reasoning_effort`** string (`OpenRouterChatClient.cs:186,641`), **not** the
`reasoning:{enabled:false}` object — and `reasoning_effort` alone does not fully disable
DeepSeek's thinking. So A1 in its clean form needs the GuideAnts change in **E2**, or use
A2 / C / D instead.

**A2 — Set the guide's reasoning effort to `none` in GuideAnts.**
The reasoning runtime profile exposes a `none` choice
(`Resources/bootstrap/runtime-profiles/openai_responses_reasoning.json`).
⚠️ Two caveats: (1) `none` actually suppresses reasoning **only for OpenAI Responses models**
(`o*` / `gpt-5*`, via `OpenAiReasoningSupport`) — OpenRouter models are marked
`reasoningEffortEnabled:false` in `knownCloudModels.json`; (2) the **per-guide** effort field
does not appear to be wired into the runtime request — the effective knob is the **global**
`ChatDefaults:ReasoningEffort` setting. So A2 is dependable only when combined with an OpenAI
Responses model (see C2), not for DeepSeek-via-OpenRouter as-is.

**A3 — Local models (if you switch to llama.cpp).**
GuideAnts *does* strip `<think>` blocks for the local client (`LlamaCppChatClient`
`ThoughtBlockPattern`), and Qwen3 supports a hard `enable_thinking=false`. Safer against
leakage than OpenRouter — but not the current setup.

---

## B. System-prompt instructions

The current prompt (`guide-demo/Twillio demo agent/instructions.md`) says nothing about
thinking out loud. Prompt changes help, with limits:

**B1 — Suppress *narration* (works).** Add something like:
*"Never narrate what you are about to do, never explain your steps or reasoning, and never say
things like 'let me check' — call the tool silently, then answer in one short spoken
sentence."* This reliably removes conversational preamble the model writes into `content`.

**B2 — Model soft-switches (unreliable for DeepSeek).** Qwen3 honors a `/no_think` token in the
prompt; **DeepSeek was not trained with `/no_think`**, and for DeepSeek V4 the API `reasoning`
parameter is authoritative. A prompt token will not dependably disable DeepSeek's thinking.

**B3 — Reality check.** For a genuine reasoning model, the thinking phase runs before and
largely independently of instruction-following, so prompt text cannot be relied on to suppress
reasoning *tokens*. Treat B as a mitigation for narration, not a fix for reasoning leakage.

---

## C. Change the model (this is fundamentally a model-choice problem)

A latency-sensitive **voice** app is a poor fit for a reasoning model: it adds seconds of
think-time before every answer *and* risks leaking that thinking. Options, best first:

**C1 — Switch to a non-reasoning chat model.** No thinking phase to leak, and faster on the
phone (e.g., a DeepSeek V3-family chat model, or any fast non-reasoning instruct model in the
OpenRouter catalog). The most robust "change the model" fix.

**C2 — If you want a reasoning model, pick one GuideAnts can mute.** An **OpenAI Responses**
model (`o4-mini`, `gpt-5-mini`) with effort `minimal`/`none` is handled cleanly: GuideAnts omits
the `reasoning` block and never requests a summary
(`OpenAiResponsesClient.cs:498-509`). Anthropic is also a first-class provider if you prefer
Claude with thinking off (note current Claude models use *adaptive* thinking and reject the old
`budget_tokens` param — disable via model choice/config, not that flag).

**C3 — Keep DeepSeek V4 Flash but use its Non-think tier** (same as A1, framed as model config).

**Bonus argument for A/C:** DeepSeek V4 *thinking mode* via OpenRouter has a known bug where
`reasoning_content` must be replayed on follow-up tool turns or the call **400s**. This app is
tool-heavy (8+ reservation tools) and GuideAnts drops the inbound reasoning field, so leaving
thinking **on** risks mid-call failures, not just spoken leakage. Disabling reasoning avoids it.

---

## D. Fix it in this app (most robust, entirely in this repo)

**D1 — Use the non-streaming responses path (`stream: false`).** GuideAnts' non-streaming path
reconstructs a clean finalized message that excludes thinking
(`WireConversationExecutor.cs:169-174`) — the leak is streaming-only. Since commit `4e95865`
already removed live token streaming, switching `_stream_turn` to `stream:false` would
eliminate leakage with little UX loss. The cleanest self-contained fix.

**D3 — Keep the buffer-and-discard.** `_stream_reply_with_tools` in `app/guide_client.py`
already discards thinking that appears in intermediate tool-call rounds.

**D4 — Trigger-phrase gating (`feature/trigger-phrase`, `_SentinelGate` in `app/guide_client.py`).**
The guide is instructed to open its actual final answer with a fixed marker phrase
(`config.FINAL_ANSWER_SENTINEL`, "declare victory" by default — see
`guide-demo/Twillio demo agent/instructions.md`'s "FINAL ANSWER MARKER" paragraph); this app
withholds every delta until that phrase has been seen in the stream, then forwards everything
after it live. Thinking — whether it's narration, a `<think>` block, or anything else the model
puts in `content` ahead of the real answer — never contains the marker, so it's dropped with
certainty rather than by a length heuristic (D3's buffer-and-discard only catches narration that
happens to precede a tool call; thinking ahead of a *final*, no-tool-call answer still slips
through D3 and gets spoken, per the TL;DR above). Unlike D1, this stays fully streaming — text
after the marker reaches Twilio as soon as it clears the gate, not after the whole reply
finishes. Same caveat as B1: this is a client-side filter on the marker's *position*, not a
suppression of reasoning tokens at the source — if the model's thinking is long enough to delay
when the marker itself appears, the caller still waits through it in silence (masked by the
filler-phrase mechanism, same as a slow tool call), it just never gets *spoken*. Doesn't require
a GuideAnts change or a model swap, unlike A/C; complements rather than replaces them.
See `docs/ARCHITECTURE.md`'s "Trigger-phrase gating" section and `docs/STREAMING_COMPARISON.md`
for a head-to-head comparison against D1-style full buffering (`main`) and the
length-threshold approach (`feature/live-token-streaming`).

---

## E. Fix it in GuideAnts (server-side, correct long-term)

**E1 — Route `assistant_thinking` to its own SSE event** instead of flattening it into
`Token` / `output_text.delta` at `ConversationStreamEngine.cs:303-312`. Then every client can
ignore reasoning cleanly, for all providers. The "proper" fix.
✅ **Implemented** (GuideAnts, branch `feature/thinking-leak-server-fixes`): new
`StreamingEventTypes.AssistantThinking` (`"assistant_thinking"`); the stream engine emits
reasoning deltas on it instead of the answer channel, and `StreamingEvents.EmitThinkingMessages`
(the post-run path for thinking that never streamed) no longer emits `assistant_message`. The
three published wire adapters and the non-streaming collector drop the event explicitly — so
`/v1/responses`, `/v1/chat/completions` and `/v1/messages` carry answer text only — and the
React client ignores it rather than appending it as tokens.

**E2 — Make the OpenRouter client honor a disable switch:** send `reasoning:{enabled:false}`
when effort is `none`, and/or read and separate the inbound `delta.reasoning` field (currently
ignored). Enables A1/A2 for OpenRouter models.
✅ **Implemented**, then a follow-up gap fixed: `OpenRouterChatClient.ResolveReasoning` and
`DatabaseStorage.ResolveReasoningEffortForModel` correctly special-case `"none"` for provider
`openrouter-chat` — but `ResolveModelReasoningEffortAsync` derived that provider by re-querying
the **Models catalog table by model id**, not from the already-resolved
`ResolvedExecutionPolicy.Provider`. A guide that references its model **directly**
(`ChatModelReferenceKind.Direct` — e.g. `deepseek/deepseek-v4-flash:nitro` set straight on the
assistant, never added through the Models catalog UI) has no catalog row, so the lookup returned
`Provider: null`, the `"none"` bypass never matched, and — same as any other requested effort for
an unregistered model — `ResolveReasoningEffortForModel` fell through to the declared-choices
gate, saw zero choices, and returned `null`. Net effect: **nothing** (`reasoning`/`reasoning_effort`)
was ever sent for that model regardless of the requested effort, so DeepSeek always ran its own
default (reasoning on) — reproducing exactly as "effort=none still reasons," while non-`none`
efforts looked like they "worked" only because the model's default happens to be reasoning-on
too. Fixed by threading the already-resolved `ExecutionPolicy.Provider` into
`ResolveModelReasoningEffortAsync` (new `knownProvider` param, preferred over the catalog row) —
`ThreadRun.cs` → `DatabaseStorage.cs`. The `"none"`-only special-casing for OpenRouter is
unchanged; effort *levels* (`low`/`medium`/`high`) still require a catalog-declared choice.

**E3 — Wire the per-guide `Assistant.ReasoningEffort` into the runtime request** (it is
persisted and validated but never projected into the outgoing call).

---

## Recommendation (prioritized)

1. **Fastest reliable fix, no code:** switch the guide to a **non-reasoning model** (C1) — or
   DeepSeek's Non-think tier if the OpenRouter disable param can be sent. Right call for a voice
   app regardless of leakage.
2. **If you must keep reasoning:** move to an **OpenAI Responses model with effort
   `none`/`minimal`** (C2 + A2) — the one path GuideAnts mutes cleanly today.
3. **Belt-and-suspenders in this repo, ship anyway:** either **switch to `stream:false` (D1)**
   (cheap, self-contained, immune to model/provider changes, but gives up live streaming
   entirely) or **trigger-phrase gating (D4, `feature/trigger-phrase`)** if streaming latency
   matters more than that tradeoff — see `docs/STREAMING_COMPARISON.md` for how the two (plus
   `feature/live-token-streaming`'s length-threshold approach) compare head-to-head.
4. Add the **anti-narration prompt line (B1)** as a low-cost complement — D4 already needs a
   prompt change (the marker instruction) anyway, so B1 costs nothing extra alongside it.
5. Longer term, land **E1** in GuideAnts so no client has to care again.

---

## Appendix: key evidence

**This repo (Twilio demo)**
- `guide-demo/Twillio demo agent/manifest.json` — `defaultModel: deepseek/deepseek-v4-flash:nitro`
- `app/guide_client.py` — `_stream_turn` (yields only `output_text.delta`),
  `_stream_reply_with_tools` (buffer rounds, discard intermediate narration; flush final round)
- `app/main.py` — `respond_to()` sends every delta to Twilio as a spoken token
- `app/config.py` — `GUIDEANTS_MODEL` default `"guide"` (alias only)
- Commit `4e95865` — "Doesn't return assistant thinking when only one tool call used
  (removes token streaming)"

**GuideAnts repo**
- `AntRunner.Chat/AntRunner.Chat.OpenRouter/OpenRouterChatClient.cs` — reads only `delta.content`,
  ignores `delta.reasoning`, no `<think>` stripping; serializes outbound `reasoning_effort` only
- `GuideAntsApi/Services/Conversations/Streaming/ConversationStreamEngine.cs:303-312` — flattens
  thinking to `Token` with `role:"assistant"`; no separate reasoning event
- `GuideAntsApi/Endpoints/PublishedWire/WireConversationExecutor.cs:169-174` — non-streaming path
  reconstructs a clean final message (no thinking)
- `AntRunner.Chat/AntRunner.Chat.OpenAI/OpenAiReasoningSupport.cs`,
  `OpenAiResponsesClient.cs:498-509` — effort `none` suppresses reasoning summary (Responses
  models only)
- `GuideAntsApi/Resources/bootstrap/runtime-profiles/openai_responses_reasoning.json` — reasoning
  choices none/low/medium/high/xhigh, default medium
- `src/client/src/pages/settings/data/knownCloudModels.json` — OpenRouter models
  `reasoningEffortEnabled:false`

## Appendix: external references

- OpenAI reasoning models guide — https://developers.openai.com/api/docs/guides/reasoning
- Does `reasoning.effort:minimal` suppress summaries —
  https://community.openai.com/t/does-setting-reasoning-effort-minimal-suppress-reasoning-summaries/1361105
- OpenRouter DeepSeek API (reasoning param) — https://openrouter.ai/deepseek/deepseek-v3.2/api
- Disabling reasoning on OpenRouter/DeepSeek —
  https://github.com/SillyTavern/SillyTavern/issues/4635
- DeepSeek V4 Flash reasoning_content / thinking tiers —
  https://github.com/anomalyco/opencode/issues/29618
- Multi-turn `reasoning_content` 400 via OpenRouter —
  https://github.com/orgs/community/discussions/193953
- llama.cpp `--reasoning-format none` / think-tag splitting (PR #11607) —
  https://app.semanticdiff.com/gh/ggml-org/llama.cpp/pull/11607/overview
- Qwen3 `enable_thinking=false` / `/no_think` —
  https://github.com/QwenLM/Qwen3/discussions/1300
- Claude extended / adaptive & interleaved thinking —
  https://docs.claude.com/en/docs/build-with-claude/extended-thinking
