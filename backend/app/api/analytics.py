from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import accessible_restaurant_id, get_current_user, get_db, get_restaurant_or_404
from app.models import User
from app.schemas.analytics import AnalyticsOverview, CapacitySnapshot, TrendBundle
from app.services.analytics import capacity, overview, trends

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverview)
def analytics_overview(
    restaurant_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalyticsOverview:
    resolved_id = accessible_restaurant_id(db, current_user=current_user, restaurant_id=restaurant_id)
    return overview(db, restaurant_id=resolved_id)


@router.get("/trends", response_model=TrendBundle)
def analytics_trends(
    restaurant_id: str | None = Query(default=None),
    days: int = Query(default=14, ge=7, le=60),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrendBundle:
    resolved_id = accessible_restaurant_id(db, current_user=current_user, restaurant_id=restaurant_id)
    return trends(db, restaurant_id=resolved_id, days=days)


@router.get("/capacity", response_model=CapacitySnapshot)
def analytics_capacity(
    restaurant_id: str | None = Query(default=None),
    booking_date: date = Query(alias="date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CapacitySnapshot:
    resolved_id = accessible_restaurant_id(db, current_user=current_user, restaurant_id=restaurant_id)
    restaurant = get_restaurant_or_404(db, resolved_id)
    return capacity(db, restaurant=restaurant, booking_date=booking_date)
