# Integrations

This file is the single source of truth for Twilio, ElevenLabs, and backend tool wiring.

## Telephony Architecture

The supported voice path is:

1. Twilio receives the call
2. Twilio sends the inbound webhook to backend `POST /api/twilio/inbound`
3. backend resolves the restaurant by `twilio_phone` and builds runtime personalization
4. backend calls ElevenLabs `register_call`
5. backend returns ElevenLabs-generated TwiML to Twilio
6. Twilio connects the call to ElevenLabs
7. ElevenLabs calls:
   - personalization webhook (once, at call start)
   - server tools (during conversation)
   - post-call webhook (after call ends)

Emergency fallback:

- `POST /api/twilio/voice-fallback`

This is only for failure handling. It is not the main AI conversation path.

## Important Rule

Do not point Twilio at:

- `https://api.elevenlabs.io/v1/convai/twilio/inbound_call`

That older manual target returned `404` during live debugging and caused the English "application error" failure heard by callers.

## Twilio Console Values

### A call comes in

- `Webhook`
- `https://ristorante-ai-api-jc7mvuujwq-ew.a.run.app/api/twilio/inbound`
- `HTTP POST`

### Primary handler fails

- `Webhook`
- `https://ristorante-ai-api-jc7mvuujwq-ew.a.run.app/api/twilio/voice-fallback`
- `HTTP POST`

### Call status changes

- `https://api.us.elevenlabs.io/twilio/status-callback`
- `HTTP POST`

## Personalization Webhook

Route:

- `POST /api/integrations/elevenlabs/twilio-personalization`

Auth:

- header: `X-Ristorante-Tool-Secret`
- accepts either `ELEVENLABS_TOOL_SECRET` or `ELEVENLABS_PERSONALIZATION_SECRET`

Expected body:

```json
{
  "caller_id": "+393331234567",
  "agent_id": "agent_abc123",
  "called_number": "+390212345678",
  "call_sid": "CA123"
}
```

Returns `conversation_initiation_client_data` with all dynamic variables.

## Current Dynamic Variables

All variables sent to ElevenLabs at call start. Use `{{variable_name}}` syntax in prompts and first message.

| Variable | Source | Example |
|----------|--------|---------|
| `restaurant_id` | DB | `a1f59bc4-b750-4f2c-bcb1-0a703ac732c7` |
| `restaurant_name` | DB | `Trattoria Madonnina` |
| `address` | DB | `Via Roma 12, Milano` |
| `timezone` | DB | `Europe/Rome` |
| `opening_hours` | DB | `lunch: 12:00-15:00, dinner: 19:00-23:00` |
| `weekly_closures` | DB | `monday` |
| `closure_dates` | DB | `2026-04-01, 2026-04-25` |
| `turni_description` | DB (computed) | `Primo: 19:00-21:00 (40p), Secondo: 21:00-23:00 (40p)` |
| `large_group_threshold` | DB | `10` |
| `caller_phone` | Twilio | `+41779802809` |
| `called_number` | Twilio | `+41225394205` |
| `call_sid` | Twilio | `CA123abc` |
| `current_date` | Server clock | `2026-03-28` |
| `current_time` | Server clock | `15:30` |
| `current_day_of_week` | Server clock | `Saturday` |
| `agent_style_notes` | DB | `Warm, concise, premium Italian hospitality tone.` |
| `greeting` | DB + server clock | `Buonasera, Trattoria Madonnina. Come posso aiutarla?` |

**Important:** `greeting` is resolved by the backend from `custom_greeting` with `{saluto}` replaced by `Buongiorno` (before 14:00) or `Buonasera` (after 14:00) in the restaurant's local timezone.

The ElevenLabs **First Message** field should be set to:
```
{{greeting}}
```

## Server Tools

All tool endpoints live in:

- `backend/app/api/tools.py`

Auth:

- header: `X-Ristorante-Tool-Secret`
- value: `ELEVENLABS_TOOL_SECRET` (from GCP Secret Manager)

Test auth:

