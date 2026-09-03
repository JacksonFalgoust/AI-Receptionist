# Local Audio Demo

A second phone demo that keeps Twilio only as the phone line. Instead of Twilio Conversation Relay handling speech-to-text and text-to-speech, this demo uses GuideAnts' own audio models: caller speech is captured with Twilio's `<Record>` TwiML, transcribed locally via GuideAnts' `/v1/audio/transcriptions` endpoint, sent to the guide for a reply, and the reply is synthesized back to the caller via GuideAnts' `/v1/audio/speech` endpoint.

## What this is

```
Caller ⇄ Twilio number ⇄ <Record>/<Play> TwiML ⇄ this app ⇄ GuideAnts
                                                             ├─ /v1/audio/transcriptions  (STT)
                                                             ├─ /v1/responses             (guide, unchanged)
                                                             └─ /v1/audio/speech          (TTS)
```

**Versus `/twiml` + `/ws` (Conversation Relay):**

*Differences:*
- **No barge-in**: the caller cannot interrupt the guide's reply mid-sentence.
- **Pause between turns**: there's a 2-3 second silence between the caller finishing and the reply starting, while the app fetches the recording, transcribes it, gets the guide's answer, and synthesizes it back to audio.

*Gains:*
- **No third-party speech models** (once GuideAnts' own models below are local): transcription and synthesis run on GuideAnts' own models instead of Deepgram/ElevenLabs/Twilio Conversation Relay. Note this is not full end-to-end privacy: `<Record>` means Twilio itself still durably records and stores every caller turn server-side, and this app downloads that recording back over the public internet to transcribe it. Nothing in this demo deletes those Twilio-side recordings afterward — treat this as fewer third-party speech vendors in the loop, not a private call.

## GuideAnts configuration (do this first)

By default, GuideAnts routes transcription to OpenRouter, so this demo is not truly local until you install and select local audio models in GuideAnts.

**In the GuideAnts UI:**

1. Under **Model Settings**, install a local transcription model and a local speech model (with its voice pack).
2. In the guide's **Active Providers**, set both the transcription and speech models to the ones you just installed.

**Verify the setup** with these two commands (the exact probes used while designing this feature):

```bash
# Confirm the published API advertises the audio models
curl -s -H "Authorization: Bearer $GUIDEANTS_API_KEY" \
  "$GUIDEANTS_BASE_URL/api/published/openai/$GUIDEANTS_PUB_ID/v1/models"

# Confirm speech synthesis works and returns WAV
curl -s -X POST "$GUIDEANTS_BASE_URL/api/published/openai/$GUIDEANTS_PUB_ID/v1/audio/speech" \
  -H "Authorization: Bearer $GUIDEANTS_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"speech","input":"Testing one two three.","responseFormat":"wav"}' \
  -o /tmp/probe.wav && file /tmp/probe.wav

# Confirm transcription works -- and note the .wav filename is required
curl -s -X POST "$GUIDEANTS_BASE_URL/api/published/openai/$GUIDEANTS_PUB_ID/v1/audio/transcriptions" \
  -H "Authorization: Bearer $GUIDEANTS_API_KEY" \
  -F "model=transcription" -F "file=@/tmp/probe.wav;type=audio/wav"
```

**If transcription fails**, look for this error response:

```json
{"error":{"message":"OpenRouter transcription does not support audio format ...","code":"provider_not_ready"}}
```

This means transcription is still pointed at OpenRouter (or the upload's filename had the wrong extension). Go back to GuideAnts' Model Settings and ensure the transcription model is selected as the active provider, not OpenRouter.

**If a greeting or reply comes back silent** (no `<Play>`, or a generic error/timeout phrase, and GuideAnts' own container logs show `tts_synthesize_failed`/`asr_transcribe_rejected` right next to an unprompted `tts_model_unload_start`/`asr_model_unload_start`): GuideAnts periodically reconciles its local ASR/TTS engines and doesn't wait out an in-flight request first, so a request whose timing overlaps that cycle can have its connection dropped. `local_audio_client.py` retries once after `GUIDEANTS_RETRY_DELAY_SECONDS` for exactly this — raise it if the reconcile cycle on your setup takes longer than the default 1s to settle.

## Running it

Use the same server as the Conversation Relay demo:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
ngrok http 8080
```

Then point your Twilio number's voice webhook to `/local/twiml` instead of `/twiml`:

```
Twilio Console → Phone Numbers → your number → A call comes in:
  https://<ngrok-host>/local/twiml   (POST)
```

**Both demos are served by the same app.** Switching between them is just changing the webhook URL — no need to restart the server.

## Tuning

These are the knobs you'll actually touch when running the demo:

| Env var | Default | What it does |
|---------|---------|--------------|
| `LOCAL_RECORD_SILENCE_SECONDS` | 3 | Seconds of caller silence that end a turn. Raise it if callers get cut off mid-sentence; lower it if turns feel sluggish. |
| `LOCAL_TURN_BUDGET_SECONDS` | 10 | Deadline for the whole turn pipeline (fetch recording + STT + guide + TTS). Must stay under Twilio's ~15s webhook timeout. Reservation/tool-using turns (`checkAvailability`, `createOrder`, `sendPaymentLink` chained together) may need this raised above the default, since each Booqable round-trip adds real latency inside the same budget. |
| `GUIDEANTS_SPEECH_VOICE` | (empty) | Voice name for speech synthesis. Valid values depend on whichever local voice pack is installed and selected in GuideAnts — there's no fixed list here, and OpenAI voice names like "alloy" or "echo" don't apply. Leave empty for GuideAnts' configured default. |
| `GUIDEANTS_RETRY_DELAY_SECONDS` | 1 | Delay before the one retry on a transient GuideAnts audio failure — see "If a greeting or reply comes back silent" above. |

Other configuration (recording timeouts, session/audio cache TTLs, error messages) is in `app/config.py` with defaults that work for most cases — only change them if you hit them in practice.

## Limitations

- **No barge-in**: the caller must wait for the full reply to finish playing before they can interrupt.
- **Silence while thinking**: there's a 2-3 second pause between the caller finishing and the reply starting, while the app handles recording, transcription, guide, and synthesis.
- **Single-use unguessable audio IDs**: `/local/audio/{id}` returns synthesized replies as WAV audio. The `{id}` is a random unguessable single-use token, not a Twilio-signed request like the Conversation Relay flow — only the app and Twilio know the ID. Eviction of stale entries is request-driven (it happens on the next `/local/twiml` or `/local/turn` call, not on a background timer), so `LOCAL_AUDIO_TTL_SECONDS` (default 5 minutes) is a ceiling on how long a stale entry can live, not a guaranteed expiry moment.
