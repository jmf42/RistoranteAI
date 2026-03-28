from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import accessible_restaurant_id, get_current_user, get_db, get_restaurant_or_404
from app.core.cache import analytics_cache
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
    cache_key = f"overview:{resolved_id}"
    cached = analytics_cache.get(cache_key)
    if cached is not None:
        return cached
    result = overview(db, restaurant_id=resolved_id)
    analytics_cache.set(cache_key, result)
    return result


@router.get("/trends", response_model=TrendBundle)
def analytics_trends(
    restaurant_id: str | None = Query(default=None),
    days: int = Query(default=14, ge=7, le=60),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrendBundle:
    resolved_id = accessible_restaurant_id(db, current_user=current_user, restaurant_id=restaurant_id)
    cache_key = f"trends:{resolved_id}:{days}"
    cached = analytics_cache.get(cache_key)
    if cached is not None:
        return cached
    result = trends(db, restaurant_id=resolved_id, days=days)
    analytics_cache.set(cache_key, result)
    return result


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
