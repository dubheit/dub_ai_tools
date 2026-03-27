# Copyright 2025 Dubhe Srls
# License OPL-1

"""
Context tracking service for MCP sessions.
Tracks recent operations per session to provide context in responses.
"""
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

_logger = logging.getLogger(__name__)

# Singleton instance
_tracker_instance = None
_tracker_lock = threading.Lock()


@dataclass
class RecordInfo:
    """Information about a tracked record operation."""
    model: str
    id: int
    display_name: str
    operation: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


@dataclass
class SessionContext:
    """Context for an active session."""
    working_records: deque = field(default_factory=lambda: deque(maxlen=10))
    last_activity: datetime = field(default_factory=datetime.utcnow)


class ContextTracker:
    """
    Singleton service for tracking operations per MCP session.
    Thread-safe for concurrent access from multiple sessions.
    """

    def __init__(self):
        self._sessions: dict[str, SessionContext] = {}
        self._lock = threading.Lock()

    def track_operation(
        self,
        session_id: str,
        model: str,
        ids: list[int],
        display_names: list[str],
        operation: str
    ):
        """
        Track a record operation for a session.

        Args:
            session_id: The session identifier
            model: Odoo model name (e.g., 'res.partner')
            ids: List of record IDs operated on
            display_names: List of display names for the records
            operation: Type of operation ('search', 'read', 'create', 'update', 'delete', 'call_method')
        """
        if not session_id or not model or not ids:
            return

        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionContext()

            ctx = self._sessions[session_id]
            ctx.last_activity = datetime.utcnow()

            # Add each record as a separate tracked item
            for idx, rec_id in enumerate(ids):
                display_name = display_names[idx] if idx < len(display_names) else f"ID {rec_id}"
                info = RecordInfo(
                    model=model,
                    id=rec_id,
                    display_name=display_name,
                    operation=operation
                )
                ctx.working_records.append(info)

            _logger.debug(
                "Tracked %s operation on %s (IDs: %s) for session %s",
                operation, model, ids, session_id
            )

    def get_context(self, session_id: str) -> Optional[dict]:
        """
        Get the current context for a session.

        Returns:
            Dictionary with working_records and session_summary, or None if no context.
        """
        with self._lock:
            ctx = self._sessions.get(session_id)
            if not ctx or not ctx.working_records:
                return None

            records = []
            for info in ctx.working_records:
                records.append({
                    "model": info.model,
                    "id": info.id,
                    "display_name": info.display_name,
                    "operation": info.operation,
                    "timestamp": info.timestamp
                })

            # Build summary from most recent record
            latest = ctx.working_records[-1] if ctx.working_records else None
            summary = ""
            if latest:
                summary = f"Working on {latest.model} '{latest.display_name}' (ID: {latest.id})"

            return {
                "working_records": records,
                "session_summary": summary
            }

    def cleanup_stale_sessions(self, ttl_minutes: int = 30):
        """
        Remove sessions that have been inactive for longer than ttl_minutes.

        Args:
            ttl_minutes: Time-to-live in minutes (default 30)
        """
        cutoff = datetime.utcnow() - timedelta(minutes=ttl_minutes)
        removed = []

        with self._lock:
            stale_sessions = [
                sid for sid, ctx in self._sessions.items()
                if ctx.last_activity < cutoff
            ]
            for sid in stale_sessions:
                del self._sessions[sid]
                removed.append(sid)

        if removed:
            _logger.info("Cleaned up %d stale context sessions", len(removed))

    def clear_session(self, session_id: str):
        """
        Clear context for a specific session (e.g., on disconnect).

        Args:
            session_id: The session identifier to clear
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                _logger.debug("Cleared context for session %s", session_id)


def get_tracker() -> ContextTracker:
    """
    Get the singleton ContextTracker instance.

    Returns:
        The global ContextTracker instance
    """
    global _tracker_instance
    if _tracker_instance is None:
        with _tracker_lock:
            if _tracker_instance is None:
                _tracker_instance = ContextTracker()
    return _tracker_instance
