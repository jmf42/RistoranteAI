from __future__ import annotations

import hashlib
from dataclasses import replace

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import (
    accessible_restaurant_id,
    get_current_user,
    get_db,
    get_restaurant_cached,
    get_restaurant_or_404,
    invalidate_restaurant_cache,
    require_roles,
)
from app.models import User
from app.schemas.studio import (
    StudioAgentPreviewResponse,
    StudioChecklistItem,
    StudioConfigDiffItem,
    StudioConfigUpdateRequest,
    StudioConfigUpdateResponse,
    StudioPreset,
    StudioScenario,
    StudioSessionOverrides,
    StudioSimulationRequest,
    StudioSimulationResponse,
    StudioToolTestRequest,
    StudioToolTestResponse,
)
from app.services.openai_realtime import (
    PRACTICAL_STUDIO_FIELDS,
    SUPPORTED_RUNTIME_OVERRIDE_FIELDS,
    RealtimeCallState,
    RealtimeSessionOverrides,
    _ingest_assistant_transcript,
    _ingest_user_transcript,
    _sync_dispatch_tool,
    build_realtime_instructions,
    build_realtime_tools,
    build_session_update,
    default_session_overrides,
    restaurant_session_overrides,
    run_text_simulation,
    studio_checklist,
    studio_practical_config_diff,
    studio_presets,
    studio_prompt_diagnostics,
    studio_readiness,
    studio_recommendations,
    studio_scenarios,
)

router = APIRouter(
    prefix="/studio",
    tags=["studio"],
    dependencies=[Depends(require_roles("operator"))],
)


def _merged_overrides(
    restaurant,
    overrides: StudioSessionOverrides | None,
) -> RealtimeSessionOverrides:
    base = restaurant_session_overrides(restaurant)
    if overrides is None:
        return base
    return replace(base, **overrides.model_dump(exclude_none=True))


def _effective_prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]


