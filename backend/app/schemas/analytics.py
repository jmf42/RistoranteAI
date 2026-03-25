from __future__ import annotations

from app.schemas.common import AppBaseModel


class MetricStat(AppBaseModel):
    value: float
    delta_vs_yesterday: float
    delta_vs_7d_avg: float
    status: str


class ActivityItem(AppBaseModel):
    id: str
    kind: str
    title: str
    detail: str
    created_at: str
    tone: str


class DemandGap(AppBaseModel):
    label: str
    total_requests: int


class AnalyticsOverview(AppBaseModel):
    calls_today: MetricStat
    bookings_today: MetricStat
    booking_rate_today: MetricStat
    recent_activity: list[ActivityItem]
    demand_gaps: list[DemandGap]


class CapacitySlot(AppBaseModel):
    turno: str
    start: str
    end: str
    booked_covers: int
    max_covers: int
    remaining_covers: int
    occupancy_ratio: float


class CapacitySnapshot(AppBaseModel):
    restaurant_id: str
    date: str
    slots: list[CapacitySlot]


class TrendPoint(AppBaseModel):
    date: str
    calls: int
    bookings: int
    booking_rate: float


class HeatmapCell(AppBaseModel):
    weekday: int
    hour: int
    calls: int


class EscalationBreakdown(AppBaseModel):
    outcome: str
    total: int


class TrendBundle(AppBaseModel):
    points: list[TrendPoint]
    heatmap: list[HeatmapCell]
    escalations: list[EscalationBreakdown]
