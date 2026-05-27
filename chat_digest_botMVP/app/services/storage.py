from __future__ import annotations

from app.domain.models import ConversationSession


class InMemorySessionStore:
    """Simple session storage for MVP.

    For production, replace this class with Redis/PostgreSQL storage so sessions survive restarts.
    """

    def __init__(self) -> None:
        self._sessions: dict[int, ConversationSession] = {}

    def get(self, user_id: int) -> ConversationSession:
        if user_id not in self._sessions:
            self._sessions[user_id] = ConversationSession(user_id=user_id)
        return self._sessions[user_id]

    def clear(self, user_id: int) -> None:
        self.get(user_id).clear()