@router.get("/agent", response_model=StudioAgentPreviewResponse)
def agent_preview(
    restaurant_id: str,
    caller_phone: str = "+390000000000",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StudioAgentPreviewResponse:
    resolved_id = accessible_restaurant_id(
        db,
        current_user=current_user,
        restaurant_id=restaurant_id,
    )
    restaurant = get_restaurant_or_404(db, resolved_id)
    baseline_overrides = default_session_overrides()
    effective_overrides = restaurant_session_overrides(restaurant)
    prompt = build_realtime_instructions(restaurant, caller_phone=caller_phone)
    session_update = build_session_update(
        restaurant,
        caller_phone=caller_phone,
        output_modalities=("audio",),
        overrides=effective_overrides,
        include_diagnostics=True,
        tool_names=(
            "check_availability",
            "find_booking",
            "create_booking",
            "modify_booking",
            "cancel_booking",
            "escalate_to_human",
        ),
    )
    return StudioAgentPreviewResponse(
        prompt=prompt,
        session_update=session_update,
        tools=build_realtime_tools(),
        checklist=[StudioChecklistItem(**item) for item in studio_checklist(session_update)],
        readiness=[StudioChecklistItem(**item) for item in studio_readiness(restaurant)],
        prompt_diagnostics=[
            StudioChecklistItem(**item)
            for item in studio_prompt_diagnostics(
                prompt,
                restaurant=restaurant,
                effective_overrides=effective_overrides,
            )
        ],
        recommendations=[
            StudioChecklistItem(**item)
            for item in studio_recommendations(
                restaurant=restaurant,
                prompt=prompt,
                effective_overrides=effective_overrides,
                session_update=session_update,
            )
        ],
        config_diff=[
            StudioConfigDiffItem(**item)
            for item in studio_practical_config_diff(restaurant, effective_overrides)
        ],
        presets=[StudioPreset(**item) for item in studio_presets()],
        scenarios=[StudioScenario(**item) for item in studio_scenarios()],
        saved_prompt_override=restaurant.openai_prompt_override,
        saved_session_overrides=StudioSessionOverrides.model_validate(
            restaurant.openai_realtime_settings or {}
        ),
        default_session_overrides=StudioSessionOverrides.model_validate(
            {
                field: getattr(baseline_overrides, field)
                for field in RealtimeSessionOverrides.__dataclass_fields__.keys()
            }
        ),
        effective_session_overrides=StudioSessionOverrides.model_validate(
            {
                field: getattr(effective_overrides, field)
                for field in RealtimeSessionOverrides.__dataclass_fields__.keys()
            }
        ),
    )


@router.post("/tool-test", response_model=StudioToolTestResponse)
def tool_test(
    payload: StudioToolTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StudioToolTestResponse:
    resolved_id = accessible_restaurant_id(
        db,
        current_user=current_user,
        restaurant_id=payload.restaurant_id,
    )
    restaurant = get_restaurant_or_404(db, resolved_id)
    session_factory = sessionmaker(bind=db.get_bind(), autoflush=False, autocommit=False)
    state = RealtimeCallState(
        caller_phone=payload.caller_phone,
        twilio_call_sid="studio-tool-test",
    )
    if payload.last_assistant_transcript:
        _ingest_assistant_transcript(state, payload.last_assistant_transcript)
    if payload.last_user_transcript:
        _ingest_user_transcript(state, payload.last_user_transcript)
    result = _sync_dispatch_tool(
        session_factory,
        restaurant=restaurant,
        state=state,
        tool_name=payload.tool_name,
        arguments=payload.arguments,
    )
    return StudioToolTestResponse(result=result)


@router.post("/simulate", response_model=StudioSimulationResponse)
async def simulate(
    payload: StudioSimulationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StudioSimulationResponse:
    resolved_id = accessible_restaurant_id(
        db,
        current_user=current_user,
        restaurant_id=payload.restaurant_id,
    )
    restaurant = get_restaurant_or_404(db, resolved_id)
    simulation = await run_text_simulation(
        db_factory=sessionmaker(bind=db.get_bind(), autoflush=False, autocommit=False),
        restaurant=restaurant,
        caller_phone=payload.caller_phone,
        user_messages=payload.user_messages,
        prompt_override=payload.prompt_override,
        overrides=_merged_overrides(restaurant, payload.session_overrides),
    )
    return StudioSimulationResponse(**simulation)


@router.put("/config", response_model=StudioConfigUpdateResponse)
def save_studio_config(
    payload: StudioConfigUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StudioConfigUpdateResponse:
    resolved_id = accessible_restaurant_id(
        db,
        current_user=current_user,
        restaurant_id=payload.restaurant_id,
    )
    restaurant = get_restaurant_or_404(db, resolved_id)

    prompt = (payload.prompt_override or "").strip()
    restaurant.openai_prompt_override = prompt or None
    saved_overrides = payload.session_overrides.model_dump(exclude_none=True) if payload.session_overrides else {}
    allowed_saved_fields = PRACTICAL_STUDIO_FIELDS | {
        field
        for field in SUPPORTED_RUNTIME_OVERRIDE_FIELDS
        if field == "semantic_vad_eagerness"
    }
    restaurant.openai_realtime_settings = {
        key: value for key, value in saved_overrides.items() if key in allowed_saved_fields
    }
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)
    invalidate_restaurant_cache(restaurant.id)

    live_restaurant = get_restaurant_cached(db, restaurant.id)
    live_prompt = build_realtime_instructions(live_restaurant, caller_phone="+390000000000")
    live_overrides = restaurant_session_overrides(live_restaurant)
    live_diagnostics = [
        StudioChecklistItem(**item)
        for item in studio_prompt_diagnostics(
            live_prompt,
            restaurant=live_restaurant,
            effective_overrides=live_overrides,
        )
    ]
    diagnostic_warnings = sum(1 for item in live_diagnostics if item.status != "good")
    deployment_status = "live" if diagnostic_warnings == 0 else "warning"
    deployment_message = (
        "Live publish confirmed. The backend cache was refreshed and the next new call will use this exact prompt."
        if diagnostic_warnings == 0
        else (
            "Live publish confirmed, but the active prompt still has best-practice warnings. "
            "Review the prompt quality checks before the next live tuning pass."
        )
    )
    saved_overrides = StudioSessionOverrides.model_validate(restaurant.openai_realtime_settings or {})
    return StudioConfigUpdateResponse(
        saved_prompt_override=restaurant.openai_prompt_override,
        saved_session_overrides=saved_overrides,
        deployed=True,
        deployment_status=deployment_status,
        deployment_message=deployment_message,
        effective_prompt=live_prompt,
        effective_prompt_hash=_effective_prompt_hash(live_prompt),
        effective_session_overrides=StudioSessionOverrides.model_validate(
            {
                field: getattr(live_overrides, field)
                for field in RealtimeSessionOverrides.__dataclass_fields__.keys()
            }
        ),
        prompt_diagnostics=live_diagnostics,
        published_at=live_restaurant.updated_at,
    )


@router.delete("/config", response_model=StudioConfigUpdateResponse)
def reset_studio_config(
    restaurant_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StudioConfigUpdateResponse:
    resolved_id = accessible_restaurant_id(
        db,
        current_user=current_user,
        restaurant_id=restaurant_id,
    )
    restaurant = get_restaurant_or_404(db, resolved_id)

    restaurant.openai_prompt_override = None
    restaurant.openai_realtime_settings = {}
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)
    invalidate_restaurant_cache(restaurant.id)
    live_restaurant = get_restaurant_cached(db, restaurant.id)
    live_prompt = build_realtime_instructions(live_restaurant, caller_phone="+390000000000")
    live_overrides = restaurant_session_overrides(live_restaurant)

    return StudioConfigUpdateResponse(
        saved_prompt_override=None,
        saved_session_overrides=StudioSessionOverrides(),
        deployed=True,
        deployment_status="live",
        deployment_message="Studio config reset. The next new call will use the backend default prompt and settings.",
        effective_prompt=live_prompt,
        effective_prompt_hash=_effective_prompt_hash(live_prompt),
        effective_session_overrides=StudioSessionOverrides.model_validate(
            {
                field: getattr(live_overrides, field)
                for field in RealtimeSessionOverrides.__dataclass_fields__.keys()
            }
        ),
        prompt_diagnostics=[
            StudioChecklistItem(**item)
            for item in studio_prompt_diagnostics(
                live_prompt,
                restaurant=live_restaurant,
                effective_overrides=live_overrides,
            )
        ],
        published_at=live_restaurant.updated_at,
    )
