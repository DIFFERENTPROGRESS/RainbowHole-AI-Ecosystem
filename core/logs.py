"""
RainbowHole V0 — Log Buffer
In-memory log capture for the cyberpunk terminal UI.
"""
from __future__ import annotations
import logging
from collections import deque
from datetime import datetime
from typing import Any


class LogBuffer(logging.Handler):
    """Captures log records in a ring buffer for the terminal UI."""

    def __init__(self, maxlen: int = 300):
        super().__init__()
        self.buffer: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        ))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.buffer.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            })
        except Exception:
            self.handleError(record)

    def snapshot(self) -> list[dict[str, Any]]:
        return list(self.buffer)


# Module-level singleton
_log_buffer: LogBuffer | None = None


def get_log_buffer() -> LogBuffer:
    global _log_buffer
    if _log_buffer is None:
        _log_buffer = LogBuffer()
        _log_buffer.setLevel(logging.DEBUG)
        root = logging.getLogger("rainbowhole")
        root.setLevel(logging.DEBUG)
        root.addHandler(_log_buffer)
    return _log_buffer
