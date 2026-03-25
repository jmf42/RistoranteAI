# Tool Definitions

All tool endpoints are implemented in `backend/app/api/tools.py`.

## Auth

Every tool request must include:

- Header: `X-Ristorante-Tool-Secret`
- Value: `ELEVENLABS_TOOL_SECRET`

## `check_availability`

`POST /api/tools/check-availability`

```json
{
  "restaurant_id": "uuid",
  "date": "2026-03-29",
  "time_preference": "20:30:00",
  "party_size": 5
}
```

## `create_booking`

`POST /api/tools/create-booking`

```json
{
  "restaurant_id": "uuid",
  "date": "2026-03-29",
  "time": "20:30:00",
  "party_size": 5,
  "customer_name": "Rossi",
  "customer_phone": "+393331234567",
  "caller_phone": "+393331234567",
  "special_requests": "Allergia glutine"
}
```

## `find_booking`

`POST /api/tools/find-booking`

```json
{
  "restaurant_id": "uuid",
  "caller_phone": "+393331234567"
}
```

or

```json
{
  "restaurant_id": "uuid",
  "confirmation_code": "TM-042901"
}
```

## `modify_booking`

`POST /api/tools/modify-booking`

```json
{
  "confirmation_code": "TM-042901",
  "changes": {
    "date": "2026-03-30",
    "time": "21:00:00"
  }
}
```

## `cancel_booking`

`POST /api/tools/cancel-booking`

```json
{
  "confirmation_code": "TM-042901"
}
```
