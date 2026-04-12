# Realtime Telephony Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Harden the Twilio + OpenAI Realtime phone path against self-interruption, premature writes, cache busting, silent responses, and operator fallback gaps.

**Architecture:** Keep the existing backend-owned WebSocket bridge and database-backed operator studio. Tighten the Realtime session contract, move per-call volatile context out of the static system prompt, and add bridge-side safeguards for input gating, buffered audio forwarding, watchdog recovery, and human fallback.

**Tech Stack:** FastAPI, Twilio Media Streams, OpenAI Realtime WebSocket API, SQLAlchemy, pytest

---

### Task 1: Session payload hardening

**Files:**
- Modify: `backend/app/services/openai_realtime.py`
- Test: `backend/tests/test_openai_realtime.py`

**Step 1: Add failing regression coverage**

- Assert every tool schema includes `strict: true`.
- Assert the session payload includes `parallel_tool_calls: false`.
- Assert the static instructions no longer embed per-call date/time.

**Step 2: Implement the minimal session changes**

- Add strict function schemas.
- Disable parallel tool calls.
- Split tool scope into read-only vs full-write phases.

**Step 3: Re-run the targeted tests**

Run: `cd backend && uv run pytest tests/test_openai_realtime.py -q`

### Task 2: Prompt and runtime-context cleanup

**Files:**
- Modify: `backend/app/services/openai_realtime.py`
- Test: `backend/tests/test_openai_realtime.py`

**Step 1: Remove volatile prompt fields**

- Move caller/date/time/day context out of `build_realtime_instructions()`.

**Step 2: Add runtime system-message injection**

- Send a `conversation.item.create` system message after `session.update`.
- Include caller number and local date/time there.

**Step 3: Add speech-quality prompt rules**

- Add phonetic number/code readback guidance.
- Add explicit foreign-name/code-switching guidance.

### Task 3: Bridge safety and recovery

**Files:**
- Modify: `backend/app/services/openai_realtime.py`
- Test: `backend/tests/test_openai_realtime.py`

**Step 1: Add assistant-speaking input gating**

- Track when assistant audio is actively streaming.
- Skip `input_audio_buffer.append` while assistant audio is playing.

**Step 2: Buffer inbound Twilio audio**

- Accumulate a few packets before forwarding to OpenAI.
- Flush buffered audio on thresholds and stop.

**Step 3: Add silent-response watchdog**

- Detect responses that never start audio.
- Cancel and retry once before treating it as a bridge failure.

### Task 4: Human fallback wiring

**Files:**
- Modify: `backend/app/api/twilio.py`
- Test: `backend/tests/test_calls_and_restaurants.py`

**Step 1: Add a DTMF human-escape path**

- Offer `Press 1` in inbound TwiML before entering the stream.
- Handle `Digits=1` in the fallback route without claiming a technical error.

**Step 2: Preserve current technical fallback behavior**

- Keep the existing technical-failure transfer/hangup flow.

### Task 5: Long-call context management

**Files:**
- Modify: `backend/app/services/openai_realtime.py`
- Test: `backend/tests/test_openai_realtime.py`

**Step 1: Track conversation turns locally**

- Record user and assistant text turns with item IDs where available.

**Step 2: Add summarization hook**

- Summarize older turns every N turns with `gpt-4o-mini`.
- Store the summary for reuse and inject it as a system message.

**Step 3: Keep the implementation bounded**

- If full server-side pruning is unsafe in this pass, keep the summary storage and reinjection path correct and explicitly document any remaining pruning gap.

### Task 6: Verification and repo notes

**Files:**
- Modify: `docs/OPERATIONS.md` (if needed for AEC / proxy notes)
- Modify: `docs/OPENAI_REALTIME_READINESS.md` (if needed for new safeguards)

**Step 1: Add concise operator notes**

- Document `noise_reduction_type=off` for upstream AEC.
- Document the websocket proxy constraint.

**Step 2: Run baseline verification**

Run:
- `cd backend && uv run ruff check app tests`
- `cd backend && uv run pytest`

