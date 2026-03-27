# ElevenLabs Configuration

## Agent Profile

- Voice model: `eleven_v3_conversational`
- LLM model is now owner-configurable in the dashboard settings and stored per restaurant
- Current app presets use OpenAI GPT-5 family names, with custom model ids also allowed
- Style: concise, warm, professional

## Telephony Integration Reality

The live telephony architecture is now:

1. Twilio inbound call hits backend `POST /api/twilio/inbound`
2. backend resolves restaurant + personalization
3. backend calls ElevenLabs `register_call`
4. backend returns ElevenLabs-generated TwiML to Twilio
5. ElevenLabs runtime then uses:
   - personalization webhook
   - server tools
   - post-call webhook

Important:

- do not rely on the older manual Twilio target `https://api.elevenlabs.io/v1/convai/twilio/inbound_call`
- that path returned `404` during live debugging
- the backend-owned inbound route is now the supported path

## Dynamic Variables

Use dynamic variables in:

- system prompt
- first message
- tool parameters

Important runtime variables returned by this repo’s personalization endpoint:

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

Configure five server tools that point to the backend:

- `POST /api/tools/check-availability`
- `POST /api/tools/create-booking`
- `POST /api/tools/find-booking`
- `POST /api/tools/modify-booking`
- `POST /api/tools/cancel-booking`

Authentication:

- add a custom header with the same name as `TOOL_SECRET_HEADER_NAME`
- default header name in code: `X-Ristorante-Tool-Secret`
- value: `ELEVENLABS_TOOL_SECRET`

## Post-Call Webhook

Send completed conversation data to:

- `POST /api/webhooks/elevenlabs/post-call`

If `ELEVENLABS_WEBHOOK_SECRET` is configured, the backend validates the `ElevenLabs-Signature` header before accepting the payload.

## API Key Requirement

`ELEVENLABS_API_KEY` is required for:

- `register_call` in the Twilio inbound route
- transcript retrieval from the ElevenLabs Conversations API
- agent sync checks against the linked agent

If the key is missing, Twilio inbound registration falls back to the Italian emergency route instead of starting the real AI conversation.

## Notes

- If `ELEVENLABS_API_KEY` is configured, the calls page now tries to pull the full transcript from the ElevenLabs Conversations API and falls back to the locally stored preview when the remote fetch fails.
- The settings page now performs a safe sync pass against the linked agent: it verifies reachability, aligns the agent display name to the restaurant name, and merges repository-owned tags. Prompt content, first message, and tool wiring still live in ElevenLabs because those artifacts are not stored in this app.
- Owner-facing AI settings are persisted in `restaurant.assistant_settings` and exposed to runtime personalization, so model choice and greeting no longer live only in docs or code constants.
