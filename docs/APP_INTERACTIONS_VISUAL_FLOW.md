# App Interactions Visual Flow

This page is the visual version for team sharing.

## Main Flowchart

```mermaid
flowchart LR
    caller["Customer calls the restaurant"] --> twilio["Twilio receives the call"]

    subgraph backend["Backend"]
        inbound["1. Inbound route receives the call"]
        match["2. Find the right restaurant"]
        context["3. Build AI context:
restaurant name
hours
closures
rules
caller phone
greeting"]
        tools["5. Booking tools:
check
create
find
change
cancel"]
        webhook["6. Save call summary and transcript"]
    end

    subgraph db["Database"]
        restaurants["Restaurant setup"]
        bookings["Bookings"]
        customers["Customers"]
        history["Booking history"]
        calls["Call logs"]
    end

    subgraph el["ElevenLabs"]
        voice["4. AI speaks with caller"]
        personal["Gets context at call start"]
        summary["Sends after-call summary"]
    end

    subgraph dash["Dashboard"]
        home["Home"]
        bookingsui["Bookings"]
        callsui["Calls"]
        capacity["Capacity"]
        settings["Settings"]
    end

    twilio --> inbound
    inbound --> match
    match --> restaurants
    restaurants --> context
    context --> voice
    voice --> personal
    personal --> context
    voice --> tools
    tools --> bookings
    tools --> customers
    tools --> history
    summary --> webhook
    webhook --> calls

    bookings --> bookingsui
    history --> bookingsui
    calls --> callsui
    bookings --> capacity
    restaurants --> settings
    calls --> home
    bookings --> home

    voice -. "after call" .-> summary
    settings -. "staff updates rules and setup" .-> restaurants
```

## One-Line Reading Guide

- Twilio starts the call.
- The backend identifies the restaurant and prepares the AI.
- ElevenLabs runs the conversation.
- During the call, ElevenLabs asks the backend to do real booking work.
- The backend reads and writes the database.
- The dashboard shows the same data the AI used.

## Current Live Caveat

```mermaid
flowchart TD
    live["Live staging today"] --> ok["Call can start and booking tools can work"]
    live --> issue["After-call webhook is currently disabled"]
    issue --> why["Reason:
webhook signing secret does not match"]
    issue --> effect["Effect:
call summaries are not being saved through the normal webhook path"]
    effect --> fallback["Current workaround:
Calls page re-pulls recent conversations from ElevenLabs when opened"]
```
