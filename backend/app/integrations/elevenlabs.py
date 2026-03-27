from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from elevenlabs.client import ElevenLabs

from app.core.config import settings


@dataclass
class SyncResult:
    synced: bool
    message: str


class ElevenLabsService:
    def __init__(self) -> None:
        self._client = ElevenLabs(api_key=settings.elevenlabs_api_key or "placeholder")

    @staticmethod
    def _dump_model(value: Any) -> Any:
        if value is None:
            return None
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="python")
        if isinstance(value, list):
            return [ElevenLabsService._dump_model(item) for item in value]
        if isinstance(value, dict):
            return {key: ElevenLabsService._dump_model(item) for key, item in value.items()}
        return value

    @staticmethod
    def _serialize_transcript_entry(entry: Any) -> str | None:
        data = ElevenLabsService._dump_model(entry)
        if not isinstance(data, dict):
            return None
        role = data.get("role") or data.get("speaker") or "speaker"
        message = data.get("message") or data.get("text") or data.get("original_message")
        if not message:
            return None
        return f"{str(role).replace('_', ' ').title()}: {message}"

    @classmethod
    def _serialize_transcript(cls, transcript: Any) -> str | None:
        if isinstance(transcript, str):
            stripped = transcript.strip()
            return stripped or None
        if not transcript:
            return None
        lines = [
            serialized
            for serialized in (cls._serialize_transcript_entry(entry) for entry in transcript)
            if serialized
        ]
        return "\n".join(lines) if lines else None

    @staticmethod
    def _merge_tags(existing_tags: list[str] | None, restaurant_slug: str) -> list[str]:
        merged = list(existing_tags or [])
        for tag in ("ristorante-ai", f"restaurant:{restaurant_slug}"):
            if tag not in merged:
                merged.append(tag)
        return merged

    @staticmethod
    def _error_message(exc: Exception) -> str:
        message = str(exc).strip()
        return message or exc.__class__.__name__

    def verify_webhook(self, payload: bytes, signature: str):
        if not settings.elevenlabs_webhook_secret:
            return None
        return self._client.webhooks.construct_event(
            payload=payload.decode("utf-8"),
            signature=signature,
            secret=settings.elevenlabs_webhook_secret,
        )

    def sync_restaurant_config(self, restaurant) -> SyncResult:
        if not settings.elevenlabs_api_key:
            return SyncResult(
                synced=False,
                message="ElevenLabs sync skipped because ELEVENLABS_API_KEY is not configured.",
            )
        if not restaurant.elevenlabs_agent_id:
            return SyncResult(
                synced=False,
                message="ElevenLabs sync skipped because the restaurant has no agent id.",
            )
        try:
            agent = self._client.conversational_ai.agents.get(restaurant.elevenlabs_agent_id)
        except Exception as exc:  # noqa: BLE001
            return SyncResult(
                synced=False,
                message=f"ElevenLabs sync failed while loading the agent: {self._error_message(exc)}",
            )

        update_payload: dict[str, Any] = {}
        changes: list[str] = []
        if agent.name != restaurant.name:
            update_payload["name"] = restaurant.name
            changes.append("display name")

        merged_tags = self._merge_tags(agent.tags, restaurant.slug)
        if merged_tags != list(agent.tags or []):
            update_payload["tags"] = merged_tags
            changes.append("tags")

        if not update_payload:
            return SyncResult(
                synced=True,
                message="ElevenLabs agent reachable and already aligned with this restaurant.",
            )

        try:
            self._client.conversational_ai.agents.update(
                restaurant.elevenlabs_agent_id,
                **update_payload,
            )
        except Exception as exc:  # noqa: BLE001
            return SyncResult(
                synced=False,
                message=f"ElevenLabs agent found, but the sync update failed: {self._error_message(exc)}",
            )

        return SyncResult(
            synced=True,
            message=f"ElevenLabs agent synced successfully: {', '.join(changes)} updated.",
        )

    def register_twilio_call(
        self,
        *,
        agent_id: str,
        from_number: str,
        to_number: str,
        conversation_initiation_client_data: dict[str, Any],
        direction: str = "inbound",
    ) -> str:
        if not settings.elevenlabs_api_key:
            raise RuntimeError("ELEVENLABS_API_KEY is not configured")
        return self._client.conversational_ai.twilio.register_call(
            agent_id=agent_id,
            from_number=from_number,
            to_number=to_number,
            direction=direction,
            conversation_initiation_client_data=conversation_initiation_client_data,
        )

    def fetch_conversation_transcript(self, conversation_id: str) -> dict | None:
        if not settings.elevenlabs_api_key:
            return None
        try:
            conversation = self._client.conversational_ai.conversations.get(conversation_id)
        except Exception:  # noqa: BLE001
            return None

        analysis = self._dump_model(conversation.analysis) or {}
        metadata = self._dump_model(conversation.metadata) or {}
        initiation_data = self._dump_model(conversation.conversation_initiation_client_data) or {}
        return {
            "conversation_id": conversation.conversation_id,
            "agent_id": conversation.agent_id,
            "agent_name": conversation.agent_name,
            "status": str(conversation.status),
            "analysis": analysis,
            "metadata": metadata,
            "conversation_initiation_client_data": initiation_data,
            "transcript": self._serialize_transcript(conversation.transcript),
        }


elevenlabs_service = ElevenLabsService()
