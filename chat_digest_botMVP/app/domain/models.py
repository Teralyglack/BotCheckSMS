from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class MessageKind(StrEnum):
    TEXT = "text"
    VOICE = "voice"
    VIDEO_NOTE = "video_note"
    PHOTO = "photo"
    DOCUMENT_IMAGE = "document_image"
    AUDIO = "audio"


class OutputFormat(StrEnum):
    TRANSCRIPT = "transcript"
    SUMMARY = "summary"
    BULLETS = "bullets"


@dataclass(slots=True)
class ExtractedMessage:
    role: str
    content: str
    kind: MessageKind
    source_message_id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    meta: dict[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not self.content.strip()


@dataclass
class ConversationSession:
    user_id: int
    messages: list[ExtractedMessage] = field(default_factory=list)
    role_map: dict[str, str] = field(default_factory=dict)
    unknown_role_counter: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add(self, message: ExtractedMessage) -> None:
        self.messages.append(message)
        self.updated_at = datetime.now(timezone.utc)

    def clear(self) -> None:
        self.messages.clear()
        self.role_map.clear()
        self.unknown_role_counter = 0
        self.updated_at = datetime.now(timezone.utc)

    def resolve_role(self, raw_role: str | None) -> str:
        """Return stable human-readable role for this session."""
        normalized = (raw_role or "").strip()
        if normalized:
            return normalized

        key = "__unknown__"
        if key not in self.role_map:
            self.unknown_role_counter += 1
            self.role_map[key] = f"Человек {self.unknown_role_counter}"
        return self.role_map[key]
