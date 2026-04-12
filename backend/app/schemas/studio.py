from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from app.schemas.common import AppBaseModel


class StudioSessionOverrides(AppBaseModel):
    model: str | None = None
    voice: str | None = None
    tool_choice: Literal["auto", "none", "required"] | None = None
    temperature: float | None = Field(default=None, ge=0.6, le=1.2)
    speed: float | None = Field(default=None, ge=0.25, le=1.5)
    max_response_output_tokens: int | None = Field(default=None, ge=1, le=4096)
    turn_detection_type: Literal["server_vad", "semantic_vad"] | None = None
    vad_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    vad_prefix_padding_ms: int | None = Field(default=None, ge=0, le=2000)
    vad_silence_duration_ms: int | None = Field(default=None, ge=100, le=5000)
    vad_idle_timeout_ms: int | None = Field(default=None, ge=0, le=60000)
    semantic_vad_eagerness: Literal["low", "medium", "high", "auto"] | None = None
    interrupt_response: bool | None = None
    create_response: bool | None = None
    noise_reduction_type: Literal["near_field", "far_field", "off"] | None = None
    transcription_model: str | None = None
    input_language: str | None = None
    tracing_enabled: bool | None = None
    truncation_mode: Literal["retention_ratio", "disabled"] | None = None
    truncation_retention_ratio: float | None = Field(default=None, ge=0.1, le=1.0)
    truncation_post_instructions_tokens: int | None = Field(default=None, ge=256, le=16000)


class StudioChecklistItem(AppBaseModel):
    label: str
    status: str
    detail: str


class StudioPreset(AppBaseModel):
    id: str
    label: str
    description: str
    session_overrides: StudioSessionOverrides


class StudioScenario(AppBaseModel):
    id: str
    label: str
    message: str
    goal: str


class StudioConfigDiffItem(AppBaseModel):
    field: str
    label: str
    baseline: str
    effective: str
    source: str


class StudioAgentPreviewResponse(AppBaseModel):
    prompt: str
    session_update: dict[str, Any]
    tools: list[dict[str, Any]]
    checklist: list[StudioChecklistItem]
    readiness: list[StudioChecklistItem] = Field(default_factory=list)
    prompt_diagnostics: list[StudioChecklistItem] = Field(default_factory=list)
    recommendations: list[StudioChecklistItem] = Field(default_factory=list)
    config_diff: list[StudioConfigDiffItem] = Field(default_factory=list)
    presets: list[StudioPreset] = Field(default_factory=list)
    scenarios: list[StudioScenario] = Field(default_factory=list)
    saved_prompt_override: str | None = None
    saved_session_overrides: StudioSessionOverrides = Field(default_factory=StudioSessionOverrides)
    default_session_overrides: StudioSessionOverrides = Field(default_factory=StudioSessionOverrides)
    effective_session_overrides: StudioSessionOverrides = Field(default_factory=StudioSessionOverrides)


class StudioConfigUpdateRequest(AppBaseModel):
    restaurant_id: str
    prompt_override: str | None = None
    session_overrides: StudioSessionOverrides | None = None


class StudioConfigUpdateResponse(AppBaseModel):
    ok: bool = True
    saved_prompt_override: str | None = None
    saved_session_overrides: StudioSessionOverrides = Field(default_factory=StudioSessionOverrides)
    deployed: bool = True
    deployment_status: Literal["live", "warning"] = "live"
    deployment_message: str = ""
    effective_prompt: str = ""
    effective_prompt_hash: str = ""
    effective_session_overrides: StudioSessionOverrides = Field(default_factory=StudioSessionOverrides)
    prompt_diagnostics: list[StudioChecklistItem] = Field(default_factory=list)
    published_at: datetime | None = None


class StudioToolTestRequest(AppBaseModel):
    restaurant_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    caller_phone: str = "+390000000000"
    last_user_transcript: str = ""
    last_assistant_transcript: str = ""


class StudioToolTestResponse(AppBaseModel):
    result: dict[str, Any]


class StudioSimulationRequest(AppBaseModel):
    restaurant_id: str
    caller_phone: str = "+390000000000"
    user_messages: list[str] = Field(default_factory=list, min_length=1)
    prompt_override: str | None = None
    session_overrides: StudioSessionOverrides | None = None

    @field_validator("user_messages", mode="before")
    @classmethod
    def normalize_messages(cls, value: list[str]) -> list[str]:
        if not isinstance(value, list):
            return value
        return [str(item).strip() for item in value if str(item).strip()]


class StudioTranscriptTurn(AppBaseModel):
    role: str
    content: str


class StudioSimulationResponse(AppBaseModel):
    assistant_message: str
    transcript: list[StudioTranscriptTurn]
    tool_events: list[dict[str, Any]]
    usage: dict[str, Any] | None = None
