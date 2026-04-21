# Copyright 2025 Dubhe Srls
# License LGPL-3

"""
Ring buffer for capturing Odoo logs.
Used by MCP get_logs tool.
"""

import logging
import threading
from collections import deque
from datetime import datetime
from typing import List, Optional


class LogEntry:
    """Single log entry."""

    __slots__ = ('timestamp', 'level', 'module', 'message', 'db')

    def __init__(self, timestamp: datetime, level: str, module: str,
                 message: str, db: str = ""):
        self.timestamp = timestamp
        self.level = level
        self.module = module
        self.message = message
        self.db = db

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "module": self.module,
            "message": self.message,
            "db": self.db,
        }


class LogBuffer:
    """Thread-safe ring buffer for log entries."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, maxsize: int = 500):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, maxsize: int = 500):
        if self._initialized:
            return
        self._buffer = deque(maxlen=maxsize)
        self._buffer_lock = threading.Lock()
        self._initialized = True

    def add(self, entry: LogEntry):
        """Add log entry to buffer."""
        with self._buffer_lock:
            self._buffer.append(entry)

    def get_logs(
        self,
        level: Optional[str] = None,
        module: Optional[str] = None,
        db: Optional[str] = None,
        limit: int = 50,
        minutes: Optional[int] = None,
    ) -> List[dict]:
        """Get filtered logs from buffer."""
        with self._buffer_lock:
            entries = list(self._buffer)

        # Filter by time
        if minutes:
            cutoff = datetime.now().timestamp() - (minutes * 60)
            entries = [
                e for e in entries
                if e.timestamp.timestamp() > cutoff
            ]

        # Filter by level
        if level:
            level_upper = level.upper()
            entries = [e for e in entries if e.level == level_upper]

        # Filter by module
        if module:
            entries = [
                e for e in entries
                if module.lower() in e.module.lower()
            ]

        # Filter by database
        if db:
            entries = [e for e in entries if e.db == db]

        # Return most recent, limited
        entries = entries[-limit:]

        return [e.to_dict() for e in entries]

    def clear(self):
        """Clear the buffer."""
        with self._buffer_lock:
            self._buffer.clear()


class McpLogHandler(logging.Handler):
    """Custom log handler that captures logs to the ring buffer."""

    # Sensitive patterns to filter out
    SENSITIVE_PATTERNS = (
        'password', 'passwd', 'secret', 'token', 'api_key',
        'apikey', 'bearer', 'authorization', 'credential',
    )

    def __init__(self, buffer: LogBuffer):
        super().__init__()
        self.buffer = buffer

    def _sanitize_message(self, message: str) -> str:
        """Remove potentially sensitive information from log message."""
        msg_lower = message.lower()
        for pattern in self.SENSITIVE_PATTERNS:
            if pattern in msg_lower:
                return "[REDACTED - contains sensitive data]"
        # Truncate very long messages
        if len(message) > 1000:
            return message[:1000] + "... [truncated]"
        return message

    def emit(self, record: logging.LogRecord):
        try:
            # Extract database name from record if available
            db = getattr(record, 'dbname', '') or ''

            entry = LogEntry(
                timestamp=datetime.fromtimestamp(record.created),
                level=record.levelname,
                module=record.name,
                message=self._sanitize_message(self.format(record)),
                db=db,
            )
            self.buffer.add(entry)
        except Exception:
            pass  # Never fail logging


# Global buffer instance
_log_buffer = None
_handler_installed = False


def get_log_buffer() -> LogBuffer:
    """Get or create the global log buffer."""
    global _log_buffer
    if _log_buffer is None:
        _log_buffer = LogBuffer(maxsize=500)
    return _log_buffer


def install_log_handler():
    """Install the MCP log handler on Odoo's root logger."""
    global _handler_installed
    if _handler_installed:
        return

    buffer = get_log_buffer()
    handler = McpLogHandler(buffer)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter('%(message)s'))

    # Add to root logger to capture all Odoo logs
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    _handler_installed = True
