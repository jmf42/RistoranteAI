from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Booking, CallLog
from app.schemas.analytics import (
    ActivityItem,
    AnalyticsOverview,
    CapacitySnapshot,
    DemandGap,
    EscalationBreakdown,
    HeatmapCell,
    MetricStat,
    TrendBundle,
    TrendPoint,
)
from app.schemas.common import CallOutcome
from app.services.availability import COUNTABLE_STATUSES, capacity_snapshot


def _count_bookings(db: Session, restaurant_id: str, day: date) -> int:
    stmt = select(func.count(Booking.id)).where(
        Booking.restaurant_id == restaurant_id,
        Booking.date == day,
        Booking.status.in_(COUNTABLE_STATUSES),
    )
    return int(db.scalar(stmt) or 0)


def _count_calls(db: Session, restaurant_id: str, day: date) -> int:
    start = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
    end = start + timedelta(days=1)
    stmt = select(func.count(CallLog.id)).where(
        CallLog.restaurant_id == restaurant_id,
        CallLog.started_at >= start,
        CallLog.started_at < end,
    )
    return int(db.scalar(stmt) or 0)


def _metric(value: float, yesterday: float, avg: float) -> MetricStat:
    delta_vs_yesterday = round(value - yesterday, 2)
    delta_vs_avg = round(value - avg, 2)
    status = "good"
    if value == 0:
        status = "attention"
    elif delta_vs_yesterday < 0:
        status = "warning"
    return MetricStat(
        value=value,
        delta_vs_yesterday=delta_vs_yesterday,
        delta_vs_7d_avg=delta_vs_avg,
        status=status,
    )


def _recent_activity(bookings: Iterable[Booking], calls: Iterable[CallLog]) -> list[ActivityItem]:
    items: list[ActivityItem] = []
    for booking in bookings:
        items.append(
            ActivityItem(
                id=booking.id,
                kind="booking",
                title=f"Prenotazione {booking.confirmation_code}",
                detail=f"{booking.party_size} coperti, stato {booking.status}",
                created_at=booking.updated_at.isoformat(),
                tone="olive" if booking.status in COUNTABLE_STATUSES else "brick",
            )
        )
    for call in calls:
        items.append(
            ActivityItem(
                id=call.id,
                kind="call",
                title=f"Chiamata {call.outcome.replace('_', ' ')}",
                detail=call.summary,
                created_at=call.started_at.isoformat(),
                tone="gold",
            )
        )
    return sorted(items, key=lambda item: item.created_at, reverse=True)[:8]


def overview(db: Session, *, restaurant_id: str, today: date | None = None) -> AnalyticsOverview:
    target_day = today or datetime.now(UTC).date()
    calls_today = _count_calls(db, restaurant_id, target_day)
    bookings_today = _count_bookings(db, restaurant_id, target_day)
    booking_rate = round((bookings_today / calls_today) * 100, 2) if calls_today else 0

    yesterday = target_day - timedelta(days=1)
    calls_yesterday = _count_calls(db, restaurant_id, yesterday)
    bookings_yesterday = _count_bookings(db, restaurant_id, yesterday)
    booking_rate_yesterday = round((bookings_yesterday / calls_yesterday) * 100, 2) if calls_yesterday else 0

    call_window = []
    booking_window = []
    rate_window = []
    for offset in range(1, 8):
        day = target_day - timedelta(days=offset)
        historical_calls = _count_calls(db, restaurant_id, day)
        historical_bookings = _count_bookings(db, restaurant_id, day)
        historical_rate = round((historical_bookings / historical_calls) * 100, 2) if historical_calls else 0
        call_window.append(historical_calls)
        booking_window.append(historical_bookings)
        rate_window.append(historical_rate)

    recent_bookings = db.scalars(
        select(Booking)
        .where(Booking.restaurant_id == restaurant_id)
        .order_by(Booking.updated_at.desc())
        .limit(5)
    ).all()
    recent_calls = db.scalars(
        select(CallLog)
        .where(CallLog.restaurant_id == restaurant_id)
        .order_by(CallLog.started_at.desc())
        .limit(5)
    ).all()

    demand_counter: Counter[str] = Counter()
    for call in recent_calls:
        requested_slot = (call.extra_data or {}).get("requested_slot_label")
        if requested_slot:
            demand_counter.update([requested_slot])
    demand_gaps = [
        DemandGap(label=label, total_requests=total)
        for label, total in demand_counter.most_common(4)
    ]

    return AnalyticsOverview(
        calls_today=_metric(calls_today, calls_yesterday, sum(call_window) / max(len(call_window), 1)),
        bookings_today=_metric(
            bookings_today, bookings_yesterday, sum(booking_window) / max(len(booking_window), 1)
        ),
        booking_rate_today=_metric(
            booking_rate,
            booking_rate_yesterday,
            sum(rate_window) / max(len(rate_window), 1),
        ),
        recent_activity=_recent_activity(recent_bookings, recent_calls),
        demand_gaps=demand_gaps,
    )


def trends(db: Session, *, restaurant_id: str, days: int = 14) -> TrendBundle:
    end_day = datetime.now(UTC).date()
    points: list[TrendPoint] = []
    for offset in reversed(range(days)):
        current_day = end_day - timedelta(days=offset)
        calls = _count_calls(db, restaurant_id, current_day)
        bookings = _count_bookings(db, restaurant_id, current_day)
        points.append(
            TrendPoint(
                date=current_day.isoformat(),
                calls=calls,
                bookings=bookings,
                booking_rate=round((bookings / calls) * 100, 2) if calls else 0,
            )
        )

    start_dt = datetime.now(UTC) - timedelta(days=days)
    call_rows = db.scalars(
        select(CallLog)
        .where(CallLog.restaurant_id == restaurant_id, CallLog.started_at >= start_dt)
        .order_by(CallLog.started_at.asc())
    ).all()
    heatmap_counter: defaultdict[tuple[int, int], int] = defaultdict(int)
    escalation_counter: Counter[str] = Counter()
    for row in call_rows:
        local_dt = row.started_at
        heatmap_counter[(local_dt.weekday(), local_dt.hour)] += 1
        if row.outcome in {
            CallOutcome.escalated,
            CallOutcome.escalation_failed,
            CallOutcome.abandoned,
        }:
            escalation_counter.update([row.outcome])

    heatmap = [
        HeatmapCell(weekday=weekday, hour=hour, calls=total)
        for (weekday, hour), total in sorted(heatmap_counter.items())
    ]
    escalations = [
        EscalationBreakdown(outcome=outcome, total=total)
        for outcome, total in escalation_counter.most_common()
    ]
    return TrendBundle(points=points, heatmap=heatmap, escalations=escalations)


def capacity(
    db: Session,
    *,
    restaurant,
    booking_date: date,
) -> CapacitySnapshot:
    return CapacitySnapshot(
        restaurant_id=restaurant.id,
        date=booking_date.isoformat(),
        slots=capacity_snapshot(db, restaurant=restaurant, booking_date=booking_date),
    )
