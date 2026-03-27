# Telephony Flow

This file explains the current real call path for the project.

## Short Version

The supported voice path is now:

1. caller reaches the Twilio number
2. Twilio sends the inbound webhook to the backend
3. backend resolves the restaurant from the called number
4. backend builds `conversation_initiation_client_data`
5. backend calls ElevenLabs `register_call`
6. backend returns ElevenLabs-generated TwiML back to Twilio
7. Twilio connects the call to ElevenLabs
8. ElevenLabs uses:
   - personalization webhook
   - server tools
   - post-call webhook

## Main Endpoints

### Twilio inbound voice entrypoint

- `POST /api/twilio/inbound`

This is the main production-facing route for voice calls.

It is responsible for:

- parsing the Twilio form payload
- finding the restaurant by `called_number`
- building personalization data
- registering the call with ElevenLabs
- returning the TwiML that connects the call to ElevenLabs

### Twilio emergency fallback

- `POST /api/twilio/voice-fallback`

This is not the primary conversation route.

It exists so callers hear an Italian apology and can be transferred to a human instead of hearing Twilio’s generic English application error when the main path fails.

### Personalization webhook

- `POST /api/integrations/elevenlabs/twilio-personalization`

This route returns `conversation_initiation_client_data` for ElevenLabs and injects restaurant-specific runtime context.

### Tool endpoints

- `POST /api/tools/check-availability`
- `POST /api/tools/create-booking`
- `POST /api/tools/find-booking`
- `POST /api/tools/modify-booking`
- `POST /api/tools/cancel-booking`

These are the booking system boundary. The voice model must not invent availability or booking outcomes.

### Post-call webhook

- `POST /api/webhooks/elevenlabs/post-call`

This is where completed conversation data comes back into the backend after the live call ends.

## The Important Failure We Already Learned

An older manual Twilio target was used during debugging:

- `https://api.elevenlabs.io/v1/convai/twilio/inbound_call`

That path returned `404`.

Result:

- Twilio played a generic English “application error” message
- the call failed before reaching this backend

Current rule:

- do not point Twilio at that older URL
- point Twilio at this backend’s `/api/twilio/inbound`

## Current Twilio Console Values

Use:

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

## What Must Be Present For Real AI Calls To Work

Backend runtime must have:

- `ELEVENLABS_API_KEY`
- `ELEVENLABS_TOOL_SECRET`
- `ELEVENLABS_PERSONALIZATION_SECRET`
- `ELEVENLABS_WEBHOOK_SECRET`

Restaurant data must have:

- `twilio_phone`
- `elevenlabs_agent_id`
- hours / turni / booking rules
- any configured greeting / AI style settings

If these are missing or mismatched, the inbound route may still respond, but the call may fall back instead of starting the AI conversation.

## Quick Health Check

Manual Twilio-style test:

```bash
curl -i -X POST https://<backend-domain>/api/twilio/inbound \
  --data 'From=%2B41779802809&To=%2B41225394205&CallSid=CA_smoke'
```

Healthy result:

- HTTP `200`
- XML response
- contains ElevenLabs `<Connect><Stream .../></Connect>` TwiML

Fallback result:

- HTTP `200`
- XML response
- contains the Italian apology / transfer flow

## Practical Lesson

The backend now owns the risky telephony handoff.

That is good because:

- routing is visible in code
- restaurant lookup is under app control
- personalization is under app control
- the system is less dependent on opaque Twilio console state

This is the preferred architecture for future work.
