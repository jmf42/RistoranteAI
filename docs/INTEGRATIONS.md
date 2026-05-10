# Integrations

Last updated: `2026-05-10`

This file is the single source of truth for the live voice stack:

- Twilio for PSTN phone numbers and media streams
- OpenAI Realtime for voice + orchestration
- backend server-side tools for booking actions
- public web reservations for guest booking creation and management
- Supabase Postgres as the source of truth

## Supported Voice Path

1. Twilio receives the inbound call.
2. Twilio sends `POST /api/twilio/inbound` to the backend.
3. The backend resolves the restaurant by `twilio_phone`.
4. The backend creates a signed media-stream token and returns TwiML with:
   - `<Connect><Stream .../></Connect>`
   - stream target: `WS /api/twilio/media-stream`
   - stream status callback: `POST /api/twilio/status`
   - auth token passed as a Twilio `<Parameter>` value, not a query string
5. The backend opens a server-side OpenAI Realtime WebSocket session.
6. Caller audio is streamed from Twilio to OpenAI.
7. Assistant audio is streamed from OpenAI back to Twilio.
8. Tool calls stay server-side and execute against the booking engine and database.
9. The backend persists transcript preview, tool events, outcome, and call status in `call_logs`.

Emergency fallback:

- `POST /api/twilio/voice-fallback`

This fallback is only for technical failure handling.

## Backend Routes In Use

### Telephony

- `POST /api/twilio/inbound`
- `POST /api/twilio/status`
- `POST /api/twilio/voice-fallback`
- `WS /api/twilio/media-stream`

### Booking Tools

- `POST /api/tools/check-availability`
- `POST /api/tools/create-booking`
- `POST /api/tools/find-booking`
- `POST /api/tools/modify-booking`
- `POST /api/tools/cancel-booking`
- `GET /api/tools/health`

### Operator Voice Studio

- `GET /api/studio/agent`
- `POST /api/studio/tool-test`
- `POST /api/studio/simulate`
- `POST /api/studio/simulate-suite`
- `PUT /api/studio/config`
- `DELETE /api/studio/config`

### Public Reservations

- `GET /api/public/restaurants/{slug}/reservation-config`
- `POST /api/public/restaurants/{slug}/availability`
- `POST /api/public/restaurants/{slug}/bookings`
- `GET /api/public/bookings/{manage_token}`
- `POST /api/public/bookings/{manage_token}/modify`
- `POST /api/public/bookings/{manage_token}/cancel`

The studio is the platform-operator console for testing prompt, session config, and tool behavior before or during rollout.

The current studio surface also exposes:

- live-readiness checks
- prompt diagnostics
- config diff versus app defaults
- scenario presets for common call flows
- a batch simulation suite for quick regression sweeps after prompt/config changes

## Runtime Secrets and Config

### Required backend runtime

- `OPENAI_API_KEY`
- `TOOL_SECRET`
- `PUBLIC_BASE_URL`
- `PUBLIC_WEB_BASE_URL`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`

### Optional backend tuning

- `OPENAI_REALTIME_MODEL` default `gpt-realtime-1.5`
- `OPENAI_REALTIME_VOICE` default `cedar`
- `OPENAI_REALTIME_BASE_URL` default `wss://api.openai.com/v1/realtime?model=gpt-realtime-1.5`
- `NOTIFICATION_FROM_EMAIL`, `SMTP_HOST`, `SMTP_USERNAME`, `SMTP_PASSWORD` for public reservation emails

`PUBLIC_BASE_URL` must be the public backend origin Twilio can reach. It is used to generate the media-stream and status callback URLs.

`PUBLIC_WEB_BASE_URL` must be the public dashboard origin used for guest reservation manage links.

Important:
- Twilio `<Stream url>` does not support query strings.
- stream authentication is therefore passed through Twilio custom parameters and validated in the websocket bootstrap.

## Tool Auth

All tool endpoints use:

- header: `X-Ristorante-Tool-Secret`
- value: `TOOL_SECRET`

Compatibility note:
- `backend/app/core/config.py` still accepts `ELEVENLABS_TOOL_SECRET` as an alias for `TOOL_SECRET` so an existing secret can be reused during cutover.

Health check:

```bash
curl -i http://127.0.0.1:8000/api/tools/health \
  -H "X-Ristorante-Tool-Secret: local-tool-secret"
```

## OpenAI Realtime Session Shape

The backend creates a GA Realtime session using server-side WebSocket orchestration and sends:

- `model = gpt-realtime-1.5` or saved per-restaurant override
- `audio.input.format = audio/pcmu` for Twilio G.711 mu-law
- `audio.output.format = audio/pcmu`
- `audio.input.transcription.model = gpt-4o-transcribe-latest`
- `audio.input.turn_detection` (`server_vad` or `semantic_vad`)
- optional `audio.input.noise_reduction`
- server-side function tools dispatched on `response.output_item.done`
- structured prompt sections
- tracing enabled by default
- `parallel_tool_calls = false`
- no unsupported Realtime `strict` flag in tool schemas

The studio can override and persist these values per restaurant.

Human transfer policy:

- the prompt treats transfer to the restaurant as a last resort
- transfer is appropriate when the caller asks, the request is out of policy, a large group/allergy needs staff handling, audio remains unclear after targeted retries, or the technical/tool path cannot safely complete
- normal missing booking details should be clarified by the AI agent, not transferred

## Twilio Console Values

For the active phone number:

### A call comes in

- webhook URL: `https://<backend-domain>/api/twilio/inbound`
- method: `HTTP POST`

### Primary handler fails

- webhook URL: `https://<backend-domain>/api/twilio/voice-fallback`
- method: `HTTP POST`

Do not point Twilio directly at any external AI vendor URL.

## Operator Workflow

If you want to tune the live agent without editing code:

1. Open the dashboard as an operator.
2. Go to `/studio`.
3. Preview the effective prompt and session payload.
4. Review readiness and prompt diagnostics before saving anything.
5. Run tool tests against the real backend.
6. Run text-mode simulations against Realtime.
7. Save the prompt/session config to the restaurant record.

Saved studio config becomes the live phone-agent config for that restaurant.
