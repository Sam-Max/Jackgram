import time
import uuid
from typing import Any, Dict, Optional


class SearchSessionStore:
    def __init__(self, ttl_seconds: int = 900) -> None:
        self.ttl_seconds = ttl_seconds
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def _now(self) -> int:
        return int(time.time())

    def cleanup_expired(self) -> None:
        now = self._now()
        expired_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if session.get("expires_at", 0) <= now
        ]
        for session_id in expired_ids:
            self._sessions.pop(session_id, None)

    def create_session(self, sender_id: int, query: str, results: list[Dict[str, Any]]) -> str:
        self.cleanup_expired()
        session_id = uuid.uuid4().hex[:8]
        now = self._now()
        self._sessions[session_id] = {
            "session_id": session_id,
            "sender_id": sender_id,
            "query": query,
            "results": results,
            "created_at": now,
            "expires_at": now + self.ttl_seconds,
            "selected_result_idx": None,
            "selected_season": None,
            "selected_episode_idx": None,
            "results_page": 1,
            "seasons_page": 1,
            "episodes_page": 1,
            "quality_page": 1,
            "quality_scope": "item",
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        self.cleanup_expired()
        session = self._sessions.get(session_id)
        if not session:
            return None
        return session

    def touch(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = self.get_session(session_id)
        if not session:
            return None
        session["expires_at"] = self._now() + self.ttl_seconds
        return session

    def update_session(self, session_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        session = self.get_session(session_id)
        if not session:
            return None
        session.update(fields)
        return self.touch(session_id)

    def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
