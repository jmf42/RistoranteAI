from __future__ import annotations

import time
from collections import defaultdict, deque

_CLEANUP_INTERVAL = 300  # purge stale buckets every 5 minutes


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._last_cleanup: float = 0.0

    def reset(self) -> None:
        self._buckets.clear()

    def _maybe_cleanup(self, current_time: float, window_seconds: int) -> None:
        if current_time - self._last_cleanup < _CLEANUP_INTERVAL:
            return
        self._last_cleanup = current_time
        cutoff = current_time - window_seconds
        stale_keys = [key for key, bucket in self._buckets.items() if not bucket or bucket[-1] <= cutoff]
        for key in stale_keys:
            del self._buckets[key]

    def allow(self, *, key: str, limit: int, window_seconds: int, now: float | None = None) -> tuple[bool, int]:
        if limit <= 0:
            return True, 0

        current_time = now if now is not None else time.time()
        self._maybe_cleanup(current_time, window_seconds)

        bucket = self._buckets[key]
        cutoff = current_time - window_seconds

        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            retry_after = max(1, int(bucket[0] + window_seconds - current_time))
            return False, retry_after

        bucket.append(current_time)
        return True, 0
