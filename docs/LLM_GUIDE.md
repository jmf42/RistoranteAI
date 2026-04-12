# LLM Guide

Last updated: `2026-04-12`

This document explains how the voice agent is now built.

## Current Agent Architecture

- voice model: OpenAI Realtime
- phone transport: Twilio Media Streams
- orchestration: backend-owned websocket bridge
- tools: backend-owned function tools
- prompt/config storage: database-backed per restaurant
- operator tuning surface: dashboard `/studio`

## Why This Replaced ElevenLabs

The old issues were:

- tool instability
- vendor-console drift from app state
- transcript and call-state dependence on a third-party console
- harder debugging of live behavior

The new design keeps the important parts inside the app:

- prompt generation
- model choice
- tool schema
- confirmation guardrails
- call outcome persistence
- transcript preview

## Prompting Rules

The live prompt is generated in `backend/app/services/openai_realtime.py` unless a restaurant-specific override has been saved.

The baseline prompt is intentionally structured for Realtime:

- `Role & Objective`
- `Personality & Tone`
- `Language`
- `Context`
- `CRITICAL RULES`
- `Tools`
- `Conversation Flow`
- `Write Action Rules`
- `Duplicate Prevention`
- `Safety & Escalation`
- `Unclear Audio`

The anti-repetition guidance is part of `Personality & Tone`, not a separate `Variety` section.

The baseline prompt also encodes lessons from live-call review:

- preserve full customer names exactly instead of shortening them
- treat nonsense or garbled fragments such as isolated letters as invalid booking data
- ask only for the missing detail when audio is unclear
- use human transfer as a last resort, not as a shortcut for normal clarification

This follows current OpenAI Realtime prompting guidance:

- short labeled sections
- explicit language rules
- explicit tool-use rules
- short latency-masking preambles
- explicit recovery behavior
- narrow escalation criteria

Current language policy in the baseline prompt:

- the first greeting starts in Italian
- if the caller clearly speaks another language the agent can handle, it mirrors that language
- only the language changes; the booking flow, tool rules, safety rules, and confirmation rules stay the same

## Tool Policy

Tools are defined server-side and exposed to the model at session level.

Read tools:

- `check_availability`
- `find_booking`

Write tools:

- `create_booking`
- `modify_booking`
- `cancel_booking`

Escalation:

- `escalate_to_human`

Important:

- write tools are blocked server-side unless the last assistant turn was a confirmation request and the user then explicitly confirmed
- the model should call escalation only when needed: caller request, large groups, allergies/out-of-policy requests, repeated unclear audio, repeated tool failure, or unresolved long calls
- the caller phone is injected by the backend, not trusted from model arguments
- booking writes still use the existing booking engine and database logic

## Live Config Surface

The operator can change live agent behavior without code deploys from `/studio`.

Persisted per restaurant:

- prompt override
- model
- voice
- tool choice mode
- max response tokens
- VAD tuning
- transcription settings
- tracing
- truncation settings

These settings are stored in `restaurants.openai_prompt_override` and `restaurants.openai_realtime_settings`.

The studio now also shows:

- live-readiness checks for env and restaurant wiring
- prompt diagnostics based on current Realtime prompting recommendations
- config diff versus system defaults
- scenario presets for fast regression testing
- a multi-scenario simulation suite for quick prompt/config checks

## Debugging Strategy

When the phone agent behaves badly, check in this order:

1. `/studio` saved config
2. backend logs
3. `call_logs.extra_data.tool_events`
4. `call_logs.transcript_preview`
5. OpenAI traces for the session

The app should be debugged from the backend and database first, not from any external agent console.
