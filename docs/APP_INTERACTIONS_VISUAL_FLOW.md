# App Interactions Visual Flow

Last updated: `2026-04-10`

```mermaid
flowchart LR
    caller["Customer calls the restaurant"] --> twilio["Twilio phone number"]
    twilio --> inbound["POST /api/twilio/inbound"]

    subgraph backend["Backend"]
        inbound --> match["Resolve restaurant"]
        match --> bridge["Return TwiML stream + open realtime bridge"]
        bridge --> tools["Server-side booking tools"]
        bridge --> calls["Persist call log + transcript preview"]
    end

    subgraph openai["OpenAI Realtime"]
        model["Live voice model"]
    end

    subgraph db["Database"]
        restaurants["Restaurants"]
        bookings["Bookings"]
        events["Booking events"]
        calllogs["Call logs"]
    end

    bridge --> model
    model --> bridge
    tools --> bookings
    tools --> events
    match --> restaurants
    calls --> calllogs
```

## Plain-English Summary

- Twilio handles the phone number.
- The backend decides which restaurant the call belongs to.
- The backend streams the audio to OpenAI Realtime.
- OpenAI talks to the caller.
- Real booking work still happens in backend tools and the database.
- Transfer to the restaurant is a controlled fallback, not the default answer to unclear booking details.
- The dashboard reads the same booking and call data the phone agent produced.
- The studio gives operators a safe place to preview, test, and regression-check the live agent config.
