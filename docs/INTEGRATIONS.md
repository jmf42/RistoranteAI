# Integrations

This file is the single source of truth for Twilio, ElevenLabs, and backend tool wiring.

## Telephony Architecture

The supported voice path is:

1. Twilio receives the call
2. Twilio sends the inbound webhook to backend `POST /api/twilio/inbound`
3. backend resolves the restaurant and builds runtime personalization
4. backend calls ElevenLabs `register_call`
5. backend returns ElevenLabs-generated TwiML to Twilio
6. Twilio connects the call to ElevenLabs
7. ElevenLabs uses:
   - personalization webhook
   - server tools
   - post-call webhook

Emergency fallback:

- `POST /api/twilio/voice-fallback`

This is only for failure handling. It is not the main AI conversation path.

## Important Rule

Do not point Twilio at:

- `https://api.elevenlabs.io/v1/convai/twilio/inbound_call`

That older manual target returned `404` during live debugging and caused the English “application error” failure heard by callers.

## Twilio Console Values

### A call comes in

- `Webhook`
- `https://<backend-domain>/api/twilio/inbound`
- `HTTP POST`

### Primary handler fails

- `Webhook`
- `https://<backend-domain>/api/twilio/voice-fallback`
- `HTTP POST`

### Call status changes

- `https://api.us.elevenlabs.io/twilio/status-callback`
- `HTTP POST`

## Personalization Webhook

Route:

- `POST /api/integrations/elevenlabs/twilio-personalization`

Auth:

- header: `X-Ristorante-Tool-Secret`
- value: `ELEVENLABS_PERSONALIZATION_SECRET`

Expected body:

```json
{
  "caller_id": "+393331234567",
  "agent_id": "agent_abc123",
  "called_number": "+390212345678",
  "call_sid": "CA123"
}
```

Returns:

- `conversation_initiation_client_data`
- restaurant and caller context
- greeting and AI behavior variables

## Current Dynamic Variables

Important runtime variables include:

- `restaurant_id`
- `restaurant_name`
- `address`
- `opening_hours`
- `weekly_closures`
- `turni_description`
- `large_group_threshold`
- `caller_phone`
- `called_number`
- `call_sid`
- `timezone`
- `llm_provider`
- `openai_model`
- `reasoning_effort`
- `response_verbosity`
- `agent_style_notes`
- `greeting`

## Server Tools

All tool endpoints live in:

- `backend/app/api/tools.py`

Auth:

- header: `X-Ristorante-Tool-Secret`
- value: `ELEVENLABS_TOOL_SECRET`

Implemented tools:

### `check_availability`

- `POST /api/tools/check-availability`

```json
{
  "restaurant_id": "uuid",
  "date": "2026-03-29",
  "time_preference": "20:30:00",
  "party_size": 5
}
```

### `create_booking`

- `POST /api/tools/create-booking`

```json
{
  "restaurant_id": "uuid",
  "date": "2026-03-29",
  "time": "20:30:00",
  "party_size": 5,
  "customer_name": "Rossi",
  "customer_phone": "+393331234567",
  "caller_phone": "+393331234567",
  "special_requests": "Allergia glutine"
}
```

### `find_booking`

- `POST /api/tools/find-booking`

```json
{
  "restaurant_id": "uuid",
  "caller_phone": "+393331234567"
}
```

or:

```json
{
  "restaurant_id": "uuid",
  "confirmation_code": "TM-042901"
}
```

### `modify_booking`

- `POST /api/tools/modify-booking`

```json
{
  "confirmation_code": "TM-042901",
  "changes": {
    "date": "2026-03-30",
    "time": "21:00:00"
  }
}
```

### `cancel_booking`

- `POST /api/tools/cancel-booking`

```json
{
  "confirmation_code": "TM-042901"
}
```

## Post-Call Webhook

Route:

- `POST /api/webhooks/elevenlabs/post-call`

Security:

- validated with `ELEVENLABS_WEBHOOK_SECRET`
- expects `ElevenLabs-Signature`

## ElevenLabs API Key

`ELEVENLABS_API_KEY` is required for:

- Twilio inbound `register_call`
- transcript retrieval from the Conversations API
- agent sync checks

If the key is missing, inbound calls can still hit the backend, but the route will fall back instead of starting the real AI conversation.

## Agent Prompt

The baseline live prompt is documented in:

- `docs/SYSTEM_PROMPT.md`
