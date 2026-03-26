# Twilio Setup

## Inbound Routing Model

The recommended production path is:

1. Buy or connect the restaurant number in Twilio.
2. Import/connect that number into ElevenLabs native telephony.
3. Configure ElevenLabs to call this backend’s personalization endpoint at conversation start.

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

## Failure Fallback

If the primary Twilio voice handler fails, configure this backend endpoint as the fallback:

- `POST /api/twilio/voice-fallback`

Behavior:

- if the called number matches a restaurant with an `escalation_phone`, Twilio plays a short Italian apology and dials the restaurant
- otherwise Twilio plays a short Italian apology and hangs up cleanly

This does not replace the main ElevenLabs telephony routing. It only prevents callers from hearing the default English Twilio application error when the upstream voice handler is broken.
