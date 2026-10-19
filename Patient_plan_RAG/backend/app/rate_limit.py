"""In-memory sliding-window rate limiting per client.

Prototype-grade: state lives in this process only, so limits are per worker
and reset on restart. Put a shared store (e.g. Redis) behind this interface
before running more than one worker.
"""

import os
import time
from collections import deque


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str) -> float | None:
        """Record a hit for key; return None if allowed, else seconds to wait."""
        now = time.monotonic()
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return self.window - (now - hits[0])
        hits.append(now)
        return None

    def reset(self) -> None:
        self._hits.clear()


api_limiter = SlidingWindowLimiter(int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")))
upload_limiter = SlidingWindowLimiter(int(os.getenv("UPLOAD_RATE_LIMIT_PER_MINUTE", "10")))
