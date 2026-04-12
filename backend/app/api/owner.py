from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import accessible_restaurant_id, get_current_user, get_db, get_restaurant_or_404
from app.models import User
from app.schemas.owner import OwnerAgendaResponse
from app.services.owner import owner_agenda

router = APIRouter(prefix="/owner", tags=["owner"])


@router.get("/agenda", response_model=OwnerAgendaResponse)
def get_owner_agenda(
    restaurant_id: str | None = Query(default=None),
    days: int = Query(default=7, ge=1, le=14),
    start_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OwnerAgendaResponse:
    resolved_id = accessible_restaurant_id(db, current_user=current_user, restaurant_id=restaurant_id)
    restaurant = get_restaurant_or_404(db, resolved_id)
    return owner_agenda(db, restaurant=restaurant, days=days, start_day=start_date)
