# System Prompt

Last updated: `2026-04-10`

This file describes the current OpenAI Realtime prompt strategy.

## Where The Live Prompt Comes From

The live phone-agent prompt is generated in:

- `backend/app/services/openai_realtime.py`

Priority order:

1. explicit temporary override from `/studio` simulation
2. saved restaurant override in `restaurants.openai_prompt_override`
3. generated default prompt from restaurant data

## Current Prompt Structure

The baseline prompt is organized into these sections:

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

Variation guidance is currently embedded inside `Personality & Tone` rather than split into a separate section.

Live-call review added explicit prompt rules for:

- preserving full caller names exactly, including multi-part names
- rejecting garbled transcripts such as isolated letters or words incompatible with the current question
- asking for only the missing detail when audio is unclear
- avoiding false-positive phrases such as "perfetto" after unclear audio
- treating transfer to the restaurant as a last resort unless the caller explicitly asks, the request is out of policy, or the bridge/tool path cannot safely complete the call

This structure is intentional and matches current OpenAI Realtime prompting recommendations for strong instruction following and lower voice-agent instability.

## What Is Dynamic

The generated prompt injects restaurant-specific values such as:

- restaurant name
- address
- timezone
- opening hours
- turni
- weekly closures
- extraordinary closures
- caller phone
- current date/time/day
- greeting
- large group threshold
- local style notes

## How To Tune It

Use the operator dashboard:

1. open `/studio`
2. inspect the current prompt
3. modify the prompt draft
4. simulate in text mode
5. optionally run the scenario suite for a quick regression pass
6. save to production config when satisfied

Do not edit the prompt only in source if the goal is operator-controlled tuning.

## Guardrails That Must Stay

Even if the prompt is customized, these safety rules are still enforced in code:

- write tools require explicit confirmation
- caller phone comes from server session state
- booking writes go through the backend booking engine
- escalation uses backend/Twilio transfer logic
- escalation is constrained by prompt and tool policy so normal booking clarification stays with the AI agent

The prompt guides behavior. The backend enforces the high-value invariants.
