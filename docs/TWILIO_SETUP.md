# Twilio Setup

## Inbound Routing Model

The current supported live path is:

1. Buy or connect the restaurant number in Twilio.
2. In Twilio, send inbound voice traffic to this backend:
   - `POST /api/twilio/inbound`
3. The backend registers the call with ElevenLabs and returns TwiML back to Twilio.
4. ElevenLabs then continues with personalization, tools, and post-call webhooks.

This backend-owned inbound route is now the supported path because the older manual Twilio target:

- `https://api.elevenlabs.io/v1/convai/twilio/inbound_call`

returned `404` during live debugging.

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

## Personalization Endpoint

This repo exposes:

- `POST /api/integrations/elevenlabs/twilio-personalization`

Expected body:

```json
{
  "caller_id": "+393331234567",
  "agent_id": "agent_abc123",
  "called_number": "+390212345678",
  "call_sid": "CA123"
}
```

Authentication:

- Header: `X-Ristorante-Tool-Secret`
- Value: `ELEVENLABS_PERSONALIZATION_SECRET`

Response:

- returns `conversation_initiation_client_data`
- injects restaurant and caller context as dynamic variables
- overrides the first message with a time-aware Italian greeting

## Operational Advice

- map `called_number` to the restaurant when possible
- keep `elevenlabs_agent_id` on the restaurant row for an additional routing key
- prefer E.164 numbers everywhere
- do not manually restore the old ElevenLabs `convai/twilio/inbound_call` URL in Twilio once the backend inbound route is working

## Failure Fallback

If the primary Twilio voice handler fails, configure this backend endpoint as the fallback:

- `POST /api/twilio/voice-fallback`

Behavior:

- if the called number matches a restaurant with an `escalation_phone`, Twilio plays a short Italian apology and dials the restaurant
- otherwise Twilio plays a short Italian apology and hangs up cleanly

This does not replace the main ElevenLabs telephony routing. It only prevents callers from hearing the default English Twilio application error when the upstream voice handler is broken.

## Quick Verification

Twilio-style manual check:

```bash
curl -i -X POST https://<backend-domain>/api/twilio/inbound \
  --data 'From=%2B41779802809&To=%2B41225394205&CallSid=CA_manual_check'
```

Healthy result:

- HTTP `200`
- XML response
- main success path returns ElevenLabs `<Connect><Stream .../></Connect>` TwiML
- failure path returns the Italian fallback speech/transfer TwiML