```bash
curl -i https://ristorante-ai-api-jc7mvuujwq-ew.a.run.app/api/tools/health \
  -H "X-Ristorante-Tool-Secret: <secret>"
```

### `check_availability`

- `POST /api/tools/check-availability`
- `restaurant_id`: **dynamic_variable** (not llm_prompt)

```json
{
  "restaurant_id": "{{restaurant_id}}",
  "date": "2026-03-29",
  "time_preference": "20:30:00",
  "party_size": 5
}
```

Returns: `{open, available, reason, alternatives: [{time, turno, remaining}]}`

### `create_booking`

- `POST /api/tools/create-booking`
- `restaurant_id`: **dynamic_variable**
- `caller_phone`: **dynamic_variable** pointing to `caller_phone`
- agent should NEVER ask for the phone number — it comes from the dynamic variable

```json
{
  "restaurant_id": "{{restaurant_id}}",
  "date": "2026-03-29",
  "time": "20:30:00",
  "party_size": 5,
  "customer_name": "Rossi",
  "customer_phone": "{{caller_phone}}",
  "caller_phone": "{{caller_phone}}",
  "special_requests": null
}
```

### `find_booking`

- `POST /api/tools/find-booking`
- `restaurant_id`: **dynamic_variable**
- `caller_phone`: **dynamic_variable**

```json
{
  "restaurant_id": "{{restaurant_id}}",
  "caller_phone": "{{caller_phone}}"
}
```

or by confirmation code:

```json
{
  "restaurant_id": "{{restaurant_id}}",
  "confirmation_code": "TM-042901"
}
```

### `modify_booking`

- `POST /api/tools/modify-booking`
- `restaurant_id`: **dynamic_variable** (top-level, NOT inside `changes`)

```json
{
  "confirmation_code": "TM-042901",
  "restaurant_id": "{{restaurant_id}}",
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
- expects `ElevenLabs-Signature` header
- **currently DISABLED** — ElevenLabs auto-disabled it after repeated 401 errors
- see `docs/OPERATIONS.md` for re-enable steps

What it does:

- creates or updates a `CallLog` record
- determines `outcome` (booking_created/modified/cancelled/info_provided/escalated/abandoned/tool_error)
- sets `call_status` (successful/failed/unknown) from payload — requires migration 0006
- links call log to booking if one was created during the call window
- invalidates analytics cache

## ElevenLabs Agent Configuration

### Voice Settings (recommended)

| Setting | Value | Reason |
|---------|-------|--------|
| Model | `Eleven v3 Conversational` | Low-latency, expressive, real-time optimized |
| Stability | 0.5–0.6 | Balanced warmth |
| Similarity Boost | 0.5–0.65 | Lower = less source noise |
| Style Exaggeration | **0** | Reduces latency and artifacts |
| Speed | 1.0 | Natural conversation pace |

**Audio noise fix:** Lower similarity boost to 0.5. If using a cloned voice, re-clone from cleaner audio processed through [ElevenLabs Voice Isolator](https://elevenlabs.io/voice-isolator).

### ASR Settings

- Model: `Scribe Realtime v2.1`
- Input format: `μ-law 8000 Hz` (Telephony) — required for Twilio

### Agent Identity

- Agent name: **Edoardo** (the AI responds to this name only if asked)
- Agent should NEVER introduce itself by name proactively
- If asked "sei un'AI?": "Sì, sono un'assistente digitale. Posso aiutarla."

## ElevenLabs API Key

`ELEVENLABS_API_KEY` is required for:

- Twilio inbound `register_call`
- transcript retrieval from the Conversations API
- agent sync checks

If the key is missing, inbound calls can still hit the backend, but the route falls back instead of starting the real AI conversation.

## ElevenLabs Quotas

ElevenLabs plans have per-billing-period call minute quotas. When exceeded:

- calls fail with "This request exceeds your quota limit"
- this shows as `Call status: Error` in the ElevenLabs dashboard

Fix: check usage at elevenlabs.io → Settings → Subscription. Upgrade or wait for cycle reset.

## Agent Prompt

The current system prompt is documented in:

- `docs/SYSTEM_PROMPT.md`
